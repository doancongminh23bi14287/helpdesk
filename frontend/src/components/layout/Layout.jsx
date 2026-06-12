import { Link, NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  HomeIcon, TicketIcon, ServerStackIcon, BellIcon,
  ArrowRightStartOnRectangleIcon, Bars3Icon, XMarkIcon,
  PlusCircleIcon, ChevronRightIcon,
  ClipboardDocumentListIcon, BuildingOffice2Icon, UserGroupIcon, ShieldCheckIcon,
  CubeIcon, TagIcon, CreditCardIcon, DocumentTextIcon,
  MagnifyingGlassIcon, PresentationChartBarIcon,
} from '@heroicons/react/24/outline'
import {
  HomeIcon as HomeSolid,
  TicketIcon as TicketSolid,
  ServerStackIcon as ServerSolid,
  BellIcon as BellSolid,
  ClipboardDocumentListIcon as ClipboardSolid,
  BuildingOffice2Icon as BuildingSolid,
  UserGroupIcon as UserGroupSolid,
  ShieldCheckIcon as ShieldSolid,
  CubeIcon as CubeSolid,
  TagIcon as TagSolid,
  CreditCardIcon as CreditCardSolid,
  DocumentTextIcon as DocumentTextSolid,
  PresentationChartBarIcon as PresentationChartBarSolid,
} from '@heroicons/react/24/solid'
import { useState, useRef, useEffect } from 'react'
import { useAuthStore } from '@/hooks/useAuth'
import { useRole } from '@/hooks/useRole'
import { useSocket } from '@/hooks/useSocket'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { getNotifications, markAllRead, markRead } from '@/api/notifications'
import { Avatar, AvatarFallback, ToastContainer, UserAvatar } from '@/components/ui'
import { useTranslation } from '@/lib/i18n'
import { cn } from '@/lib/utils'
import { motion, AnimatePresence } from 'framer-motion'
import ProfileSettings from './ProfileSettings'
import { formatDateTime } from '@/lib/utils'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import CommandPalette from '@/components/ui/CommandPalette'

// Nav items keyed by id; labels are resolved at render time so the
// sidebar reacts to language changes without remounting.
const NAV_ITEMS = {
  dashboard:        { labelKey: 'nav.dashboard',         href: '/',                        icon: HomeIcon,                  iconActive: HomeSolid },
  organizations:    { labelKey: 'nav.organizations',     href: '/admin/organizations',     icon: BuildingOffice2Icon,       iconActive: BuildingSolid },
  users:            { labelKey: 'nav.users',             href: '/admin/users',             icon: UserGroupIcon,             iconActive: UserGroupSolid },
  staffAssignments: { labelKey: 'nav.staffAssignments',  href: '/admin/staff-assignments', icon: UserGroupIcon,             iconActive: UserGroupSolid },
  services:         { labelKey: 'nav.services',          href: '/services',                icon: ServerStackIcon,           iconActive: ServerSolid },
  seoProjects:      { labelKey: 'nav.seoProjects',       href: '/projects',                icon: ClipboardDocumentListIcon, iconActive: ClipboardSolid },
  myTickets:        { labelKey: 'nav.myTickets',         href: '/tickets',                 icon: TicketIcon,                iconActive: TicketSolid },
  allTickets:       { labelKey: 'nav.allTickets',        href: '/tickets',                 icon: TicketIcon,                iconActive: TicketSolid },
  notifications:    { labelKey: 'nav.notifications',     href: '/notifications',           icon: BellIcon,                  iconActive: BellSolid },
  slaPolicies:      { labelKey: 'nav.slaPolicies',       href: '/admin/sla',               icon: ShieldCheckIcon,           iconActive: ShieldSolid },
  items:            { labelKey: 'nav.items',             href: '/admin/items',             icon: CubeIcon,                  iconActive: CubeSolid },
  subscriptions:    { labelKey: 'nav.subscriptions',     href: '/admin/subscriptions',     icon: CreditCardIcon,            iconActive: CreditCardSolid },
  invoicesAdmin:    { labelKey: 'nav.invoices',          href: '/admin/invoices',          icon: DocumentTextIcon,          iconActive: DocumentTextSolid },
  invoicesMine:     { labelKey: 'nav.invoices',          href: '/invoices',                icon: DocumentTextIcon,          iconActive: DocumentTextSolid },
  emailOutbox:      { labelKey: 'nav.emailOutbox',       href: '/admin/email-outbox',      icon: DocumentTextIcon,          iconActive: DocumentTextSolid },
  analytics:        { labelKey: 'nav.analytics',         href: '/admin/analytics',         icon: PresentationChartBarIcon,  iconActive: PresentationChartBarSolid },
  systemStatus:     { labelKey: 'nav.systemStatus',      href: '/admin/system',            icon: ServerStackIcon,           iconActive: ServerSolid },
  accountSecurity:  { labelKey: 'nav.accountSecurity',   href: '/account/security',        icon: ShieldCheckIcon,           iconActive: ShieldSolid },
}

