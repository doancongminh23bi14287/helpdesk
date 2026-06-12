import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/hooks/useAuth'
import { UserAvatar } from '@/components/ui'
import { useTranslation } from '@/lib/i18n'
import {
  ArrowRightStartOnRectangleIcon,
  UserCircleIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import { motion, AnimatePresence } from 'framer-motion'

export default function ProfileSettings() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  const handleLogout = async () => {
    setOpen(false)
    await logout()
    navigate('/login')
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="h-9 w-9 rounded-full ring-2 ring-offset-1 ring-offset-background ring-border hover:ring-foreground transition-all"
        aria-label={t('profile.menu.openMenu')}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <UserAvatar user={user} size="md" />
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40"
              onClick={() => setOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-11 w-60 bg-card border border-border rounded-lg shadow-lg p-2 z-50"
              role="menu"
            >
              <div className="flex items-center gap-3 px-3 py-2 mb-2 border-b border-border">
                <UserAvatar user={user} size="md" />
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-foreground truncate">{user?.full_name || user?.email}</p>
                  <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                </div>
              </div>

              <Link
                to="/profile"
                onClick={() => setOpen(false)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted rounded-lg transition-colors"
                role="menuitem"
              >
                <UserCircleIcon className="w-4 h-4" aria-hidden="true" />
                {t('profile.menu.myProfile')}
              </Link>
              <Link
                to="/preferences"
                onClick={() => setOpen(false)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted rounded-lg transition-colors"
                role="menuitem"
              >
                <Cog6ToothIcon className="w-4 h-4" aria-hidden="true" />
                {t('profile.menu.preferences')}
              </Link>
              <Link
                to="/account/security"
                onClick={() => setOpen(false)}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-muted rounded-lg transition-colors"
                role="menuitem"
              >
                <ShieldCheckIcon className="w-4 h-4" aria-hidden="true" />
                {t('profile.menu.accountSecurity')}
              </Link>

              <div className="my-1 h-px bg-border" />

              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                role="menuitem"
              >
                <ArrowRightStartOnRectangleIcon className="w-4 h-4" aria-hidden="true" />
                {t('profile.menu.signOut')}
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
