import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MagnifyingGlassIcon,
  HomeIcon,
  TicketIcon,
  PlusCircleIcon,
  ServerStackIcon,
  BellIcon,
  DocumentTextIcon,
  BuildingOffice2Icon,
  UserGroupIcon,
  CubeIcon,
  TagIcon,
  CreditCardIcon,
  ShieldCheckIcon,
  CogIcon,
  ClockIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline'
import { useAuthStore } from '@/hooks/useAuth'
import client from '@/api/client'
import { cn } from '@/lib/utils'

// ── History helpers ───────────────────────────────────────────────────────────

const HISTORY_KEY = 'cmd_palette_history'
const MAX_HISTORY = 5

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]')
  } catch {
    return []
  }
}

function saveToHistory(item) {
  const history = getHistory()
  const filtered = history.filter((h) => h.href !== item.href)
  const next = [{ label: item.label, href: item.href }, ...filtered].slice(0, MAX_HISTORY)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
}

// ── Static nav items ──────────────────────────────────────────────────────────

const ICON_MAP = {
  home: HomeIcon,
  ticket: TicketIcon,
  plus: PlusCircleIcon,
  server: ServerStackIcon,
  bell: BellIcon,
  document: DocumentTextIcon,
  building: BuildingOffice2Icon,
  users: UserGroupIcon,
  cube: CubeIcon,
  tag: TagIcon,
  'credit-card': CreditCardIcon,
  shield: ShieldCheckIcon,
  cog: CogIcon,
}

const NAV_ITEMS = [
  { label: 'Dashboard',       href: '/',                      icon: 'home' },
  { label: 'Tickets',         href: '/tickets',               icon: 'ticket' },
  { label: 'New Ticket',      href: '/tickets/new',           icon: 'plus' },
  { label: 'Services',        href: '/services',              icon: 'server' },
  { label: 'Notifications',   href: '/notifications',         icon: 'bell' },
  { label: 'Invoices',        href: '/invoices',              icon: 'document',      roles: ['customer'] },
  { label: 'Organizations',   href: '/admin/organizations',   icon: 'building',      roles: ['admin'] },
  { label: 'Users',           href: '/admin/users',           icon: 'users',         roles: ['admin'] },
  { label: 'Items',           href: '/admin/items',           icon: 'cube',          roles: ['admin'] },
  { label: 'Subscriptions',   href: '/admin/subscriptions',   icon: 'credit-card',   roles: ['admin'] },
  { label: 'Admin Invoices',  href: '/admin/invoices',        icon: 'document',      roles: ['admin'] },
  { label: 'SLA Policies',    href: '/admin/sla',             icon: 'shield',        roles: ['admin'] },
  { label: 'Setup Wizard',    href: '/admin/setup',           icon: 'cog',           roles: ['admin'] },
]

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4 text-primary flex-shrink-0" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

// ── Result item ───────────────────────────────────────────────────────────────

