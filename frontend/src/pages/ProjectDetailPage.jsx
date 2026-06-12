import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  ArchiveBoxIcon,
  CalendarDaysIcon,
  CheckCircleIcon,
  ClockIcon,
  DocumentArrowUpIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  FolderIcon,
  HomeIcon,
  PencilSquareIcon,
  PlusIcon,
  XMarkIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import { Spinner, PageShell } from '@/components/ui'
import { useRole } from '@/hooks/useRole'
import {
  cancelProject,
  cancelProjectTask,
  createProjectTask,
  downloadProjectDocument,
  getProject,
  listProjectDocuments,
  listProjectTasks,
  updateProjectTask,
  updateProjectTaskStatus,
  uploadProjectDocument,
} from '@/api/projects'
import { listUsers } from '@/api/users'
import { StatusBadge } from './ProjectsPage'
import { formatDate, formatDateTime } from '@/lib/utils'

const TASK_TYPES = [
  ['keyword_research', 'Keyword research'],
  ['technical_audit', 'Technical audit'],
  ['on_page', 'On-page'],
  ['content', 'Content'],
  ['backlink', 'Backlink'],
  ['report', 'Report'],
  ['design', 'Design'],
  ['development', 'Development'],
  ['deployment', 'Deployment'],
  ['support', 'Support'],
  ['other', 'Other'],
]

const TASK_STATUSES = ['open', 'working', 'review', 'completed', 'cancelled']

const PRIORITY_CLASSES = {
  low: 'bg-slate-100 text-slate-600',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
}

const fmtDate = (value) => value ? formatDate(value) : 'Not set'
const fmtDateTime = formatDateTime
const fmtSize = (bytes = 0) => {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`
  return `${bytes} B`
}

function isPastDeadline(value, status) {
  if (!value || ['completed', 'cancelled'].includes(status)) return false
  const deadline = new Date(value)
  deadline.setHours(23, 59, 59, 999)
  return deadline < new Date()
}

function TaskStatusBadge({ status }) {
  const classes = {
    open: 'bg-slate-100 text-slate-600',
    working: 'bg-amber-100 text-amber-700',
    review: 'bg-cyan-100 text-cyan-700',
    completed: 'bg-slate-100 text-slate-700',
    cancelled: 'bg-slate-100 text-slate-400 line-through',
  }
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${classes[status] ?? classes.open}`}>{status}</span>
}