function navSectionsForRole(role) {
  if (role === 'customer') {
    return [
      { titleKey: 'sidebar.section.main',        items: [NAV_ITEMS.dashboard] },
      { titleKey: 'sidebar.section.myServices',  items: [NAV_ITEMS.services, NAV_ITEMS.seoProjects] },
      { titleKey: 'sidebar.section.support',     items: [NAV_ITEMS.myTickets, NAV_ITEMS.notifications, NAV_ITEMS.invoicesMine] },
      { titleKey: 'sidebar.section.account',     items: [NAV_ITEMS.accountSecurity] },
    ]
  }
  if (role === 'staff') {
    return [
      { titleKey: 'sidebar.section.main',      items: [NAV_ITEMS.dashboard] },
      { titleKey: 'sidebar.section.delivery',  items: [NAV_ITEMS.seoProjects, NAV_ITEMS.services] },
      { titleKey: 'sidebar.section.support',   items: [NAV_ITEMS.allTickets, NAV_ITEMS.notifications] },
      { titleKey: 'sidebar.section.reporting', items: [NAV_ITEMS.analytics] },
      { titleKey: 'sidebar.section.account',   items: [NAV_ITEMS.accountSecurity] },
    ]
  }
  // admin (default)
  return [
    { titleKey: 'sidebar.section.main',             items: [NAV_ITEMS.dashboard] },
    { titleKey: 'sidebar.section.clientManagement', items: [NAV_ITEMS.organizations, NAV_ITEMS.users, NAV_ITEMS.staffAssignments, NAV_ITEMS.services] },
    { titleKey: 'sidebar.section.delivery',         items: [NAV_ITEMS.seoProjects] },
    { titleKey: 'sidebar.section.support',          items: [NAV_ITEMS.allTickets, NAV_ITEMS.notifications, NAV_ITEMS.slaPolicies] },
    { titleKey: 'sidebar.section.billing',          items: [NAV_ITEMS.items, NAV_ITEMS.subscriptions, NAV_ITEMS.invoicesAdmin, NAV_ITEMS.emailOutbox] },
    { titleKey: 'sidebar.section.reporting',        items: [NAV_ITEMS.analytics, NAV_ITEMS.systemStatus] },
    { titleKey: 'sidebar.section.account',          items: [NAV_ITEMS.accountSecurity] },
  ]
}

const breadcrumbLabels = {
  '':              'Dashboard',
  'tickets':       'Tickets',
  'projects':      'SEO Projects',
  'new':           'New Ticket',
  'services':      'Services',
  'notifications': 'Notifications',
  'admin':         'Admin',
  'organizations': 'Organizations',
  'users':         'Users',
  'items':         'Items',
  'subscriptions': 'Subscriptions',
  'invoices':      'Invoices',
  'sla':           'SLA Policies',
  'analytics':     'Analytics',
  'account':       'Account',
  'security':      'Security',
  'system':        'System Status',
  'email-outbox':  'Email Outbox',
}

