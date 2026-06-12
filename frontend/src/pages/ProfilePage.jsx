import { useRef, useState } from 'react'
import { useAuthStore } from '@/hooks/useAuth'
import { updateMe, uploadAvatar, deleteAvatar } from '@/api/auth'
import { PageShell, PageHeader, UserAvatar, Spinner } from '@/components/ui'
import { setTheme as applyAndStoreTheme, getStoredTheme } from '@/lib/theme'
import { useTranslation } from '@/lib/i18n'
import { ArrowUpTrayIcon, TrashIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'

// Theme-aligned palette: amber/orange first, then neutral blues, rose, slate.
// Purple and emerald/mint were removed when the global theme was refreshed.
const COLOR_OPTIONS = [
  { value: 'amber',  label: 'Amber',  swatch: 'bg-amber-500' },
  { value: 'orange', label: 'Orange', swatch: 'bg-orange-500' },
  { value: 'blue',   label: 'Blue',   swatch: 'bg-blue-500' },
  { value: 'sky',    label: 'Sky',    swatch: 'bg-sky-500' },
  { value: 'rose',   label: 'Rose',   swatch: 'bg-rose-500' },
  { value: 'slate',  label: 'Slate',  swatch: 'bg-slate-500' },
]

const ALLOWED_MIME = ['image/jpeg', 'image/png', 'image/webp']
const MAX_BYTES = 2 * 1024 * 1024

const THEME_OPTIONS = ['light', 'dark', 'system']
const LANGUAGE_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'vi', label: 'Tiếng Việt' },
]

function Card({ title, children }) {
  return (
    <section className="bg-card border border-border rounded-xl">
      <div className="px-5 py-3 border-b border-border">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  )
}

