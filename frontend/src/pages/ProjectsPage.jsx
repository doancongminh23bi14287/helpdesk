import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRightIcon, CalendarDaysIcon, CheckCircleIcon, FolderIcon, MagnifyingGlassIcon, PlusIcon } from '@heroicons/react/24/outline'
import { EmptyState, MobileCardList, MobileDataCard, MobileDataRow, PageShell, PageHeader, ResponsiveTableViewport } from '@/components/ui'
import { listProjects, createProject, listProjectTasks } from '@/api/projects'
import { listOrganizations } from '@/api/organizations'
import { useRole } from '@/hooks/useRole'
import { formatDate } from '@/lib/utils'

// Theme palette: active/running → cyan, warning → amber, complete/neutral → slate.
const STATUS_CLASSES = {
  open: 'bg-slate-100 text-slate-600',
  working: 'bg-cyan-100 text-cyan-700',
  on_hold: 'bg-amber-100 text-amber-700',
  completed: 'bg-slate-100 text-slate-600',
  cancelled: 'bg-slate-100 text-slate-400 line-through',
}

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_CLASSES[status] ?? STATUS_CLASSES.open}`}>
      {(status ?? 'open').replace('_', ' ')}
    </span>
  )
}

function ProgressBar({ value }) {
  const percent = Math.max(0, Math.min(100, Number(value ?? 0)))
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-28 rounded-full bg-muted overflow-hidden">
        <div className="h-full bg-amber-500" style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">{percent.toFixed(0)}%</span>
    </div>
  )
}

const fmtDate = (value) => value ? formatDate(value) : 'Not set'

function isDueSoon(value) {
  if (!value) return false
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(value)
  due.setHours(0, 0, 0, 0)
  const days = Math.ceil((due.getTime() - today.getTime()) / 86400000)
  return days >= 0 && days <= 14
}

function isPastDeadline(value, status) {
  if (!value || ['completed', 'cancelled'].includes(status)) return false
  const deadline = new Date(value)
  deadline.setHours(23, 59, 59, 999)
  return deadline < new Date()
}

function CreateProjectPanel({ onCreated }) {
  const [orgs, setOrgs] = useState([])
  const [form, setForm] = useState({
    org_id: '',
    name: '',
    project_type: 'seo',
    visibility: 'customer_visible',
    start_date: '',
    due_date: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listOrganizations({ per_page: 100 })
      .then(data => setOrgs(data.items ?? data ?? []))
      .catch(() => setOrgs([]))
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.org_id || !form.name.trim()) {
      setError('Organization and project name are required')
      return
    }
    setSaving(true)
    setError('')
    try {
      await createProject({
        ...form,
        org_id: Number(form.org_id),
        start_date: form.start_date || null,
        due_date: form.due_date || null,
      })
      setForm({ org_id: '', name: '', project_type: 'seo', visibility: 'customer_visible', start_date: '', due_date: '' })
      await onCreated()
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to create project')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="border border-border rounded-lg p-4 bg-card space-y-3">
      <div className="flex items-center gap-2">
        <PlusIcon className="w-4 h-4 text-primary" />
        <h2 className="font-semibold text-sm text-foreground">Create SEO Project</h2>
      </div>
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1">{error}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3">
        <select value={form.org_id} onChange={e => setForm(f => ({ ...f, org_id: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          <option value="">Organization</option>
          {orgs.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}
        </select>
        <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Project name" className="xl:col-span-2 px-3 py-2 border border-input rounded-lg bg-background text-sm" />
        <select value={form.project_type} onChange={e => setForm(f => ({ ...f, project_type: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          <option value="seo">SEO</option>
          <option value="website">Website</option>
          <option value="hosting">Hosting</option>
          <option value="maintenance">Maintenance</option>
          <option value="other">Other</option>
        </select>
        <label className="space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Start date</span>
          <input
            type="date"
            value={form.start_date}
            onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-sm"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Deadline</span>
          <input
            type="date"
            value={form.due_date}
            onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-sm"
          />
        </label>
      </div>
      <div className="flex items-center justify-between gap-3">
        <select value={form.visibility} onChange={e => setForm(f => ({ ...f, visibility: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          <option value="customer_visible">Customer visible</option>
          <option value="internal">Internal</option>
        </select>
        <button disabled={saving} className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50">
          {saving ? 'Creating...' : 'Create Project'}
        </button>
      </div>
    </form>
  )
}

export { StatusBadge, ProgressBar }

export default function ProjectsPage() {
  const { isCustomer } = useRole()
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ q: '', status: '', project_type: '', due: '' })

  const params = useMemo(() => {
    const next = {}
    Object.entries(filters).forEach(([key, value]) => {
      if (key === 'due') return
      if (value) next[key] = value
    })
    return next
  }, [filters])

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listProjects(params)
      const items = data.items ?? []
      const taskResults = await Promise.allSettled(
        items.map(project => listProjectTasks(project.id)),
      )
      setProjects(items.map((project, index) => {
        const result = taskResults[index]
        const tasks = result?.status === 'fulfilled' ? result.value : []
        return {
          ...project,
          _task_total: tasks.length,
          _task_completed: tasks.filter(task => task.status === 'completed').length,
        }
      }))
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to load projects')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [params])

  const visibleProjects = useMemo(() => {
    if (filters.due !== 'soon') return projects
    return projects.filter(project => isDueSoon(project.due_date))
  }, [filters.due, projects])

  const headerActions = (
    <>
      <div className="relative">
        <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-2.5 text-muted-foreground" aria-hidden="true" />
        <input
          aria-label="Search projects"
          value={filters.q}
          onChange={e => setFilters(f => ({ ...f, q: e.target.value }))}
          placeholder="Search projects"
          className="pl-9 pr-3 py-2 border border-input rounded-lg bg-background text-sm"
        />
      </div>
      <select aria-label="Filter by status" value={filters.status} onChange={e => setFilters(f => ({ ...f, status: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
        <option value="">All status</option>
        <option value="open">Open</option>
        <option value="working">Working</option>
        <option value="on_hold">On hold</option>
        <option value="completed">Completed</option>
        <option value="cancelled">Cancelled</option>
      </select>
      <select aria-label="Filter by project type" value={filters.project_type} onChange={e => setFilters(f => ({ ...f, project_type: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
        <option value="">All types</option>
        <option value="seo">SEO</option>
        <option value="website">Website</option>
        <option value="hosting">Hosting</option>
        <option value="maintenance">Maintenance</option>
        <option value="other">Other</option>
      </select>
      <select aria-label="Filter by deadline" value={filters.due} onChange={e => setFilters(f => ({ ...f, due: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
        <option value="">All deadlines</option>
        <option value="soon">Due soon</option>
      </select>
    </>
  )

  const mobileProjectCards = (
    <MobileCardList ariaLabel="Projects">
      {visibleProjects.map((project) => (
        <MobileDataCard
          key={project.id}
          onClick={(event) => {
            if (event.target.closest('a, button')) return
            navigate('/projects/' + project.id)
          }}
          ariaLabel={'Open project ' + project.name}
          actions={(
            <Link to={'/projects/' + project.id} className="btn-secondary min-h-11 w-full">
              View details
              <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
            </Link>
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <Link to={'/projects/' + project.id} className="text-base font-semibold text-foreground">
                {project.name}
              </Link>
              <p className="mt-1 text-xs capitalize text-muted-foreground">
                {project.project_type}
                {!isCustomer && project.org_name ? ' - ' + project.org_name : ''}
              </p>
            </div>
            <StatusBadge status={project.status} />
          </div>
          <div className="mt-4"><ProgressBar value={project.progress_percent} /></div>
          <dl className="mt-3 border-t border-border pt-2">
            <MobileDataRow label="Tasks">
              <span className="inline-flex items-center gap-1">
                <CheckCircleIcon className="h-4 w-4 text-info" aria-hidden="true" />
                {(project._task_completed ?? 0) + '/' + (project._task_total ?? 0)}
              </span>
            </MobileDataRow>
            <MobileDataRow label="Start">{fmtDate(project.start_date)}</MobileDataRow>
            <MobileDataRow label="Deadline">
              <span className={isPastDeadline(project.due_date, project.status) ? 'text-danger' : isDueSoon(project.due_date) ? 'text-warning' : ''}>
                {fmtDate(project.due_date)}
              </span>
            </MobileDataRow>
          </dl>
        </MobileDataCard>
      ))}
    </MobileCardList>
  )

  return (
    <PageShell>
      <PageHeader
        title="SEO Projects"
        subtitle={isCustomer ? 'Track customer-visible SEO delivery progress.' : 'Manage SEO delivery projects and task progress.'}
        actions={headerActions}
      />

      {!isCustomer && <CreateProjectPanel onCreated={load} />}

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {error}
          <button onClick={load} className="ml-3 underline">Retry</button>
        </div>
      )}
      {loading ? (
        <div className="grid grid-cols-1 gap-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-24 skeleton-shimmer rounded-lg" />)}
        </div>
      ) : visibleProjects.length === 0 ? (
        <EmptyState icon={FolderIcon} title="No projects found" description="SEO project progress will appear here once projects are created." />
      ) : (
        <div className="border border-slate-200 rounded-2xl overflow-hidden bg-white shadow-sm">
          <ResponsiveTableViewport mobile={mobileProjectCards}>
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Project</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Type</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Status</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Progress</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Tasks</th>
                <th className="text-left px-4 py-3 font-medium text-slate-500">Deadline</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {visibleProjects.map(project => (
                <tr
                  key={project.id}
                  className="hover:bg-slate-50/70 cursor-pointer"
                  onClick={e => { if (e.target.closest('a')) return; navigate(`/projects/${project.id}`) }}
                >
                  <td className="px-4 py-3">
                    <Link to={`/projects/${project.id}`} className="font-semibold text-slate-900 hover:text-amber-700">{project.name}</Link>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {!isCustomer && project.org_name ? `${project.org_name} · ` : ''}
                      Start date: {fmtDate(project.start_date)}
                    </p>
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-500">{project.project_type}</td>
                  <td className="px-4 py-3"><StatusBadge status={project.status} /></td>
                  <td className="px-4 py-3"><ProgressBar value={project.progress_percent} /></td>
                  <td className="px-4 py-3 text-slate-600">
                    <span className="inline-flex items-center gap-1">
                      <CheckCircleIcon className="h-4 w-4 text-cyan-600" aria-hidden="true" />
                      {project._task_completed ?? 0}/{project._task_total ?? 0}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500">
                    <span className={`inline-flex items-center gap-1 ${isPastDeadline(project.due_date, project.status) ? 'text-red-700' : isDueSoon(project.due_date) ? 'text-amber-700' : ''}`}>
                      <CalendarDaysIcon className="h-4 w-4" aria-hidden="true" />
                      {fmtDate(project.due_date)}
                    </span>
                    {isPastDeadline(project.due_date, project.status) && (
                      <span className="mt-1 inline-flex rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">Overdue</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link to={`/projects/${project.id}`} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                      View
                      <ArrowRightIcon className="h-3.5 w-3.5" aria-hidden="true" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </ResponsiveTableViewport>
        </div>
      )}
    </PageShell>
  )
}
