import { NavLink, useNavigate } from 'react-router-dom'
import {
  ArrowRightStartOnRectangleIcon,
  MagnifyingGlassIcon,
  PlusCircleIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import { useAuthStore } from '@/hooks/useAuth'
import { useRole } from '@/hooks/useRole'
import { useTranslation } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { UserAvatar } from '@/components/ui'
import { navSectionsForRole } from './navigation'

function SidebarItem({ labelKey, href, icon: Icon, iconActive: ActiveIcon, onNavigate }) {
  const { t } = useTranslation()
  return (
    <NavLink
      to={href}
      end={href === '/'}
      onClick={onNavigate}
      className={({ isActive }) => cn(
        'flex min-h-11 items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:ring-inset',
        isActive
          ? 'bg-sidebar-active text-white'
          : 'text-sidebar-foreground hover:bg-sidebar-hover hover:text-white',
      )}
    >
      {({ isActive }) => {
        const ResolvedIcon = isActive ? ActiveIcon : Icon
        return (
          <>
            <ResolvedIcon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate">{t(labelKey)}</span>
          </>
        )
      }}
    </NavLink>
  )
}

export function SidebarSection({ titleKey, items, onNavigate }) {
  const { t } = useTranslation()
  return (
    <section className="mt-4 first:mt-0">
      <h2 className="px-3 pb-2 text-xs font-semibold uppercase text-sidebar-foreground/65">
        {t(titleKey)}
      </h2>
      <div className="space-y-0.5">
        {items.map((item) => (
          <SidebarItem key={`${titleKey}-${item.href}-${item.labelKey}`} {...item} onNavigate={onNavigate} />
        ))}
      </div>
    </section>
  )
}

export function Sidebar({ onNavigate, onOpenSearch }) {
  const { user, logout } = useAuthStore()
  const { role } = useRole()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const email = user?.email ?? (typeof user === 'string' ? user : '')
  const displayName = user?.full_name ?? email.split('@')[0] ?? 'User'

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <aside className="flex h-full w-full shrink-0 md:w-sidebar flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="flex h-topbar items-center gap-3 px-5">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-sidebar-border bg-black/20">
          <UserGroupIcon className="h-4 w-4 text-primary" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-white">CustomerHub</p>
          <p className="text-xs text-sidebar-foreground/70">OSD.vn</p>
        </div>
      </div>

      <div className="border-t border-sidebar-border px-4 pt-4">
        <NavLink to="/tickets/new" onClick={onNavigate} className="btn-primary min-h-11 w-full">
          <PlusCircleIcon className="h-4 w-4" aria-hidden="true" />
          {t('nav.newTicket')}
        </NavLink>
        <button
          type="button"
          onClick={onOpenSearch}
          className="mt-3 flex h-11 w-full items-center gap-2 rounded-md border border-sidebar-border bg-black/15 px-3 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-hover hover:text-white focus-visible:ring-2 focus-visible:ring-sidebar-ring"
        >
          <MagnifyingGlassIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-left">{t('nav.search')}</span>
          <kbd className="rounded border border-sidebar-border px-1.5 py-0.5 text-[10px]">⌘K</kbd>
        </button>
      </div>

      <nav className="scrollbar-thin flex-1 overflow-y-auto px-3 py-4" aria-label="Primary navigation">
        {navSectionsForRole(role).map((section) => (
          <SidebarSection key={section.titleKey} {...section} onNavigate={onNavigate} />
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-md bg-black/15 px-3 py-2.5">
          <UserAvatar user={user} size="md" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-white">{displayName}</p>
            <p className="truncate text-xs text-sidebar-foreground/70">{email}</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
            className="rounded-md p-2 text-sidebar-foreground transition-colors hover:bg-sidebar-hover hover:text-white focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          >
            <ArrowRightStartOnRectangleIcon className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </aside>
  )
}