function useBreadcrumbs() {
  const { pathname } = useLocation()
  const parts = pathname.split('/').filter(Boolean)
  return parts.map((part, i) => ({
    label: breadcrumbLabels[part] ?? `#${part}`,
    href: '/' + parts.slice(0, i + 1).join('/'),
    isLast: i === parts.length - 1,
  }))
}

function NavItem({ labelKey, href, icon: Icon, iconActive: ActiveIcon, onClose }) {
  const { t } = useTranslation()
  const label = t(labelKey)
  return (
    <NavLink
      to={href}
      end={href === '/'}
      onClick={onClose}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all duration-150',
          isActive
            ? 'text-sidebar-accent-foreground'
            : 'text-sidebar-foreground hover:text-sidebar-accent-foreground hover:bg-[#18181B]',
        )
      }
      style={({ isActive }) => isActive
        ? { background: '#1A1A1A', boxShadow: 'inset 3px 0 0 hsl(var(--sidebar-primary))' }
        : {}}
    >
      {({ isActive }) => (
        <>
          <span
            className="flex-shrink-0"
            style={isActive ? { color: '#F59E0B' } : { color: '#737373' }}
          >
            {isActive
              ? <ActiveIcon className="w-[18px] h-[18px]" />
              : <Icon className="w-[18px] h-[18px]" />}
          </span>
          <span className="flex-1">{label}</span>
          {isActive && (
            <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: 'hsl(var(--sidebar-primary))' }} />
          )}
        </>
      )}
    </NavLink>
  )
}

function Sidebar({ onClose, onOpenSearch, width = 256 }) {
  const { user, logout } = useAuthStore()
  const { role } = useRole()
  const navigate = useNavigate()
  const { t } = useTranslation()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const email = user?.email ?? (typeof user === 'string' ? user : '')
  const initials = (user?.full_name || email).slice(0, 2).toUpperCase() || '??'
  const displayName = user?.full_name ?? email.split('@')[0] ?? 'User'

  const sections = navSectionsForRole(role)

  return (
    <aside className="flex flex-col h-full flex-shrink-0 bg-sidebar" style={{ width: `${width}px` }}>
      {/* Logo */}
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
               style={{ background: '#111111', border: '1px solid rgba(245, 158, 11, 0.55)' }}>
            <svg className="w-4 h-4" style={{ color: 'hsl(var(--sidebar-primary))' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
            </svg>
          </div>
          <div>
            <p className="font-bold text-[15px] text-sidebar-accent-foreground leading-tight tracking-tight">
              WorkDesk
            </p>
            <p className="text-[10px]" style={{ color: '#A3A3A3' }}>
              {t('sidebar.brand.subtitle')}
            </p>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="mx-4 h-px" style={{ background: 'hsl(var(--sidebar-border))' }} />

      {/* New Ticket CTA — amber-bordered dark button matches the reference. */}
      <div className="px-4 pt-4">
        <NavLink
          to="/tickets/new"
          onClick={onClose}
          className="group flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-semibold transition-colors"
          style={{
            background: '#111111',
            color: '#FAFAFA',
            border: '1px solid rgba(245, 158, 11, 0.55)',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'hsl(var(--sidebar-primary) / 0.12)' }}
          onMouseLeave={(e) => { e.currentTarget.style.background = '#111111' }}
        >
          <PlusCircleIcon className="w-4 h-4" style={{ color: 'hsl(var(--sidebar-primary))' }} aria-hidden="true" />
          {t('nav.newTicket')}
        </NavLink>

        {/* Search button */}
        <button
          onClick={onOpenSearch}
          className="mx-0 mt-3 flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm transition-colors border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          style={{ background: '#111111', borderColor: '#262626', color: '#A3A3A3' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = '#18181B'
            e.currentTarget.style.color = '#FAFAFA'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = '#111111'
            e.currentTarget.style.color = '#A3A3A3'
          }}
        >
          <MagnifyingGlassIcon className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1 text-left">{t('nav.search')}</span>
          <kbd className="text-[10px] px-1.5 py-0.5 rounded border" style={{ background: '#18181B', borderColor: '#262626', color: '#737373' }}>⌘K</kbd>
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto scrollbar-thin">
        {sections.map((section, idx) => (
          <div key={section.titleKey} className={idx === 0 ? '' : 'mt-3'}>
            <p className="px-3 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-widest"
               style={{ color: '#737373' }}>
              {t(section.titleKey)}
            </p>
            {section.items.map((item) => (
              <NavItem key={section.titleKey + item.href + item.labelKey} {...item} onClose={onClose} />
            ))}
          </div>
        ))}
      </nav>

      {/* Divider */}
      <div className="mx-4 h-px" style={{ background: 'hsl(var(--sidebar-border))' }} />

      {/* User footer */}
      <div className="px-3 py-4">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg"
             style={{ background: '#111111', border: '1px solid #262626' }}>
          <UserAvatar user={user} size="md" />
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold text-sidebar-accent-foreground truncate">{displayName}</p>
            <p className="text-[11px] truncate" style={{ color: '#A3A3A3' }}>
              {email}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
            className="p-1.5 rounded-lg transition-colors hover:bg-amber-500/10 hover:text-amber-500 flex-shrink-0"
            style={{ color: '#737373' }}
          >
            <ArrowRightStartOnRectangleIcon className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </aside>
  )
}