function StatusLine({ kind, children }) {
  if (!children) return null
  const Icon = kind === 'error' ? ExclamationCircleIcon : CheckCircleIcon
  const cls = kind === 'error' ? 'text-red-600 bg-red-50 border-red-100' : 'text-emerald-700 bg-emerald-50 border-emerald-100'
  return (
    <div className={`mt-3 px-3 py-2 rounded-lg border text-sm flex items-center gap-2 ${cls}`}>
      <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export default function ProfilePage() {
  const { user, setUser } = useAuthStore()
  const { t, lang, setLang } = useTranslation()
  const fileInputRef = useRef(null)

  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [phone, setPhone] = useState(user?.phone ?? '')
  const [color, setColor] = useState(user?.avatar_color ?? 'amber')
  const [savingProfile, setSavingProfile] = useState(false)
  const [profileMsg, setProfileMsg] = useState(null) // { kind, text }

  const [uploadError, setUploadError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [removing, setRemoving] = useState(false)

  // Preferences: local-only — the backend does not persist these yet, so
  // they live in localStorage. Keeping the same control here avoids a
  // disconnect when full i18n / theme persistence lands.
  const [theme, setTheme] = useState(() => getStoredTheme())

  const handleSaveProfile = async (e) => {
    e.preventDefault()
    setSavingProfile(true)
    setProfileMsg(null)
    try {
      const updated = await updateMe({
        full_name: fullName.trim(),
        phone: phone.trim() || null,
        avatar_color: color,
      })
      setUser(updated)
      setProfileMsg({ kind: 'ok', text: t('profile.savedOK') })
    } catch (err) {
      const detail = err?.response?.data?.detail
      setProfileMsg({
        kind: 'error',
        text: typeof detail === 'string' ? detail : t('profile.savedFail'),
      })
    } finally {
      setSavingProfile(false)
    }
  }

  const handleAvatarSelect = async (e) => {
    setUploadError('')
    const file = e.target.files?.[0]
    if (!file) return

    if (!ALLOWED_MIME.includes(file.type)) {
      setUploadError(t('profile.invalidType'))
      e.target.value = ''
      return
    }
    if (file.size > MAX_BYTES) {
      setUploadError(t('profile.tooLarge'))
      e.target.value = ''
      return
    }

    setUploading(true)
    try {
      const updated = await uploadAvatar(file)
      setUser(updated)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setUploadError(typeof detail === 'string' ? detail : t('profile.uploadFail'))
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const handleRemoveAvatar = async () => {
    setUploadError('')
    setRemoving(true)
    try {
      const updated = await deleteAvatar()
      setUser(updated)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setUploadError(typeof detail === 'string' ? detail : t('profile.removeFail'))
    } finally {
      setRemoving(false)
    }
  }

  const handleThemeChange = (value) => {
    setTheme(value)
    // Shared helper writes localStorage and toggles the `dark` class on
    // <html> so the whole app — sidebar excluded, it's always dark —
    // switches palette instantly.
    applyAndStoreTheme(value)
  }

  const handleLanguageChange = (value) => {
    // The provider stores the value and re-renders any component that
    // reads via useTranslation, so the whole UI flips immediately.
    setLang(value)
  }

  // Preview reflects the current pending color selection so the user sees the
  // fallback color update immediately, before they click Save.
  const previewUser = { ...user, full_name: fullName, avatar_color: color }

  return (
    <PageShell>
      <PageHeader
        title={t('profile.title')}
        subtitle={t('profile.subtitle')}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card title={t('profile.section.photo')}>
            <div className="flex flex-col items-center gap-4">
              <UserAvatar user={previewUser} size="xl" />
              <div className="text-center">
                <p className="font-semibold text-foreground">{user?.full_name || user?.email}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{user?.email}</p>
                <p className="text-xs text-muted-foreground capitalize mt-0.5">{user?.role}</p>
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleAvatarSelect}
                className="hidden"
                aria-label={t('profile.action.uploadFileLabel')}
              />

              <div className="flex flex-wrap items-center gap-2 justify-center">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading || removing}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
                >
                  {uploading ? <Spinner className="w-3.5 h-3.5 text-primary-foreground" /> : <ArrowUpTrayIcon className="w-4 h-4" aria-hidden="true" />}
                  {t('profile.action.upload')}
                </button>
                {user?.avatar_url && (
                  <button
                    type="button"
                    onClick={handleRemoveAvatar}
                    disabled={uploading || removing}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-input text-sm font-medium disabled:opacity-50"
                  >
                    {removing ? <Spinner className="w-3.5 h-3.5" /> : <TrashIcon className="w-4 h-4" aria-hidden="true" />}
                    {t('profile.action.remove')}
                  </button>
                )}
              </div>
              <p className="text-xs text-muted-foreground text-center">{t('profile.formatHint')}</p>
              <StatusLine kind="error">{uploadError}</StatusLine>
            </div>
          </Card>

          <Card title={t('profile.section.color')}>
            <p className="text-xs text-muted-foreground mb-3">
              {t('profile.colorHint')}
            </p>
            <div className="grid grid-cols-3 gap-2">
              {COLOR_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setColor(opt.value)}
                  className={`flex items-center gap-2 px-2 py-2 rounded-lg border text-sm transition-colors ${color === opt.value ? 'border-primary ring-2 ring-primary/30' : 'border-border hover:bg-muted/40'}`}
                  aria-pressed={color === opt.value}
                >
                  <span className={`w-4 h-4 rounded-full ${opt.swatch}`} aria-hidden="true" />
                  {opt.label}
                </button>
              ))}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={handleSaveProfile}>
            <Card title={t('profile.section.personalInfo')}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="full_name" className="text-xs font-medium text-muted-foreground">{t('profile.field.fullName')}</label>
                  <input
                    id="full_name"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    className="mt-1 w-full px-3 py-2 border border-input rounded-lg bg-background text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="phone" className="text-xs font-medium text-muted-foreground">{t('profile.field.phone')}</label>
                  <input
                    id="phone"
                    type="text"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="mt-1 w-full px-3 py-2 border border-input rounded-lg bg-background text-sm"
                  />
                </div>
                <div>
                  <label htmlFor="email" className="text-xs font-medium text-muted-foreground">{t('profile.field.email')}</label>
                  <input
                    id="email"
                    type="email"
                    value={user?.email ?? ''}
                    readOnly
                    className="mt-1 w-full px-3 py-2 border border-input rounded-lg bg-muted/40 text-sm text-muted-foreground cursor-not-allowed"
                  />
                </div>
                <div>
                  <label htmlFor="role" className="text-xs font-medium text-muted-foreground">{t('profile.field.role')}</label>
                  <input
                    id="role"
                    type="text"
                    value={user?.role ?? ''}
                    readOnly
                    className="mt-1 w-full px-3 py-2 border border-input rounded-lg bg-muted/40 text-sm text-muted-foreground capitalize cursor-not-allowed"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="org" className="text-xs font-medium text-muted-foreground">{t('profile.field.organization')}</label>
                  <input
                    id="org"
                    type="text"
                    value={user?.org_name ?? '—'}
                    readOnly
                    className="mt-1 w-full px-3 py-2 border border-input rounded-lg bg-muted/40 text-sm text-muted-foreground cursor-not-allowed"
                  />
                </div>
              </div>

              <div className="mt-5 flex items-center justify-end">
                <button
                  type="submit"
                  disabled={savingProfile}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
                >
                  {savingProfile && <Spinner className="w-3.5 h-3.5 text-primary-foreground" />}
                  {t('profile.save')}
                </button>
              </div>
              {profileMsg && <StatusLine kind={profileMsg.kind}>{profileMsg.text}</StatusLine>}
            </Card>
          </form>

          <Card title={t('profile.section.preferences')}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <span className="text-xs font-medium text-muted-foreground">{t('profile.theme')}</span>
                <div className="mt-1 flex gap-2" role="radiogroup" aria-label={t('profile.theme')}>
                  {THEME_OPTIONS.map((themeOpt) => (
                    <button
                      key={themeOpt}
                      type="button"
                      onClick={() => handleThemeChange(themeOpt)}
                      aria-pressed={theme === themeOpt}
                      className={`flex-1 px-3 py-2 rounded-lg border text-sm ${theme === themeOpt ? 'border-primary ring-2 ring-primary/30' : 'border-border hover:bg-muted/40'}`}
                    >
                      {t(`profile.theme.${themeOpt}`)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label htmlFor="language" className="text-xs font-medium text-muted-foreground">{t('profile.language')}</label>
                <select
                  id="language"
                  value={lang}
                  onChange={(e) => handleLanguageChange(e.target.value)}
                  className="mt-1 w-full px-3 py-2 border border-input rounded-lg bg-background text-sm"
                >
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              {t('profile.preferencesNote')}
            </p>
          </Card>
        </div>
      </div>
    </PageShell>
  )
}
