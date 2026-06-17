import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useTickets } from '@/hooks/useTickets'
import { useServices } from '@/hooks/useServices'
import { useAuthStore } from '@/hooks/useAuth'
import { Spinner } from '@/components/ui'
import { formatDate, formatDateTime, daysUntil, formatVND, formatCurrencyVND } from '@/lib/utils'
import { getMySubscriptions, listSubscriptions } from '@/api/subscriptions'
import { listMyInvoices, listInvoices } from '@/api/invoices'
import { listUsers } from '@/api/users'
import { listOrganizations } from '@/api/organizations'
import { getTickets } from '@/api/tickets'
import { listProjects } from '@/api/projects'
import client from '@/api/client'
import {
  TicketIcon,
  CheckCircleIcon,
  ServerStackIcon,
  ExclamationTriangleIcon,
  ArrowUpRightIcon,
  PlusIcon,
  DocumentTextIcon,
  CogIcon,
  UsersIcon,
  BuildingOfficeIcon,
  ClipboardDocumentListIcon,
  CalendarDaysIcon,
} from '@heroicons/react/24/outline'
import { StatusBadge as ProjectStatusBadge, ProgressBar } from './ProjectsPage'
import { useTranslation } from '@/lib/i18n'

// Status palette mirrors the brief: active/running → cyan,
// warning/expiring → amber, danger/breached → red, neutral → slate.
const TICKET_STATUS_STYLES = {
  Open:          'bg-blue-50 text-blue-700',
  'In Progress': 'bg-amber-50 text-amber-700',
  Waiting:       'bg-purple-50 text-purple-700',
  Resolved:      'bg-green-50 text-green-700',
  Closed:        'bg-gray-100 text-gray-500',
}

const PRIORITY_STYLES = {
  Low:    'bg-gray-100 text-gray-500',
  Medium: 'bg-yellow-50 text-yellow-700',
  High:   'bg-orange-50 text-orange-700',
  Urgent: 'bg-red-50 text-red-700',
}

function StatusBadge({ label }) {
  const cls = TICKET_STATUS_STYLES[label] ?? 'bg-gray-100 text-gray-500'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
}

function PriorityBadge({ label }) {
  const cls = PRIORITY_STYLES[label] ?? 'bg-gray-100 text-gray-600'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
}