function ResultItem({ label, sublabel, icon: Icon, isActive, onClick }) {
  return (
    <button
      onMouseDown={(e) => { e.preventDefault(); onClick() }}
      className={cn(
        'w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors',
        isActive
          ? 'bg-primary/10 border-l-2 border-primary text-foreground'
          : 'border-l-2 border-transparent text-foreground/80 hover:bg-muted/50',
      )}
    >
      {Icon && <Icon className={cn('w-4 h-4 flex-shrink-0', isActive ? 'text-primary' : 'text-muted-foreground')} />}
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium truncate block">{label}</span>
        {sublabel && (
          <span className="text-xs text-muted-foreground truncate block">{sublabel}</span>
        )}
      </div>
      {isActive && <ArrowRightIcon className="w-3.5 h-3.5 text-primary flex-shrink-0" />}
    </button>
  )
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionHeader({ label }) {
  return (
    <div className="px-4 pt-3 pb-1">
      <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{label}</span>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CommandPalette({ open, onClose }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState({ navigation: [], tickets: [], users: [], orgs: [], items: [] })
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [history, setHistory] = useState([])
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  const isAdmin = user?.role === 'admin'

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setHistory(getHistory())
      setTimeout(() => inputRef.current?.focus(), 0)
    } else {
      setQuery('')
      setResults({ navigation: [], tickets: [], users: [], orgs: [], items: [] })
      setActiveIndex(0)
      setLoading(false)
    }
  }, [open])

  // Build flat list of all visible result items for keyboard navigation
  const flatItems = buildFlatItems(query, results, history, isAdmin)

  // Perform search
  const doSearch = useCallback(async (q) => {
    if (!q.trim()) {
      setResults({ navigation: [], tickets: [], users: [], orgs: [], items: [] })
      setLoading(false)
      return
    }

    // Navigation: instant filter
    const lower = q.toLowerCase()
    const role = user?.role
    const filteredNav = NAV_ITEMS.filter((item) => {
      if (item.roles && !item.roles.includes(role)) return false
      return item.label.toLowerCase().includes(lower)
    })

    setResults((prev) => ({ ...prev, navigation: filteredNav }))

    // API search (debounced)
    setLoading(true)
    try {
      const requests = [
        client.get('/tickets', { params: { search: q, per_page: 5, page: 1 } }).catch(() => null),
        client.get('/items', { params: { search: q, per_page: 5, page: 1, paginated: true } }).catch(() => null),
      ]
      if (isAdmin) {
        requests.push(
          client.get('/users', { params: { search: q, per_page: 5, page: 1 } }).catch(() => null),
          client.get('/organizations', { params: { search: q, per_page: 5, page: 1 } }).catch(() => null),
        )
      }

      const [ticketsRes, itemsRes, usersRes, orgsRes] = await Promise.all(requests)

      setResults({
        navigation: filteredNav,
        tickets: ticketsRes?.data?.items ?? [],
        items: itemsRes?.data?.items ?? [],
        users: usersRes?.data?.items ?? [],
        orgs: orgsRes?.data?.items ?? [],
      })
    } catch {
      // silently ignore network errors
    } finally {
      setLoading(false)
    }
  }, [user?.role, isAdmin])

  // Debounce search
  useEffect(() => {
    if (!open) return
    clearTimeout(debounceRef.current)
    setActiveIndex(0)

    if (!query.trim()) {
      setResults({ navigation: [], tickets: [], users: [], orgs: [], items: [] })
      setLoading(false)
      return
    }

    // Run nav filter instantly
    const lower = query.toLowerCase()
    const role = user?.role
    const filteredNav = NAV_ITEMS.filter((item) => {
      if (item.roles && !item.roles.includes(role)) return false
      return item.label.toLowerCase().includes(lower)
    })
    setResults((prev) => ({ ...prev, navigation: filteredNav }))

    // Debounce API calls
    debounceRef.current = setTimeout(() => {
      doSearch(query)
    }, 300)

    return () => clearTimeout(debounceRef.current)
  }, [query, open, doSearch, user?.role])

  // Keyboard navigation
  useEffect(() => {
    if (!open) return

    function handler(e) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((i) => (i + 1) % Math.max(1, flatItems.length))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((i) => (i - 1 + Math.max(1, flatItems.length)) % Math.max(1, flatItems.length))
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        const item = flatItems[activeIndex]
        if (item) selectItem(item)
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, flatItems, activeIndex, onClose])

  function selectItem(item) {
    saveToHistory(item)
    navigate(item.href)
    onClose()
  }

  if (!open) return null

  const showHistory = !query.trim() && history.length > 0
  const hasResults = flatItems.length > 0
  const showEmpty = query.trim() && !loading && !hasResults

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-start justify-center pt-[15vh] px-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-full max-w-lg bg-card border border-border rounded-xl shadow-2xl overflow-hidden flex flex-col"
        style={{ maxHeight: '60vh' }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <MagnifyingGlassIcon className="w-5 h-5 text-muted-foreground flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages, tickets, users..."
            className="flex-1 bg-transparent text-base text-foreground placeholder:text-muted-foreground outline-none"
          />
          {loading && <Spinner />}
          <kbd className="hidden sm:inline-flex text-[10px] px-1.5 py-0.5 rounded bg-muted border border-border text-muted-foreground">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {/* History (shown when query is empty) */}
          {showHistory && (
            <>
              <SectionHeader label="Recent" />
              {history.map((item, i) => (
                <ResultItem
                  key={item.href}
                  label={item.label}
                  icon={ClockIcon}
                  isActive={activeIndex === i}
                  onClick={() => selectItem(item)}
                />
              ))}
            </>
          )}

          {/* Navigation results */}
          {results.navigation.length > 0 && (
            <>
              <SectionHeader label="Navigation" />
              {results.navigation.map((item) => {
                const Icon = ICON_MAP[item.icon]
                const flatIdx = flatItems.findIndex((f) => f.href === item.href && f._section === 'navigation')
                return (
                  <ResultItem
                    key={item.href + item.label}
                    label={item.label}
                    icon={Icon}
                    isActive={activeIndex === flatIdx}
                    onClick={() => selectItem({ label: item.label, href: item.href })}
                  />
                )
              })}
            </>
          )}

          {/* Ticket results */}
          {results.tickets.length > 0 && (
            <>
              <SectionHeader label="Tickets" />
              {results.tickets.map((ticket) => {
                const href = `/tickets/${ticket.id}`
                const flatIdx = flatItems.findIndex((f) => f.href === href && f._section === 'tickets')
                return (
                  <ResultItem
                    key={ticket.id}
                    label={`#${ticket.id} - ${ticket.subject}`}
                    icon={TicketIcon}
                    isActive={activeIndex === flatIdx}
                    onClick={() => selectItem({ label: `#${ticket.id} - ${ticket.subject}`, href })}
                  />
                )
              })}
            </>
          )}

          {/* User results (admin only) */}
          {isAdmin && results.users.length > 0 && (
            <>
              <SectionHeader label="Users" />
              {results.users.map((u) => {
                const href = `/admin/users/${u.id}`
                const flatIdx = flatItems.findIndex((f) => f.href === href && f._section === 'users')
                return (
                  <ResultItem
                    key={u.id}
                    label={`${u.full_name ?? u.email} (${u.email})`}
                    icon={UserGroupIcon}
                    isActive={activeIndex === flatIdx}
                    onClick={() => selectItem({ label: u.full_name ?? u.email, href })}
                  />
                )
              })}
            </>
          )}

          {/* Organization results (admin only) */}
          {isAdmin && results.orgs.length > 0 && (
            <>
              <SectionHeader label="Organizations" />
              {results.orgs.map((org) => {
                const href = `/admin/organizations/${org.id}`
                const flatIdx = flatItems.findIndex((f) => f.href === href && f._section === 'orgs')
                return (
                  <ResultItem
                    key={org.id}
                    label={`${org.name} [${org.code}]`}
                    icon={BuildingOffice2Icon}
                    isActive={activeIndex === flatIdx}
                    onClick={() => selectItem({ label: org.name, href })}
                  />
                )
              })}
            </>
          )}

          {/* Item results */}
          {results.items.length > 0 && (
            <>
              <SectionHeader label="Items" />
              {results.items.map((item) => {
                const href = `/admin/items/${item.id}`
                const flatIdx = flatItems.findIndex((f) => f.href === href && f._section === 'items')
                return (
                  <ResultItem
                    key={item.id}
                    label={`[${item.code}] ${item.name}`}
                    icon={CubeIcon}
                    isActive={activeIndex === flatIdx}
                    onClick={() => selectItem({ label: item.name, href })}
                  />
                )
              })}
            </>
          )}

          {/* Empty state */}
          {showEmpty && (
            <div className="flex flex-col items-center justify-center py-12 text-center px-4">
              <MagnifyingGlassIcon className="w-8 h-8 text-muted-foreground mb-3" />
              <p className="text-sm font-medium text-foreground">No results for &ldquo;{query}&rdquo;</p>
              <p className="text-xs text-muted-foreground mt-1">Try different keywords</p>
            </div>
          )}

          {/* Placeholder when nothing queried and no history */}
          {!query.trim() && !showHistory && (
            <div className="flex flex-col items-center justify-center py-10 text-center px-4">
              <p className="text-sm text-muted-foreground">Start typing to search...</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-border bg-muted/30">
          <span className="text-[11px] text-muted-foreground">
            <kbd className="font-mono">↑↓</kbd> navigate
          </span>
          <span className="text-[11px] text-muted-foreground">
            <kbd className="font-mono">↵</kbd> select
          </span>
          <span className="text-[11px] text-muted-foreground">
            <kbd className="font-mono">Esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Helper: build flat navigable list ────────────────────────────────────────

function buildFlatItems(query, results, history, isAdmin) {
  const items = []

  if (!query.trim()) {
    // Show history items
    history.forEach((h) => items.push({ ...h, _section: 'history' }))
    return items
  }

  results.navigation.forEach((n) =>
    items.push({ label: n.label, href: n.href, _section: 'navigation' }),
  )
  results.tickets.forEach((t) =>
    items.push({ label: `#${t.id} - ${t.subject}`, href: `/tickets/${t.id}`, _section: 'tickets' }),
  )
  if (isAdmin) {
    results.users.forEach((u) =>
      items.push({ label: u.full_name ?? u.email, href: `/admin/users/${u.id}`, _section: 'users' }),
    )
    results.orgs.forEach((o) =>
      items.push({ label: o.name, href: `/admin/organizations/${o.id}`, _section: 'orgs' }),
    )
  }
  results.items.forEach((i) =>
    items.push({ label: i.name, href: `/admin/items/${i.id}`, _section: 'items' }),
  )

  return items
}