function WorkspaceCard({ title, icon: Icon, children, action, className = '' }) {
  return (
    <section className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-4 w-4 text-slate-500" aria-hidden="true" />}
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function EmptyPanel({ children }) {
  return <p className="px-5 py-6 text-sm text-slate-500">{children}</p>
}

function StatCard({ icon: Icon, label, value, tone = 'slate' }) {
  const tones = {
    slate: 'bg-white text-slate-700 border-slate-200',
    cyan: 'bg-cyan-50 text-cyan-700 border-cyan-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
    orange: 'bg-orange-50 text-orange-700 border-orange-100',
    red: 'bg-red-50 text-red-700 border-red-100',
  }
  return (
    <div className={`rounded-2xl border p-4 shadow-sm ${tones[tone] ?? tones.slate}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
        <span className="rounded-xl bg-white/70 p-2">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}

function TaskCreateForm({ onCreate }) {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({
    title: '',
    task_type: 'other',
    priority: 'medium',
    status: 'open',
    assignee_id: '',
    due_date: '',
    is_client_visible: false,
    internal_note: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listUsers({ per_page: 100 }).then(data => setUsers(data.items ?? data ?? [])).catch(() => setUsers([]))
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.title.trim()) {
      setError('Task title is required')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onCreate({
        ...form,
        assignee_id: form.assignee_id ? Number(form.assignee_id) : null,
        due_date: form.due_date || null,
        internal_note: form.internal_note || null,
      })
      setForm({ title: '', task_type: 'other', priority: 'medium', status: 'open', assignee_id: '', due_date: '', is_client_visible: false, internal_note: '' })
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to create task')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} className="border border-border rounded-lg p-4 bg-card space-y-3">
      <div className="flex items-center gap-2">
        <PlusIcon className="w-4 h-4 text-primary" aria-hidden="true" />
        <h2 className="font-semibold text-sm text-foreground">Add Task</h2>
      </div>
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1">{error}</p>}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="Task title" className="md:col-span-2 px-3 py-2 border border-input rounded-lg bg-background text-sm" />
        <select value={form.task_type} onChange={e => setForm(f => ({ ...f, task_type: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          {TASK_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
        <select value={form.assignee_id} onChange={e => setForm(f => ({ ...f, assignee_id: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          <option value="">Unassigned</option>
          {users.map(user => <option key={user.id} value={user.id}>{user.full_name || user.email}</option>)}
        </select>
        <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className="px-3 py-2 border border-input rounded-lg bg-background text-sm">
          {TASK_STATUSES.map(status => <option key={status} value={status}>{status}</option>)}
        </select>
        <label className="space-y-1">
          <span className="text-xs font-medium text-muted-foreground">Deadline</span>
          <input
            type="date"
            value={form.due_date}
            onChange={e => setForm(f => ({ ...f, due_date: e.target.value }))}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-sm"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input type="checkbox" checked={form.is_client_visible} onChange={e => setForm(f => ({ ...f, is_client_visible: e.target.checked }))} />
          Client visible
        </label>
      </div>
      <textarea value={form.internal_note} onChange={e => setForm(f => ({ ...f, internal_note: e.target.value }))} placeholder="Internal note" className="w-full px-3 py-2 border border-input rounded-lg bg-background text-sm min-h-20" />
      <button disabled={saving} className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50">
        {saving ? 'Adding...' : 'Add Task'}
      </button>
    </form>
  )
}

function TeamMembers({ project, tasks }) {
  const members = useMemo(() => {
    const seen = new Map()
    if (project.project_manager_id || project.project_manager_name) {
      seen.set(`manager-${project.project_manager_id ?? project.project_manager_name}`, {
        id: project.project_manager_id,
        name: project.project_manager_name || 'Project manager',
        role: 'Project manager',
      })
    }
    tasks.forEach((task) => {
      if (!task.assignee_id && !task.assignee_name && !task.assignee_email) return
      const key = `assignee-${task.assignee_id ?? task.assignee_email ?? task.assignee_name}`
      const current = seen.get(key)
      seen.set(key, {
        id: task.assignee_id,
        name: task.assignee_name || task.assignee_email || `Staff #${task.assignee_id}`,
        email: task.assignee_email,
        role: current?.role === 'Project manager' ? 'Project manager, Assignee' : 'Assignee',
        taskCount: (current?.taskCount ?? 0) + 1,
      })
    })
    return Array.from(seen.values())
  }, [project, tasks])

  return (
    <WorkspaceCard title="Team Members" icon={UserGroupIcon}>
      {members.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-500">No team members assigned yet.</p>
      ) : (
        <div className="max-h-44 overflow-y-auto divide-y divide-slate-100">
          {members.slice(0, 5).map((member) => (
            <div key={`${member.role}-${member.id ?? member.name}`} className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">{member.name}</p>
                {member.email && <p className="text-xs text-slate-500 truncate">{member.email}</p>}
              </div>
              <div className="text-right shrink-0">
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">{member.role}</span>
                {member.taskCount > 0 && <p className="mt-1 text-xs text-slate-500">{member.taskCount} task{member.taskCount === 1 ? '' : 's'}</p>}
              </div>
            </div>
          ))}
          {members.length > 5 && (
            <p className="px-4 py-2 text-xs text-slate-500">+{members.length - 5} more member{members.length - 5 === 1 ? '' : 's'}</p>
          )}
        </div>
      )}
    </WorkspaceCard>
  )
}