/* ── Notification bell ── */
function NotificationBell() {
  const { unreadCount, setUnreadCount, clearUnread } = useNotificationStore()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [loadingNotifs, setLoadingNotifs] = useState(false)
  const navigate = useNavigate()
  const ref = useRef(null)
  const { t } = useTranslation()

  // Load unread count on mount
  useEffect(() => {
    getNotifications()
      .then((data) => {
        const list = Array.isArray(data) ? data : []
        setNotifications(list)
        setUnreadCount(list.filter((n) => !n.is_read).length)
      })
      .catch(() => {})
  }, [setUnreadCount])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleOpen = async () => {
    setOpen((o) => !o)
    if (!open) {
      setLoadingNotifs(true)
      try {
        const data = await getNotifications()
        const list = Array.isArray(data) ? data : []
        setNotifications(list)
        setUnreadCount(list.filter((n) => !n.is_read).length)
      } finally {
        setLoadingNotifs(false)
      }
    }
  }

  const handleMarkAll = async () => {
    await markAllRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    clearUnread()
  }

  const handleClick = async (n) => {
    if (!n.is_read) {
      await markRead(n.id).catch(() => {})
      setNotifications((prev) => prev.map((x) => x.id === n.id ? { ...x, is_read: true } : x))
      setUnreadCount(Math.max(0, unreadCount - 1))
    }
    setOpen(false)
    if (n.ref_ticket_id) navigate(`/tickets/${n.ref_ticket_id}`)
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={handleOpen}
        className="relative p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        title={t('topbar.notifications')}
        aria-label={unreadCount > 0 ? `${t('topbar.notifications')} (${unreadCount})` : t('topbar.notifications')}
      >
        <BellIcon className="w-5 h-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white leading-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-80 bg-card border border-border rounded-xl shadow-xl z-50 overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-sm font-semibold text-foreground">{t('topbar.notifications')}</span>
              {unreadCount > 0 && (
                <button onClick={handleMarkAll} className="text-xs text-primary hover:underline">
                  {t('topbar.markAllRead')}
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto divide-y divide-border">
              {loadingNotifs ? (
                <div className="flex justify-center py-8">
                  <svg className="animate-spin h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                </div>
              ) : notifications.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">{t('topbar.allCaughtUp')}</p>
              ) : (
                notifications.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => handleClick(n)}
                    className={cn(
                      'w-full text-left px-4 py-3 hover:bg-muted/50 transition-colors',
                      !n.is_read && 'bg-primary/[0.03]',
                    )}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-1" />}
                      <div className="flex-1 min-w-0">
                        <p className={cn('text-xs leading-snug', !n.is_read ? 'font-semibold text-foreground' : 'text-foreground/80')}>
                          {n.title}
                        </p>
                        {n.content && <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">{n.content}</p>}
                        <p className="text-[10px] text-muted-foreground mt-1">{formatDateTime(n.created_at)}</p>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Topbar({ onMenuClick }) {
  const breadcrumbs = useBreadcrumbs()
  const { t } = useTranslation()

  return (
    <header className="flex items-center justify-between h-14 px-5 border-b border-border bg-card flex-shrink-0 relative z-30">
      <div className="flex items-center gap-3 min-w-0">
        {/* Mobile hamburger */}
        <button
          onClick={onMenuClick}
          aria-label="Open navigation menu"
          className="md:hidden p-2 -ml-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors flex-shrink-0"
        >
          <Bars3Icon className="w-5 h-5" aria-hidden="true" />
        </button>

        {/* Breadcrumbs */}
        <nav className="flex items-center gap-1 text-sm min-w-0 overflow-hidden">
          <Link
            to="/"
            className="text-muted-foreground font-medium hover:text-foreground transition-colors whitespace-nowrap"
          >
            {t('topbar.home')}
          </Link>
          {breadcrumbs.map(({ label, href, isLast }) => (
            <span key={label} className="flex items-center gap-1 flex-shrink-0">
              <ChevronRightIcon className="w-3.5 h-3.5 text-muted-foreground/50" />
              {isLast ? (
                <span className="font-medium text-foreground truncate">{label}</span>
              ) : (
                <Link
                  to={href}
                  className="font-medium text-muted-foreground hover:text-foreground transition-colors whitespace-nowrap"
                >
                  {label}
                </Link>
              )}
            </span>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <NotificationBell />
        {/* Profile Settings Dropdown */}
        <ProfileSettings />
      </div>
    </header>
  )
}

export default function Layout({ children }) {
  useSocket()
  const [open, setOpen] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('sidebarWidth')
    return saved ? parseInt(saved) : 256
  })
  const [isResizing, setIsResizing] = useState(false)
  const resizeRef = useRef(null)

  useEffect(() => {
    if (!isResizing) return

    let currentWidth = sidebarWidth

    const handleMouseMove = (e) => {
      currentWidth = Math.max(200, Math.min(500, e.clientX))
      setSidebarWidth(currentWidth)
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      localStorage.setItem('sidebarWidth', currentWidth.toString())
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing])

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <ToastContainer />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      {/* Desktop sidebar */}
      <div className="hidden md:flex flex-shrink-0 relative group">
        <Sidebar width={sidebarWidth} onOpenSearch={() => setPaletteOpen(true)} />

        {/* Resize handle */}
        <div
          ref={resizeRef}
          onMouseDown={() => setIsResizing(true)}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          className="w-1 bg-border cursor-col-resize hover:bg-primary/50 transition-colors group-hover:bg-primary/30"
          title="Drag to resize sidebar"
        />
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-50 md:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setOpen(false)}
            />
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="relative flex h-full w-64"
            >
              <Sidebar onClose={() => setOpen(false)} onOpenSearch={() => { setOpen(false); setPaletteOpen(true) }} width={256} />
              <button
                onClick={() => setOpen(false)}
                aria-label="Close navigation menu"
                className="absolute top-4 right-3 p-1.5 rounded-lg text-white/40 hover:text-white transition-colors"
              >
                <XMarkIcon className="w-4 h-4" aria-hidden="true" />
              </button>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Topbar onMenuClick={() => setOpen(true)} />
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  )
}