function StatCard({ icon: Icon, label, value, color, hint, loading }) {
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 flex items-start justify-between hover:border-gray-200 transition-colors">
      <div>
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">{label}</p>
        {loading ? (
          <div className="h-8 w-14 bg-gray-100 rounded animate-pulse" />
        ) : (
          <p className="text-3xl font-semibold text-gray-900">{value}</p>
        )}
        {hint && <p className="text-sm text-gray-400 mt-1">{hint}</p>}
      </div>
      <div className={`p-2 rounded-lg flex-shrink-0 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
    </div>
  )
}

function SubscriptionSummaryWidget() {
  const { user } = useAuthStore()
  const [subs, setSubs] = useState([])

  useEffect(() => {
    const fetchFn = user?.role === 'customer' ? getMySubscriptions : listSubscriptions
    fetchFn().then(data => setSubs(Array.isArray(data) ? data : [])).catch(() => {})
  }, [user])

  if (subs.length === 0) return null

  const active   = subs.filter(s => s.status === 'active').length
  const trial    = subs.filter(s => s.status === 'trial').length
  const past_due = subs.filter(s => s.status === 'past_due').length

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-800">Subscriptions</h2>
        {user?.role === 'admin' && (
          <Link to="/admin/subscriptions" className="text-xs font-medium text-gray-900 hover:text-gray-600">
            Manage →
          </Link>
        )}
      </div>
      <div className="flex items-center gap-4 text-sm">
        {active > 0 && <span><span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1.5" /><span className="font-semibold">{active}</span> active</span>}
        {trial > 0 && <span><span className="inline-block w-2 h-2 rounded-full bg-blue-500 mr-1.5" /><span className="font-semibold">{trial}</span> trial</span>}
        {past_due > 0 && <span><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1.5" /><span className="font-semibold">{past_due}</span> past due</span>}
      </div>
    </div>
  )
}

function InvoiceSummaryWidget() {
  const { user } = useAuthStore()
  const [invoices, setInvoices] = useState([])

  useEffect(() => {
    const isCustomer = user?.role === 'customer'
    const fetchFn = isCustomer ? listMyInvoices : listInvoices
    fetchFn().then(data => setInvoices(Array.isArray(data) ? data : [])).catch(() => {})
  }, [user])

  if (invoices.length === 0) return null

  const isCustomer = user?.role === 'customer'

  if (isCustomer) {
    const outstanding = invoices
      .filter(inv => inv.status === 'sent' || inv.status === 'overdue')
      .reduce((sum, inv) => sum + (inv.total ?? 0), 0)
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-800">Invoices</h2>
          <Link to="/invoices" className="text-xs font-medium text-gray-900 hover:text-gray-600">
            View all →
          </Link>
        </div>
        {outstanding === 0 ? (
          <p className="text-sm text-emerald-600 font-medium">No outstanding invoices</p>
        ) : (
          <p className="text-sm text-foreground">
            Outstanding: <span className="font-semibold text-amber-600">{formatCurrencyVND(outstanding)}</span>
          </p>
        )}
      </div>
    )
  }

  // admin/staff
  const overdueCount = invoices.filter(inv => inv.status === 'overdue').length
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-800">Invoices</h2>
        <Link to="/admin/invoices" className="text-xs font-medium text-gray-900 hover:text-gray-600">
          Manage →
        </Link>
      </div>
      <div className="flex items-center gap-4 text-sm">
        {overdueCount > 0
          ? <span><span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1.5" /><span className="font-semibold">{overdueCount}</span> overdue</span>
          : <p className="text-sm text-emerald-600 font-medium">No overdue invoices</p>
        }
      </div>
    </div>
  )
}

// ─── Helpers ────────────────────────────────────────────────────────────────
// VND formatting goes through the shared safe helper so missing/NaN totals
// render as "0 ₫" rather than the previously-visible "NaN ₫".
const fmtVND = formatVND

// ─── Admin Stats ─────────────────────────────────────────────────────────────

function AdminStats({ activeProjects = null, projectsLoading = false }) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const { t } = useTranslation()

  useEffect(() => {
    Promise.all([
      listUsers({ per_page: 1 }).catch(() => null),
      listUsers({ per_page: 1, is_active: false }).catch(() => null),
      listOrganizations({ per_page: 1 }).catch(() => null),
      getTickets({ status: 'Open', per_page: 1 }).catch(() => null),
      listInvoices({ per_page: 100 }).catch(() => null),
    ]).then(([usersRes, inactiveRes, orgsRes, ticketsRes, invoicesRes]) => {
      const totalUsers = usersRes?.total ?? '—'
      const inactiveUsers = inactiveRes?.total ?? 0
      const totalOrgs = orgsRes?.total ?? '—'
      const openTickets = ticketsRes?.total ?? '—'

      const invoiceItems = Array.isArray(invoicesRes?.items) ? invoicesRes.items : []
      const outstandingTotal = invoiceItems
        .filter((inv) => inv.status === 'sent' || inv.status === 'overdue')
        // Coerce per-line totals — strings or null from the API would have
        // turned the sum into NaN under the previous + operator.
        .reduce((sum, inv) => {
          const n = Number(inv?.total)
          return sum + (Number.isFinite(n) ? n : 0)
        }, 0)

      setStats({ totalUsers, inactiveUsers, totalOrgs, openTickets, outstandingTotal })
      setLoading(false)
    })
  }, [])

  const skeletonCls = 'h-8 w-16 bg-slate-100 rounded animate-pulse mt-1'

  // Each card keeps the same white surface and subtle border but is
  // differentiated by three layers: the icon-chip colour, a thin coloured
  // ring inside the chip, and an optional value/hint accent. This avoids
  // the "all four look identical" problem without resorting to full
  // colour-tinted card backgrounds.
  const AdminMetricCard = ({ icon: Icon, label, value, hint, chipCls }) => (
    <div className="bg-white rounded-xl border border-gray-100 p-5 flex items-start justify-between hover:border-gray-200 transition-colors">
      <div>
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">{label}</p>
        {loading ? (
          <div className={skeletonCls} />
        ) : (
          <p className="text-3xl font-semibold text-gray-900">{value}</p>
        )}
        <p className="text-sm text-gray-400 mt-1">{hint}</p>
      </div>
      <div className={`p-2 rounded-lg flex-shrink-0 ${chipCls}`}>
        <Icon className="w-5 h-5" aria-hidden="true" />
      </div>
    </div>
  )

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
      <AdminMetricCard
        icon={UsersIcon}
        label={t('dashboard.metric.users')}
        value={stats?.totalUsers ?? '—'}
        hint={loading ? t('dashboard.metric.inactiveSuffix') : `${stats.inactiveUsers} ${t('dashboard.metric.inactiveSuffix')}`}
        chipCls="bg-blue-50 text-blue-500"
      />
      <AdminMetricCard
        icon={BuildingOfficeIcon}
        label={t('dashboard.metric.organizations')}
        value={stats?.totalOrgs ?? '—'}
        hint={t('dashboard.metric.registered')}
        chipCls="bg-purple-50 text-purple-500"
      />
      <AdminMetricCard
        icon={TicketIcon}
        label={t('dashboard.metric.openTickets')}
        value={stats?.openTickets ?? '—'}
        hint={t('dashboard.metric.awaiting')}
        chipCls="bg-blue-50 text-blue-500"
      />
      <AdminMetricCard
        icon={DocumentTextIcon}
        label={t('dashboard.metric.outstanding')}
        value={fmtVND(stats?.outstandingTotal)}
        hint={t('dashboard.metric.outstandingHint')}
        chipCls="bg-amber-50 text-amber-600"
      />
      {/* 5th card: Active SEO Projects — pulled up from secondary grid */}
      <AdminMetricCard
        icon={ClipboardDocumentListIcon}
        label={t('dashboard.metric.activeSeoProjects')}
        value={projectsLoading ? '—' : (activeProjects ?? 0)}
        hint="in progress"
        chipCls="bg-amber-50 text-amber-600"
      />
    </div>
  )
}

// ─── Admin Quick Actions ──────────────────────────────────────────────────────
// All four buttons share the same h-10 / rounded-lg / font-semibold frame.
// The two primaries are fully filled (amber, orange). The two outlined
// secondaries get an explicit slate-300 border, deliberate icon colour, and
// a personality-revealing hover (slate-400 for Invoices, sky-300 for Setup
// Wizard) so they no longer read as "default white".

function AdminQuickActions() {
  const actions = [
    { label: 'Organizations', icon: BuildingOfficeIcon, href: '/admin/organizations' },
    { label: 'Users',         icon: UsersIcon,          href: '/admin/users' },
    { label: 'Invoices',      icon: DocumentTextIcon,   href: '/admin/invoices' },
    { label: 'Setup',         icon: CogIcon,            href: '/admin/setup' },
  ]
  return (
    <div className="flex flex-wrap gap-2 mb-6">
      {actions.map(({ label, icon: Icon, href }) => (
        <Link
          key={label}
          to={href}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200
                     bg-white text-sm text-gray-600 hover:bg-gray-50 hover:border-gray-300
                     transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
        >
          <Icon className="w-4 h-4" aria-hidden="true" />
          {label}
        </Link>
      ))}
    </div>
  )
}

// ─── Relative time helper ─────────────────────────────────────────────────────

function getRelativeTime(isoStr) {
  const ts = new Date(isoStr).getTime()
  if (isNaN(ts)) return ''
  const diff = Date.now() - ts
  if (diff < 0) return 'just now'
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ─── Admin Health Panel ───────────────────────────────────────────────────────

function AdminHealthPanel() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    client.get('/admin/health', { signal: controller.signal })
      .then(res => { if (!controller.signal.aborted) setHealth(res.data) })
      .catch(err => { if (!controller.signal.aborted) setHealth(null) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  const allClear =
    health &&
    (health.overdue_invoices ?? 0) === 0 &&
    (health.sla_breached_tickets ?? 0) === 0 &&
    health.celery_workers === 'running'

  return (
    <div className="flex flex-wrap items-center gap-6 px-5 py-3 bg-white rounded-xl border border-gray-100 text-sm overflow-x-auto">
      {loading ? (
        <>
          {[0, 1, 2].map(i => (
            <div key={i} className="h-4 w-32 bg-gray-100 rounded animate-pulse" />
          ))}
        </>
      ) : !health ? (
        <span className="text-gray-400">Health data unavailable</span>
      ) : (
        <>
          <span className="text-gray-400 font-medium">System status</span>
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${(health.overdue_invoices ?? 0) > 0 ? 'bg-amber-400' : 'bg-green-400'}`} />
            <span className="text-gray-600">Overdue invoices: {health.overdue_invoices ?? 0}</span>
          </span>
          <span className="flex items-center gap-1.5">
            {(health.sla_breached_tickets ?? 0) > 0
              ? <span className="w-2 h-2 rounded-full flex-shrink-0 bg-red-400 animate-pulse" />
              : <span className="w-2 h-2 rounded-full flex-shrink-0 bg-green-400" />}
            <span className="text-gray-600">SLA breached: {health.sla_breached_tickets ?? 0}</span>
          </span>
          <span className="flex items-center gap-1.5">
            {health.celery_workers === 'running'
              ? <span className="w-2 h-2 rounded-full flex-shrink-0 bg-green-400" />
              : <span className="w-2 h-2 rounded-full flex-shrink-0 bg-amber-400" />}
            <span className="text-gray-600">Workers: {health.celery_workers === 'running' ? 'running' : 'stopped'}</span>
          </span>
        </>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { tickets, loading: ticketsLoading } = useTickets()
  const { services, loading: servicesLoading } = useServices()
  const { t } = useTranslation()

  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setProjectsLoading(true)
    listProjects({ per_page: 50 })
      .then((data) => {
        if (cancelled) return
        setProjects(Array.isArray(data?.items) ? data.items : [])
      })
      .catch(() => { if (!cancelled) setProjects([]) })
      .finally(() => { if (!cancelled) setProjectsLoading(false) })
    return () => { cancelled = true }
  }, [])

  // Flatten the services object (hosting + subscriptions) into a single array
  const allServices = [...(services.hosting ?? []), ...(services.subscriptions ?? [])]

  const openTickets     = tickets.filter((t) => t.status === 'Open').length
  const resolvedTickets = tickets.filter((t) => t.status === 'Resolved').length
  const activeServices  = allServices.filter((s) => s.status !== 'Cancelled').length

  const expiringSoon = allServices.filter((s) => {
    const days = daysUntil(s.expiry_date || s.current_invoice_end)
    return days !== null && days >= 0 && days <= 30
  }).length

  const activeProjects = projects.filter((p) => p.status !== 'completed' && p.status !== 'cancelled').length
  const projectsDueSoon = projects.filter((p) => {
    if (p.status === 'completed' || p.status === 'cancelled') return false
    const days = daysUntil(p.due_date)
    return days !== null && days >= 0 && days <= 14
  }).length

  const recentTickets = [...tickets]
    .sort((a, b) => new Date(b.modified ?? b.updated_at) - new Date(a.modified ?? a.updated_at))
    .slice(0, 8)

  const recentProjects = [...projects]
    .sort((a, b) => new Date(b.updated_at ?? 0) - new Date(a.updated_at ?? 0))
    .slice(0, 5)

  const isCustomer = user?.role === 'customer'
  const isAdmin = user?.role === 'admin'

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Page header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="page-title">{t('dashboard.title')}</h1>
        <p className="text-xs text-gray-400 mt-0.5">{t('dashboard.overview')}</p>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-6 space-y-6">
        {/* Admin-only: quick stats + actions */}
        {user?.role === 'admin' && (
          <>
            <AdminStats activeProjects={activeProjects} projectsLoading={projectsLoading} />
            <AdminQuickActions />
            <AdminHealthPanel />
          </>
        )}

        {/* Secondary stat cards — customers see their own open tickets here;
            admins skip it (AdminStats row already shows system-wide count).
            Zero-value noise cards are hidden to keep the view clean. */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Open Tickets: customer only — admin sees it in KPI row above */}
          {isCustomer && (
            <StatCard
              icon={TicketIcon}
              label={t('dashboard.metric.myOpenTickets')}
              value={openTickets}
              color="bg-blue-50 text-blue-500"
              hint="awaiting response"
              loading={ticketsLoading}
            />
          )}
          {/* Active SEO Projects: admin already sees it in the KPI row above */}
          {!isAdmin && (activeProjects > 0 || projectsLoading) && (
            <StatCard
              icon={ClipboardDocumentListIcon}
              label={t('dashboard.metric.activeSeoProjects')}
              value={activeProjects}
              color="bg-amber-50 text-amber-600"
              hint="in progress"
              loading={projectsLoading}
            />
          )}
          {/* Active Services: hide when 0 */}
          {(activeServices > 0 || servicesLoading) && (
            <StatCard
              icon={ServerStackIcon}
              label={isCustomer ? t('dashboard.metric.myActiveServices') : t('dashboard.metric.activeServices')}
              value={activeServices}
              color="bg-slate-100 text-slate-500"
              hint="running"
              loading={servicesLoading}
            />
          )}
          {/* Expiring soon: hide when 0 */}
          {expiringSoon > 0 && (
            <StatCard
              icon={ExclamationTriangleIcon}
              label={t('dashboard.metric.expiringSoon')}
              value={expiringSoon}
              color="bg-orange-50 text-orange-500"
              hint="within 30 days"
              loading={servicesLoading}
            />
          )}
          {/* Projects due soon: hide when 0 */}
          {projectsDueSoon > 0 && (
            <StatCard
              icon={CalendarDaysIcon}
              label={t('dashboard.metric.projectsDueSoon')}
              value={projectsDueSoon}
              color="bg-red-50 text-red-500"
              hint="within 14 days"
              loading={projectsLoading}
            />
          )}
          {/* Resolved: non-admin only, hide when 0 */}
          {!isAdmin && resolvedTickets > 0 && (
            <StatCard
              icon={CheckCircleIcon}
              label={t('dashboard.metric.resolvedTickets')}
              value={resolvedTickets}
              color="bg-green-50 text-green-500"
              hint="this session"
              loading={ticketsLoading}
            />
          )}
        </div>

        {/* Subscription summary */}
        <SubscriptionSummaryWidget />

        {/* Invoice summary */}
        <InvoiceSummaryWidget />

        {/* Recent Tickets */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-800">{t('dashboard.recentTickets')}</h2>
            <Link to="/tickets" className="inline-flex items-center gap-1 text-xs font-medium text-gray-900 hover:text-gray-600 transition-colors">
              {t('dashboard.viewAll')} <ArrowUpRightIcon className="w-3.5 h-3.5" />
            </Link>
          </div>
          {ticketsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner className="w-5 h-5" />
            </div>
          ) : recentTickets.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2">
              <TicketIcon className="w-8 h-8 text-gray-200" />
              <p className="text-sm text-gray-400">{t('dashboard.noTickets')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-5 py-2.5 w-32">#</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5">{t('dashboard.subjectCol')}</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5 w-28">{t('dashboard.statusCol')}</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-3 py-2.5 w-24">{t('dashboard.priorityCol')}</th>
                  <th className="text-left text-[11px] font-medium text-gray-400 uppercase tracking-wider px-5 py-2.5 w-36">{t('dashboard.updatedCol')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {recentTickets.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50 transition-colors group">
                    <td className="px-5 py-2.5">
                      <Link to={`/tickets/${t.id}`} className="block">
                        <span className="text-xs font-mono text-gray-400 group-hover:text-gray-900 transition-colors">#{t.id}</span>
                      </Link>
                    </td>
                    <td className="px-3 py-2.5">
                      <Link to={`/tickets/${t.id}`} className="block">
                        <span className="text-sm font-medium text-gray-700 group-hover:text-gray-900 transition-colors line-clamp-1">{t.subject}</span>
                      </Link>
                    </td>
                    <td className="px-3 py-2.5">
                      <Link to={`/tickets/${t.id}`} className="block">
                        <StatusBadge label={t.status} />
                      </Link>
                    </td>
                    <td className="px-3 py-2.5">
                      <Link to={`/tickets/${t.id}`} className="block">
                        <PriorityBadge label={t.priority} />
                      </Link>
                    </td>
                    <td className="px-5 py-2.5">
                      <Link to={`/tickets/${t.id}`} className="block">
                        <span className="text-xs text-gray-400">{formatDateTime(t.modified ?? t.updated_at)}</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>

        {/* Recent SEO Projects */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-800">{t('dashboard.recentSeoProjects')}</h2>
            <Link to="/projects" className="inline-flex items-center gap-1 text-xs font-medium text-gray-900 hover:text-gray-600 transition-colors">
              {t('dashboard.viewAll')} <ArrowUpRightIcon className="w-3.5 h-3.5" />
            </Link>
          </div>
          {projectsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner className="w-5 h-5" />
            </div>
          ) : recentProjects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2">
              <ClipboardDocumentListIcon className="w-8 h-8 text-gray-200" />
              <p className="text-sm text-gray-400">{t('dashboard.noProjects')}</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {recentProjects.map((p) => (
                <Link
                  key={p.id}
                  to={`/projects/${p.id}`}
                  className="flex items-center gap-4 px-5 py-3 hover:bg-gray-50 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-800 truncate">{p.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5 truncate">
                      {!isCustomer && p.org_name ? `${p.org_name} · ` : ''}
                      Start date: {p.start_date ? formatDate(p.start_date) : 'Not set'}
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    <ProjectStatusBadge status={p.status} />
                  </div>
                  <div className="hidden sm:block flex-shrink-0">
                    <ProgressBar value={p.progress_percent} />
                  </div>
                  <div className="flex-shrink-0 w-36 text-right">
                    <span className="text-xs text-gray-400">
                      Deadline: {p.due_date ? formatDate(p.due_date) : 'Not set'}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Services summary */}
        {!servicesLoading && allServices.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-800">{t('dashboard.yourServices')}</h2>
              <Link to="/services" className="inline-flex items-center gap-1 text-xs font-medium text-gray-900 hover:text-gray-600 transition-colors">
                {t('dashboard.viewAll')} <ArrowUpRightIcon className="w-3.5 h-3.5" />
              </Link>
            </div>
            <div className="divide-y divide-gray-50">
              {allServices.slice(0, 5).map((s) => {
                const days = daysUntil(s.expiry_date || s.current_invoice_end)
                const isExpiring = days !== null && days <= 30 && days >= 0
                return (
                  <div key={s.name} className="flex items-center justify-between px-5 py-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{s.domain || s.name}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{s.status}</p>
                    </div>
                    {days !== null && (
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                        isExpiring
                          ? days <= 7 ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'
                          : 'bg-gray-100 text-gray-500'
                      }`}>
                        {days <= 0 ? 'Expired' : `${days}d left`}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