function DocumentsPanel({ projectId, documents, loading, error, canUpload, onUpload, onDownload }) {
  const fileInputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [isClientVisible, setIsClientVisible] = useState(false)

  const handleFiles = async (files) => {
    if (!files.length) return
    setUploading(true)
    setUploadError('')
    try {
      await onUpload(files[0], isClientVisible)
    } catch (err) {
      setUploadError(err?.response?.data?.detail ?? err?.message ?? 'Document upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <section className="border border-border rounded-lg bg-card">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <DocumentTextIcon className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
          <h2 className="font-semibold text-sm text-foreground">Documents</h2>
        </div>
        {canUpload && (
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={isClientVisible}
                onChange={(e) => setIsClientVisible(e.target.checked)}
              />
              Client visible
            </label>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              accept="image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv"
              onChange={(e) => handleFiles(Array.from(e.target.files ?? []))}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-input rounded-lg text-xs font-medium hover:bg-muted disabled:opacity-50"
            >
              {uploading ? <Spinner className="w-3.5 h-3.5" /> : <DocumentArrowUpIcon className="w-3.5 h-3.5" aria-hidden="true" />}
              Upload
            </button>
          </div>
        )}
      </div>
      {(error || uploadError) && <p className="m-4 text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1">{uploadError || error}</p>}
      {loading ? (
        <div className="p-4 flex items-center gap-2 text-sm text-muted-foreground"><Spinner className="w-4 h-4" /> Loading documents</div>
      ) : documents.length === 0 ? (
        <p className="p-4 text-sm text-muted-foreground">No project documents uploaded yet.</p>
      ) : (
        <div className="divide-y divide-border">
          {documents.map((doc) => (
            <div key={doc.id} className="p-4 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{doc.file_name}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {fmtSize(doc.file_size)} · {doc.mime_type} · {fmtDateTime(doc.created_at)}
                </p>
                {canUpload && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {doc.is_client_visible ? 'Client visible' : 'Internal document'}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => onDownload(projectId, doc)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-input rounded-lg text-xs font-medium hover:bg-muted"
              >
                <ArrowDownTrayIcon className="w-3.5 h-3.5" aria-hidden="true" />
                Download
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function NotesPanel({ tasks, isCustomer }) {
  const notes = isCustomer
    ? []
    : tasks
      .filter((task) => task.internal_note)
      .map((task) => ({ id: task.id, title: task.title, note: task.internal_note }))

  return (
    <WorkspaceCard title="Notes" icon={DocumentTextIcon}>
      {notes.length === 0 ? (
        <EmptyPanel>{isCustomer ? 'No customer-visible notes yet.' : 'No internal notes yet.'}</EmptyPanel>
      ) : (
        <div className="divide-y divide-slate-100">
          {notes.map((item) => (
            <div key={item.id} className="px-5 py-4">
              <p className="text-xs font-semibold text-slate-500">{item.title}</p>
              <p className="mt-1 text-sm text-slate-700 whitespace-pre-wrap">{item.note}</p>
            </div>
          ))}
        </div>
      )}
    </WorkspaceCard>
  )
}

function ActivityPanel({ project, tasks }) {
  const activity = useMemo(() => {
    const rows = []
    if (project?.created_at) rows.push({ id: 'project-created', label: 'Project created', at: project.created_at })
    if (project?.updated_at && project.updated_at !== project.created_at) {
      rows.push({ id: 'project-updated', label: 'Project updated', at: project.updated_at })
    }
    tasks.forEach((task) => {
      if (task.created_at) rows.push({ id: `task-${task.id}-created`, label: `Task created: ${task.title}`, at: task.created_at })
      if (task.completed_at) rows.push({ id: `task-${task.id}-completed`, label: `Task completed: ${task.title}`, at: task.completed_at })
    })
    return rows
      .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
      .slice(0, 6)
  }, [project, tasks])

  return (
    <WorkspaceCard title="Activity" icon={ClockIcon}>
      {activity.length === 0 ? (
        <EmptyPanel>No project activity yet.</EmptyPanel>
      ) : (
        <div className="divide-y divide-slate-100">
          {activity.map((item) => (
            <div key={item.id} className="flex gap-3 px-5 py-4">
              <span className="mt-1.5 h-2 w-2 rounded-full bg-amber-400" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{item.label}</p>
                <p className="mt-0.5 text-xs text-slate-500">{fmtDateTime(item.at)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </WorkspaceCard>
  )
}

function TaskEditRow({ task, onCancel, onSave }) {
  const [form, setForm] = useState({
    title: task.title ?? '',
    description: task.description ?? '',
    priority: task.priority ?? 'medium',
    due_date: task.due_date ?? '',
    is_client_visible: Boolean(task.is_client_visible),
    internal_note: task.internal_note ?? '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    if (!form.title.trim()) {
      setError('Task title is required')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave({
        ...form,
        description: form.description || null,
        due_date: form.due_date || null,
        internal_note: form.internal_note || null,
      })
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to update task')
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr>
      <td colSpan={8} className="bg-slate-50 px-4 py-4">
        <form onSubmit={submit} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="lg:col-span-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="Task title"
            />
            <select
              value={form.priority}
              onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
            <label className="space-y-1">
              <span className="text-xs font-medium text-slate-500">Deadline</span>
              <input
                type="date"
                value={form.due_date || ''}
                onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </label>
          </div>
          <textarea
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            className="min-h-16 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Short task description"
          />
          <textarea
            value={form.internal_note}
            onChange={(e) => setForm((f) => ({ ...f, internal_note: e.target.value }))}
            className="min-h-16 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Internal note"
          />
          <div className="flex items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.is_client_visible}
                onChange={(e) => setForm((f) => ({ ...f, is_client_visible: e.target.checked }))}
              />
              Client visible
            </label>
            <div className="flex gap-2">
              <button type="button" onClick={onCancel} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">
                Cancel
              </button>
              <button disabled={saving} className="rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50">
                {saving ? 'Saving...' : 'Save Task'}
              </button>
            </div>
          </div>
        </form>
      </td>
    </tr>
  )
}

export default function ProjectDetailPage() {
  const { id } = useParams()
  const { isCustomer } = useRole()
  const taskFormRef = useRef(null)
  const [project, setProject] = useState(null)
  const [tasks, setTasks] = useState([])
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [error, setError] = useState('')
  const [documentsError, setDocumentsError] = useState('')
  const [updatingTask, setUpdatingTask] = useState(null)
  const [editingTaskId, setEditingTaskId] = useState(null)
  const [taskActionId, setTaskActionId] = useState(null)

  const loadDocuments = useCallback(async () => {
    setDocumentsLoading(true)
    setDocumentsError('')
    try {
      setDocuments(await listProjectDocuments(id))
    } catch (err) {
      setDocumentsError(err?.response?.data?.detail ?? err?.message ?? 'Failed to load documents')
    } finally {
      setDocumentsLoading(false)
    }
  }, [id])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [projectData, taskData, documentData] = await Promise.all([
        getProject(id),
        listProjectTasks(id),
        listProjectDocuments(id).catch(() => []),
      ])
      setProject(projectData)
      setTasks(taskData)
      setDocuments(documentData)
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to load project')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const stats = useMemo(() => {
    const total = tasks.length
    const completed = tasks.filter(task => task.status === 'completed').length
    const inProgress = tasks.filter(task => ['working', 'review'].includes(task.status)).length
    const overdue = tasks.filter((task) => {
      if (!task.due_date || ['completed', 'cancelled'].includes(task.status)) return false
      const due = new Date(task.due_date)
      due.setHours(23, 59, 59, 999)
      return due < new Date()
    }).length
    let daysRemaining = '—'
    if (project?.due_date) {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const due = new Date(project.due_date)
      due.setHours(0, 0, 0, 0)
      daysRemaining = Math.ceil((due.getTime() - today.getTime()) / 86400000)
    }
    return { total, completed, inProgress, overdue, daysRemaining }
  }, [project?.due_date, tasks])

  const addTask = async (payload) => {
    await createProjectTask(id, payload)
    await load()
  }

  const changeStatus = async (taskId, status) => {
    setUpdatingTask(taskId)
    try {
      await updateProjectTaskStatus(taskId, status)
      await load()
    } finally {
      setUpdatingTask(null)
    }
  }

  const saveTask = async (taskId, payload) => {
    await updateProjectTask(taskId, payload)
    setEditingTaskId(null)
    await load()
  }

  const cancelTask = async (taskId) => {
    setTaskActionId(taskId)
    try {
      await cancelProjectTask(taskId)
      await load()
    } finally {
      setTaskActionId(null)
    }
  }

  const cancel = async () => {
    await cancelProject(id)
    await load()
  }

  const uploadDocument = async (file, isClientVisible) => {
    await uploadProjectDocument(id, file, isClientVisible)
    await loadDocuments()
  }

  if (loading) return (
    <PageShell>
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-28 animate-pulse rounded-2xl bg-slate-200" />)}
        </div>
        <div className="h-80 animate-pulse rounded-2xl bg-slate-200" />
      </div>
    </PageShell>
  )
  if (error) return (
    <PageShell>
      <div className="rounded-2xl border border-red-100 bg-red-50 p-5 text-sm text-red-700">
        <p className="font-semibold">Project could not be loaded.</p>
        <p className="mt-1">{error}</p>
        <button onClick={load} className="mt-4 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700">Retry</button>
      </div>
    </PageShell>
  )
  if (!project) return null
  const projectOverdue = isPastDeadline(project.due_date, project.status)

  return (
    <PageShell>
      <div className="space-y-5">
        <nav className="flex items-center gap-2 text-sm text-slate-500">
          <HomeIcon className="h-4 w-4" aria-hidden="true" />
          <span>Home</span>
          <span>/</span>
          <Link to="/projects" className="hover:text-slate-900">SEO Projects</Link>
          <span>/</span>
          <span className="truncate text-slate-900">{project.name}</span>
        </nav>

        <header className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <Link to="/projects" className="mb-3 inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900">
                <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
                Back to Projects
              </Link>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
                <StatusBadge status={project.status} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-slate-500">
                {!isCustomer && project.org_name && <span>{project.org_name}</span>}
                <span className="capitalize">{project.project_type}</span>
                <span className={projectOverdue ? 'font-medium text-red-700' : ''}>
                  Deadline: {fmtDate(project.due_date)}
                </span>
                {projectOverdue && <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">Overdue</span>}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {!isCustomer && (
                <button
                  onClick={() => taskFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                  className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-600"
                >
                  <PlusIcon className="h-4 w-4" aria-hidden="true" />
                  Add Task
                </button>
              )}
              {!isCustomer && project.status !== 'cancelled' && (
                <button onClick={cancel} className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50">
                  <ArchiveBoxIcon className="h-4 w-4" aria-hidden="true" />
                  Archive Project
                </button>
              )}
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          <StatCard icon={FolderIcon} label="Total Tasks" value={stats.total} tone="amber" />
          <StatCard icon={CheckCircleIcon} label="Completed" value={stats.completed} tone="cyan" />
          <StatCard icon={ClockIcon} label="In Progress" value={stats.inProgress} tone="orange" />
          <StatCard
            icon={ExclamationTriangleIcon}
            label={stats.overdue > 0 ? 'Overdue Tasks' : 'Days Until Deadline'}
            value={stats.overdue > 0 ? stats.overdue : stats.daysRemaining}
            tone={stats.overdue > 0 || Number(stats.daysRemaining) <= 7 ? 'red' : 'slate'}
          />
        </div>

        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_340px]">
          <main className="space-y-5 min-w-0">
          <div className={`grid grid-cols-1 gap-5 ${!isCustomer ? 'xl:grid-cols-2' : ''}`}>
            <WorkspaceCard title="Progress" icon={CheckCircleIcon}>
              <div className="px-5 py-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <span className="text-3xl font-bold text-slate-900">{Math.round(Number(project.progress_percent ?? 0))}%</span>
                    <p className="mt-1 text-xs text-slate-500">Completed active tasks</p>
                  </div>
                  <StatusBadge status={project.status} />
                </div>
                <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-amber-500" style={{ width: `${Math.max(0, Math.min(100, Number(project.progress_percent ?? 0)))}%` }} />
                </div>
              </div>
            </WorkspaceCard>

            {!isCustomer && <TeamMembers project={project} tasks={tasks} />}
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
            <WorkspaceCard title="About Project" icon={FolderIcon}>
              <div className="px-5 py-5">
                <p className="text-sm leading-6 text-slate-600 whitespace-pre-wrap">{project.description || 'No project description has been added yet.'}</p>
                <dl className="mt-5 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                  {!isCustomer && project.org_name && (
                    <div className="rounded-lg bg-muted/30 px-3 py-2">
                      <dt className="text-xs text-muted-foreground">Organisation</dt>
                      <dd className="font-medium text-foreground truncate">{project.org_name}</dd>
                    </div>
                  )}
                  <div className="rounded-lg bg-muted/30 px-3 py-2">
                    <dt className="text-xs text-muted-foreground">Start date</dt>
                    <dd className="font-medium text-foreground">{fmtDate(project.start_date)}</dd>
                  </div>
                  <div className={`rounded-lg px-3 py-2 ${projectOverdue ? 'border border-red-100 bg-red-50' : 'bg-muted/30'}`}>
                    <dt className="text-xs text-muted-foreground">Deadline</dt>
                    <dd className={`font-medium ${projectOverdue ? 'text-red-700' : 'text-foreground'}`}>
                      {fmtDate(project.due_date)}
                      {projectOverdue && <span className="ml-2 text-xs font-semibold">Overdue</span>}
                    </dd>
                  </div>
                  {!isCustomer && project.project_manager_name && (
                    <div className="rounded-lg bg-muted/30 px-3 py-2">
                      <dt className="text-xs text-muted-foreground">Project manager</dt>
                      <dd className="font-medium text-foreground truncate">{project.project_manager_name}</dd>
                    </div>
                  )}
                  {!isCustomer && project.service_id && (
                    <div className="rounded-lg bg-muted/30 px-3 py-2">
                      <dt className="text-xs text-muted-foreground">Service</dt>
                      <dd className="font-medium text-foreground">#{project.service_id}</dd>
                    </div>
                  )}
                  {!isCustomer && project.subscription_id && (
                    <div className="rounded-lg bg-muted/30 px-3 py-2">
                      <dt className="text-xs text-muted-foreground">Subscription</dt>
                      <dd className="font-medium text-foreground">#{project.subscription_id}</dd>
                    </div>
                  )}
                </dl>
              </div>
            </WorkspaceCard>

            <DocumentsPanel
              projectId={id}
              documents={documents}
              loading={documentsLoading}
              error={documentsError}
              canUpload={!isCustomer}
              onUpload={uploadDocument}
              onDownload={downloadProjectDocument}
            />
          </div>

          {!isCustomer && <div ref={taskFormRef}><TaskCreateForm onCreate={addTask} /></div>}

          <WorkspaceCard title="Task List" icon={CheckCircleIcon} action={<span className="text-xs text-slate-500">{tasks.length} shown</span>}>
            {tasks.length === 0 ? (
              <EmptyPanel>{isCustomer ? 'No customer-visible tasks are available yet.' : 'No tasks have been created yet.'}</EmptyPanel>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-slate-100 bg-slate-50">
                    <tr>
                      <th className="w-10 px-4 py-3" />
                      <th className="text-left px-4 py-3 font-medium text-slate-500">Task</th>
                      <th className="text-left px-4 py-3 font-medium text-slate-500">Assignee</th>
                      <th className="text-left px-4 py-3 font-medium text-slate-500">Priority</th>
                      <th className="text-left px-4 py-3 font-medium text-slate-500">Status</th>
                      {!isCustomer && <th className="text-left px-4 py-3 font-medium text-slate-500">Client</th>}
                      <th className="text-left px-4 py-3 font-medium text-slate-500">Deadline</th>
                      {!isCustomer && <th className="text-left px-4 py-3 font-medium text-slate-500">Actions</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {tasks.map(task => (
                      <Fragment key={task.id}>
                      <tr className="hover:bg-slate-50/70">
                        <td className="px-4 py-3">
                          <span className={`flex h-5 w-5 items-center justify-center rounded-full border ${task.status === 'completed' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-300 text-transparent'}`}>
                            <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
                          </span>
                        </td>
                        <td className="px-4 py-3 min-w-64">
                          <p className="font-medium text-slate-900">{task.title}</p>
                          {task.description && <p className="text-xs text-slate-500 mt-0.5">{task.description}</p>}
                          <p className="mt-1 text-xs text-slate-400">{TASK_TYPES.find(([value]) => value === task.task_type)?.[1] ?? task.task_type}</p>
                          {!isCustomer && task.internal_note && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1 mt-2">Internal: {task.internal_note}</p>}
                        </td>
                        <td className="px-4 py-3 text-slate-500">{isCustomer ? (task.assignee_name || '—') : (task.assignee_name || task.assignee_email || '—')}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${PRIORITY_CLASSES[task.priority] ?? PRIORITY_CLASSES.medium}`}>{task.priority}</span>
                        </td>
                        <td className="px-4 py-3"><TaskStatusBadge status={task.status} /></td>
                        {!isCustomer && <td className="px-4 py-3">{task.is_client_visible ? 'Visible' : 'Internal'}</td>}
                        <td className="px-4 py-3 text-slate-500">
                          <span className="inline-flex items-center gap-1">
                            <CalendarDaysIcon className="w-3.5 h-3.5" aria-hidden="true" />
                            {fmtDate(task.due_date)}
                          </span>
                        </td>
                        {!isCustomer && (
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                            <select
                              value={task.status}
                              disabled={updatingTask === task.id || task.status === 'cancelled'}
                              onChange={e => changeStatus(task.id, e.target.value)}
                              className="px-2 py-1 border border-slate-200 rounded bg-white text-xs"
                            >
                              {TASK_STATUSES.map(status => <option key={status} value={status}>{status}</option>)}
                            </select>
                            <button
                              type="button"
                              onClick={() => setEditingTaskId(task.id)}
                              className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-100"
                              title="Edit task"
                            >
                              <PencilSquareIcon className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                            <button
                              type="button"
                              onClick={() => cancelTask(task.id)}
                              disabled={taskActionId === task.id || task.status === 'cancelled'}
                              className="rounded border border-red-100 p-1.5 text-red-600 hover:bg-red-50 disabled:opacity-40"
                              title="Cancel task"
                            >
                              <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                            </div>
                          </td>
                        )}
                      </tr>
                      {!isCustomer && editingTaskId === task.id && (
                        <TaskEditRow
                          key={`${task.id}-edit`}
                          task={task}
                          onCancel={() => setEditingTaskId(null)}
                          onSave={(payload) => saveTask(task.id, payload)}
                        />
                      )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </WorkspaceCard>
          </main>

          <aside className="space-y-5">
          <NotesPanel tasks={tasks} isCustomer={isCustomer} />
          <ActivityPanel project={project} tasks={tasks} />
          </aside>
        </div>
      </div>
    </PageShell>
  )
}
