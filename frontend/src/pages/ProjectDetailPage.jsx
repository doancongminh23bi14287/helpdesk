import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowDownTrayIcon,
  ArrowLeftIcon,
  ArchiveBoxIcon,
  CalendarDaysIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClockIcon,
  DocumentArrowUpIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  FolderIcon,
  MagnifyingGlassIcon,
  PaperClipIcon,
  PencilSquareIcon,
  PhotoIcon,
  PlusIcon,
  XMarkIcon,
  UserGroupIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline'
import { Spinner, UserAvatar } from '@/components/ui'
import { StatusBadge } from '@/components/StatusBadge'
import { useRole } from '@/hooks/useRole'
import { useAuthStore } from '@/hooks/useAuth'
import { subscribeSocketEvent } from '@/hooks/useSocket'
import { useRelativeTime, parseUTC } from '@/hooks/useRelativeTime'
import {
  cancelProject,
  cancelProjectTask,
  createProjectTask,
  createTaskComment,
  downloadProjectDocument,
  getProject,
  getProjectTask,
  getProjectTickets,
  getProjectDiscussion,
  getTaskApprovals,
  listProjectDocuments,
  listProjectTasks,
  postProjectDiscussion,
  submitTaskApproval,
  updateProjectTask,
  updateProjectTaskStatus,
  uploadProjectDocument,
  addProjectMember,
  listProjectMembers,
  removeProjectMember,
} from '@/api/projects'
import { uploadAttachment, getAttachments, openOrDownloadAttachment } from '@/api/attachments'
import AttachmentList from '@/components/ui/AttachmentList'
import { listUsers } from '@/api/users'
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

// Ordered columns for the Kanban board view — all 6 real task statuses
const KANBAN_COLUMNS = [
  { key: 'open',      label: 'Open',      dot: 'bg-slate-400',  colBg: 'bg-slate-100/60',  head: 'text-slate-600' },
  { key: 'working',   label: 'Working',   dot: 'bg-amber-400',  colBg: 'bg-amber-50/60',   head: 'text-amber-700' },
  { key: 'review',    label: 'Review',    dot: 'bg-cyan-400',   colBg: 'bg-cyan-50/60',    head: 'text-cyan-700'  },
  { key: 'approved',  label: 'Approved',  dot: 'bg-green-400',  colBg: 'bg-green-50/60',   head: 'text-green-700' },
  { key: 'completed', label: 'Completed', dot: 'bg-teal-500',   colBg: 'bg-teal-50/40',    head: 'text-teal-700'  },
  { key: 'cancelled', label: 'Cancelled', dot: 'bg-slate-300',  colBg: 'bg-slate-50',      head: 'text-slate-400' },
]

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

function daysUntilDeadline(value) {
  if (!value) return null
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const due = new Date(value); due.setHours(0, 0, 0, 0)
  return Math.ceil((due.getTime() - today.getTime()) / 86400000)
}

function TaskStatusBadge({ status }) {
  const classes = {
    open: 'bg-slate-100 text-slate-600',
    working: 'bg-amber-100 text-amber-700',
    review: 'bg-cyan-100 text-cyan-700',
    approved: 'bg-green-100 text-green-700',
    completed: 'bg-slate-100 text-slate-700',
    cancelled: 'bg-slate-100 text-slate-400 line-through',
  }
  return <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${classes[status] ?? classes.open}`}>{status}</span>
}

// TODO: add drag-and-drop between columns (e.g. @dnd-kit/core) when needed
function KanbanCard({ task, onOpen }) {
  const pastDue = isPastDeadline(task.due_date, task.status)
  const typeLabel = TASK_TYPES.find(([v]) => v === task.task_type)?.[1] ?? task.task_type
  return (
    <div
      role="button"
      tabIndex={0}
      className="bg-white rounded-lg border border-slate-200 p-3 cursor-pointer hover:shadow-sm hover:border-slate-300 transition-all select-none"
      onClick={onOpen}
      onKeyDown={e => e.key === 'Enter' && onOpen()}
    >
      <p className="text-sm font-medium text-slate-900 leading-snug">{task.title}</p>
      {task.task_type && task.task_type !== 'other' && (
        <p className="text-[11px] text-slate-400 mt-0.5">{typeLabel}</p>
      )}
      <div className="flex flex-wrap items-center gap-1.5 mt-2">
        {task.priority && (
          <span className={`px-1.5 py-0.5 rounded-full text-[11px] font-medium capitalize ${PRIORITY_CLASSES[task.priority] ?? PRIORITY_CLASSES.medium}`}>
            {task.priority}
          </span>
        )}
        {task.due_date && (
          <span className={`inline-flex items-center gap-0.5 text-[11px] ${pastDue ? 'text-red-600 font-medium' : 'text-slate-400'}`}>
            <CalendarDaysIcon className="w-3 h-3" />
            {fmtDate(task.due_date)}
          </span>
        )}
      </div>
      {task.assignees?.length > 0 && (
        <div className="mt-2">
          <AssigneesPills assignees={task.assignees} />
        </div>
      )}
    </div>
  )
}

function AssigneesPills({ assignees = [] }) {
  if (!assignees.length) return <span className="text-slate-400">—</span>
  const visible = assignees.slice(0, 3)
  return (
    <div className="flex flex-wrap gap-1">
      {visible.map(a => (
        <span key={a.user_id} className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-slate-100 text-slate-700">
          {(a.full_name?.split(' ')[0]) || (a.email?.split('@')[0]) || `#${a.user_id}`}
        </span>
      ))}
      {assignees.length > 3 && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-slate-200 text-slate-500">+{assignees.length - 3}</span>
      )}
    </div>
  )
}

// ── Approval constants ─────────────────────────────────────────────────────────

const APPROVAL_ACTION_LABELS = {
  submitted_for_review: 'Submitted for review',
  approved: 'Approved',
  changes_requested: 'Changes requested',
}

const APPROVAL_ACTION_CLASSES = {
  submitted_for_review: 'bg-blue-100 text-blue-700',
  approved: 'bg-green-100 text-green-700',
  changes_requested: 'bg-orange-100 text-orange-700',
}

function RelativeTime({ dateStr, className = '' }) {
  const label = useRelativeTime(dateStr)
  const tooltip = dateStr
    ? parseUTC(dateStr).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
    : ''
  return <span className={className} title={tooltip}>{label}</span>
}

function TaskDetailModal({ taskId, isCustomer, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [commentContent, setCommentContent] = useState('')
  const [commentIsInternal, setCommentIsInternal] = useState(false)
  const [commentSubmitting, setCommentSubmitting] = useState(false)
  const [commentError, setCommentError] = useState('')

  const [approvals, setApprovals] = useState([])
  const [approvalsLoading, setApprovalsLoading] = useState(false)
  const [approvalSubmitting, setApprovalSubmitting] = useState(false)
  const [approvalError, setApprovalError] = useState('')
  const [changesComment, setChangesComment] = useState('')
  const [showChangesForm, setShowChangesForm] = useState(false)

  const fetchDetail = useCallback(async () => {
    setLoading(true)
    try {
      setDetail(await getProjectTask(taskId))
    } finally {
      setLoading(false)
    }
  }, [taskId])

  const fetchApprovals = useCallback(async () => {
    setApprovalsLoading(true)
    try {
      setApprovals(await getTaskApprovals(taskId))
    } catch {
      // 403 for invisible tasks — silently ignore
    } finally {
      setApprovalsLoading(false)
    }
  }, [taskId])

  useEffect(() => { fetchDetail() }, [fetchDetail])
  useEffect(() => { fetchApprovals() }, [fetchApprovals])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleApproval = async (action, comment = '') => {
    setApprovalSubmitting(true)
    setApprovalError('')
    try {
      await submitTaskApproval(taskId, { action, comment: comment || undefined })
      setChangesComment('')
      setShowChangesForm(false)
      await Promise.all([fetchDetail(), fetchApprovals()])
    } catch (err) {
      setApprovalError(err?.response?.data?.detail ?? 'Action failed')
    } finally {
      setApprovalSubmitting(false)
    }
  }

  const handleComment = async () => {
    if (!commentContent.trim()) return
    setCommentSubmitting(true)
    setCommentError('')
    try {
      await createTaskComment(taskId, { content: commentContent.trim(), is_internal: commentIsInternal })
      setCommentContent('')
      setCommentIsInternal(false)
      await fetchDetail()
    } catch (err) {
      setCommentError(err?.response?.data?.detail ?? 'Failed to post comment')
    } finally {
      setCommentSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start gap-3 px-6 py-4 border-b border-slate-100">
          {loading ? (
            <div className="flex items-center gap-2 flex-1"><Spinner className="w-4 h-4" /><span className="text-sm text-slate-500">Loading…</span></div>
          ) : (
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold text-slate-900">{detail?.title}</h2>
              <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                {detail && <TaskStatusBadge status={detail.status} />}
                {detail && <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${PRIORITY_CLASSES[detail.priority] ?? PRIORITY_CLASSES.medium}`}>{detail.priority}</span>}
                {detail?.due_date && <span className="text-xs text-slate-400">Due {fmtDate(detail.due_date)}</span>}
              </div>
            </div>
          )}
          <button type="button" onClick={onClose} className="flex-shrink-0 rounded p-1.5 hover:bg-slate-100 text-slate-400 transition-colors">
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>

        {!loading && detail && (
          <div className="overflow-y-auto flex-1 divide-y divide-slate-100">
            {detail.assignees?.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-2">Assignees</p>
                <div className="flex flex-wrap gap-1.5">
                  {detail.assignees.map(a => (
                    <span
                      key={a.user_id}
                      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${a.is_primary ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}
                    >
                      {a.full_name || a.email || `#${a.user_id}`}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="px-6 py-4 space-y-3">
              <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                Comments{detail.comments?.length ? ` (${detail.comments.length})` : ''}
              </p>
              {detail.comments?.length === 0 ? (
                <p className="text-sm text-slate-400">No comments yet.</p>
              ) : (
                <div className="space-y-2">
                  {detail.comments.map(c => (
                    <div key={c.id} className={`rounded-lg px-3 py-2.5 ${c.is_internal ? 'bg-amber-50 border border-amber-100' : 'bg-slate-50'}`}>
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="text-xs font-semibold text-slate-700">{c.author_name || `User #${c.author_id}`}</span>
                        <div className="flex items-center gap-1.5">
                          {c.is_internal && <span className="text-[10px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full">Internal</span>}
                          <RelativeTime dateStr={c.created_at} className="text-[10px] text-slate-400" />
                        </div>
                      </div>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap">{c.content}</p>
                    </div>
                  ))}
                </div>
              )}
              {(!isCustomer || detail.is_client_visible) && (
                <div className="mt-1 space-y-2 pt-3 border-t border-slate-100">
                  {commentError && <p className="text-xs text-red-600">{commentError}</p>}
                  <textarea
                    value={commentContent}
                    onChange={e => setCommentContent(e.target.value)}
                    placeholder="Add a comment…"
                    rows={2}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
                  />
                  <div className="flex items-center justify-between">
                    {!isCustomer && (
                      <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer select-none">
                        <input type="checkbox" checked={commentIsInternal} onChange={e => setCommentIsInternal(e.target.checked)} className="rounded" />
                        Internal only
                      </label>
                    )}
                    <button
                      type="button"
                      onClick={handleComment}
                      disabled={!commentContent.trim() || commentSubmitting}
                      className="ml-auto px-3 py-1.5 rounded-lg bg-amber-500 text-white text-xs font-semibold hover:bg-amber-600 disabled:opacity-50 transition-colors"
                    >
                      {commentSubmitting ? 'Posting…' : 'Comment'}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {detail.is_client_visible && (
              <div className="px-6 py-4 space-y-3">
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest">Approval</p>

                {approvalError && <p className="text-xs text-red-600">{approvalError}</p>}

                {!isCustomer && (detail.status === 'working' || detail.status === 'review') && (
                  <button
                    type="button"
                    onClick={() => handleApproval('submitted_for_review')}
                    disabled={approvalSubmitting}
                    className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    {approvalSubmitting ? 'Submitting…' : 'Submit for Review'}
                  </button>
                )}

                {isCustomer && detail.status === 'review' && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleApproval('approved')}
                        disabled={approvalSubmitting}
                        className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-xs font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        {approvalSubmitting ? '…' : 'Approve'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowChangesForm(v => !v)}
                        disabled={approvalSubmitting}
                        className="px-3 py-1.5 rounded-lg border border-orange-300 text-orange-700 text-xs font-semibold hover:bg-orange-50 disabled:opacity-50 transition-colors"
                      >
                        Request Changes
                      </button>
                    </div>
                    {showChangesForm && (
                      <div className="space-y-2">
                        <textarea
                          value={changesComment}
                          onChange={e => setChangesComment(e.target.value)}
                          placeholder="Describe the changes needed…"
                          rows={2}
                          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-orange-400"
                        />
                        <button
                          type="button"
                          onClick={() => handleApproval('changes_requested', changesComment)}
                          disabled={approvalSubmitting || !changesComment.trim()}
                          className="px-3 py-1.5 rounded-lg bg-orange-500 text-white text-xs font-semibold hover:bg-orange-600 disabled:opacity-50 transition-colors"
                        >
                          {approvalSubmitting ? 'Sending…' : 'Send Request'}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {approvalsLoading ? (
                  <p className="text-xs text-slate-400">Loading history…</p>
                ) : approvals.length > 0 ? (
                  <div className="space-y-2 mt-1">
                    {approvals.map(a => (
                      <div key={a.id} className="flex items-start gap-2 text-xs">
                        <span className={`flex-shrink-0 px-2 py-0.5 rounded-full font-semibold ${APPROVAL_ACTION_CLASSES[a.action] ?? 'bg-slate-100 text-slate-600'}`}>
                          {APPROVAL_ACTION_LABELS[a.action] ?? a.action}
                        </span>
                        <div className="min-w-0">
                          <span className="font-medium text-slate-700">{a.actor_name || `User #${a.actor_id}`}</span>
                          {a.comment && <p className="text-slate-500 truncate">{a.comment}</p>}
                          <span className="text-slate-400">{fmtDateTime(a.created_at)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400">No approval history yet.</p>
                )}
              </div>
            )}

            {!isCustomer && detail.activities?.length > 0 && (
              <div className="px-6 py-4">
                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-3">Activity</p>
                <div className="space-y-2">
                  {detail.activities.map(a => (
                    <div key={a.id} className="flex items-start gap-2">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                      <div>
                        <span className="text-xs text-slate-600">
                          <span className="font-medium">{a.actor_name || 'System'}</span>
                          {' '}
                          {a.action === 'status_change'
                            ? `changed status: ${a.from_value} → ${a.to_value}`
                            : a.action === 'comment_added'
                            ? 'added a comment'
                            : a.action}
                        </span>
                        {' '}
                        <span className="text-[10px] text-slate-400">{fmtDateTime(a.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
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
    assignee_ids: [],
    due_date: '',
    is_client_visible: false,
    internal_note: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listUsers({ per_page: 100 }).then(data => setUsers(data.items ?? data ?? [])).catch(() => setUsers([]))
  }, [])

  const toggleAssignee = (userId) => {
    setForm(f => ({
      ...f,
      assignee_ids: f.assignee_ids.includes(userId)
        ? f.assignee_ids.filter(id => id !== userId)
        : [...f.assignee_ids, userId],
    }))
  }

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
        assignee_ids: form.assignee_ids.length > 0 ? form.assignee_ids : null,
        due_date: form.due_date || null,
        internal_note: form.internal_note || null,
      })
      setForm({ title: '', task_type: 'other', priority: 'medium', status: 'open', assignee_ids: [], due_date: '', is_client_visible: false, internal_note: '' })
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to create task')
    } finally {
      setSaving(false)
    }
  }

  const staffUsers = users.filter(u => u.role === 'staff' || u.role === 'admin')

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
      {staffUsers.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground mb-1.5">Assignees</p>
          <div className="flex flex-wrap gap-2">
            {staffUsers.map(u => (
              <label key={u.id} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs cursor-pointer border transition-colors ${form.assignee_ids.includes(u.id) ? 'bg-primary text-primary-foreground border-primary' : 'bg-background border-input text-foreground hover:border-primary/50'}`}>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={form.assignee_ids.includes(u.id)}
                  onChange={() => toggleAssignee(u.id)}
                />
                {u.full_name || u.email}
              </label>
            ))}
          </div>
        </div>
      )}
      <textarea value={form.internal_note} onChange={e => setForm(f => ({ ...f, internal_note: e.target.value }))} placeholder="Internal note" className="w-full px-3 py-2 border border-input rounded-lg bg-background text-sm min-h-20" />
      <button disabled={saving} className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium disabled:opacity-50">
        {saving ? 'Adding...' : 'Add Task'}
      </button>
    </form>
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
    if (!form.title.trim()) { setError('Task title is required'); return }
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
            <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} className="lg:col-span-2 rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Task title" />
            <select value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
            <label className="space-y-1">
              <span className="text-xs font-medium text-slate-500">Deadline</span>
              <input type="date" value={form.due_date || ''} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" />
            </label>
          </div>
          <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} className="min-h-16 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Short task description" />
          <textarea value={form.internal_note} onChange={(e) => setForm((f) => ({ ...f, internal_note: e.target.value }))} className="min-h-16 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Internal note" />
          <div className="flex items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={form.is_client_visible} onChange={(e) => setForm((f) => ({ ...f, is_client_visible: e.target.checked }))} />
              Client visible
            </label>
            <div className="flex gap-2">
              <button type="button" onClick={onCancel} className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">Cancel</button>
              <button disabled={saving} className="rounded-lg bg-amber-500 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50">{saving ? 'Saving...' : 'Save Task'}</button>
            </div>
          </div>
        </form>
      </td>
    </tr>
  )
}

const TICKET_STATUS_BADGE = {
  'Open':        'bg-blue-50 text-blue-700',
  'In Progress': 'bg-amber-50 text-amber-700',
  'Waiting':     'bg-purple-50 text-purple-700',
  'Resolved':    'bg-green-50 text-green-700',
  'Closed':      'bg-gray-100 text-gray-500',
}

function ImageLightbox({ src, name, onClose }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" onClick={onClose}>
      <div className="relative max-w-4xl max-h-[90vh] w-full" onClick={e => e.stopPropagation()}>
        <button type="button" onClick={onClose} className="absolute -top-10 right-0 text-white/80 hover:text-white">
          <XMarkIcon className="h-6 w-6" />
        </button>
        <img src={src} alt={name} className="max-h-[85vh] w-auto max-w-full rounded-xl object-contain mx-auto block" />
        <p className="mt-2 text-center text-xs text-white/60">{name}</p>
      </div>
    </div>
  )
}

function DocumentsPanel({ projectId, documents, loading, error, canUpload, onUpload, onDownload }) {
  const fileInputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [isClientVisible, setIsClientVisible] = useState(false)
  const [lightbox, setLightbox] = useState(null)

  const handleFiles = async (files) => {
    if (!files.length) return
    setUploading(true)
    setUploadError('')
    try {
      await onUpload(files[0], isClientVisible)
    } catch (err) {
      setUploadError(err?.response?.data?.detail ?? err?.message ?? 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const imageDocs = documents.filter(d => d.mime_type?.startsWith('image/'))
  const otherDocs = documents.filter(d => !d.mime_type?.startsWith('image/'))

  return (
    <div className="px-5 py-4">
      {canUpload && (
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <input type="checkbox" checked={isClientVisible} onChange={(e) => setIsClientVisible(e.target.checked)} />
            Client visible
          </label>
          <input ref={fileInputRef} type="file" className="hidden" accept="image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv" onChange={(e) => handleFiles(Array.from(e.target.files ?? []))} />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-input rounded-lg text-xs font-medium hover:bg-muted disabled:opacity-50">
            {uploading ? <Spinner className="w-3.5 h-3.5" /> : <DocumentArrowUpIcon className="w-3.5 h-3.5" aria-hidden="true" />}
            Upload file
          </button>
        </div>
      )}

      {(error || uploadError) && (
        <p className="mb-3 text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1">{uploadError || error}</p>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner className="w-4 h-4" /> Loading…</div>
      ) : documents.length === 0 ? (
        <p className="py-4 text-sm text-muted-foreground">No documents uploaded yet.</p>
      ) : (
        <>
          {imageDocs.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
              {imageDocs.slice(0, 4).map((doc, i) => (
                <div key={doc.id} className="relative aspect-square rounded-lg overflow-hidden bg-slate-100 cursor-pointer hover:ring-2 hover:ring-amber-400 transition" onClick={() => setLightbox({ src: `/api/projects/${projectId}/documents/${doc.id}/download`, name: doc.file_name })}>
                  <img src={`/api/projects/${projectId}/documents/${doc.id}/download`} alt={doc.file_name} className="w-full h-full object-cover" />
                  {i === 3 && imageDocs.length > 4 && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center text-white text-sm font-semibold">+{imageDocs.length - 4}</div>
                  )}
                </div>
              ))}
            </div>
          )}
          {otherDocs.length > 0 && (
            <div className="divide-y divide-slate-100">
              {otherDocs.map((doc) => (
                <div key={doc.id} className="py-2.5 flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground truncate">{doc.file_name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {fmtSize(doc.file_size)} · {fmtDateTime(doc.created_at)}
                      {doc.source === 'ticket_attachment' && (
                        <span className="ml-1.5 text-violet-600">· from ticket</span>
                      )}
                    </p>
                  </div>
                  <button type="button" onClick={() => onDownload(projectId, doc)} className="inline-flex items-center gap-1 px-2 py-1 border border-input rounded text-xs font-medium hover:bg-muted flex-shrink-0">
                    <ArrowDownTrayIcon className="w-3 h-3" />
                    Download
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {lightbox && <ImageLightbox src={lightbox.src} name={lightbox.name} onClose={() => setLightbox(null)} />}
    </div>
  )
}

function DiscussionItem({ item, attachments = [] }) {
  const { user } = useAuthStore()
  const relTime = useRelativeTime(item.created_at)
  const tooltip = item.created_at
    ? parseUTC(item.created_at).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
    : ''

  const displayName = item.author_name || item.author_email?.split('@')[0] || 'Unknown'
  const initial = displayName.charAt(0).toUpperCase()
  const isRight = item.author_id != null && item.author_id === user?.id

  return (
    <div className={`px-5 pt-4 pb-1 ${item.is_internal ? 'bg-amber-50/60' : ''}`}>
      <div className={`flex gap-3 ${isRight ? 'flex-row-reverse' : ''}`}>
        <div
          className="h-8 w-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-0.5"
          style={isRight
            ? { background: '#DBEAFE', color: '#1D4ED8' }
            : item.author_role === 'customer'
              ? { background: '#EDE9FE', color: '#6D28D9' }
              : { background: '#E2E8F0', color: '#475569' }}
        >
          {initial}
        </div>
        <div className={`min-w-0 flex-1 ${isRight ? 'flex flex-col items-end' : ''}`}>
          <div className={`flex items-baseline gap-2 mb-1 flex-wrap ${isRight ? 'flex-row-reverse' : ''}`}>
            <span className="text-xs font-semibold text-slate-800" title={item.author_email || undefined}>{displayName}</span>
            <span className="text-[10px] text-slate-400" title={tooltip}>{relTime}</span>
            {item.is_internal && (
              <span className="text-[10px] font-semibold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded-full">Internal</span>
            )}
            {item.ticket_subject && (
              <Link to={`/tickets/${item.ticket_id}`} onClick={e => e.stopPropagation()} className="text-[10px] text-violet-600 bg-violet-50 px-1.5 py-0.5 rounded-full hover:underline">
                {item.ticket_subject}
              </Link>
            )}
          </div>
          <div className={`border rounded-lg px-3 py-2 text-sm leading-relaxed max-w-[85%] ${
            item.is_internal
              ? 'bg-amber-50 border-amber-100 text-amber-900'
              : isRight
                ? 'bg-blue-50 border-blue-100 text-blue-900'
                : 'bg-white border-slate-200 text-slate-700'
          }`}>
            {item.content?.trim() && item.content !== '(attachment)' && (
              <p className="whitespace-pre-wrap break-words">{item.content}</p>
            )}
            {attachments.length > 0 && <AttachmentList attachments={attachments} />}
          </div>
        </div>
      </div>
    </div>
  )
}

function DiscussionPanel({ projectId, isCustomer }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [replyContent, setReplyContent] = useState('')
  const [replyIsInternal, setReplyIsInternal] = useState(false)
  const [replySending, setReplySending] = useState(false)
  const [sendError, setSendError] = useState('')
  const [attachFiles, setAttachFiles] = useState([])
  const [discussionAttachments, setDiscussionAttachments] = useState([])
  const fileInputRef = useRef(null)
  const fetchPage = useCallback(async (p) => {
    setLoading(true)
    try {
      const data = await getProjectDiscussion(projectId, p)
      const newItems = data.items ?? []
      if (p === 1) {
        setItems(newItems)
        const ticketIds = [...new Set(newItems.map(i => i.ticket_id).filter(Boolean))]
        if (ticketIds.length > 0) {
          Promise.all(ticketIds.map(tid => getAttachments(tid).catch(() => [])))
            .then(results => setDiscussionAttachments(results.flat()))
            .catch(() => {})
        }
      } else {
        setItems(prev => [...prev, ...newItems])
      }
      setTotal(data.total ?? 0)
      setPage(p)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { fetchPage(1) }, [fetchPage])

  // H.4B: listen new_reply socket event → append to list (dedup by id)
  useEffect(() => {
    const pid = Number(projectId)
    const handler = (data) => {
      if (data.project_id !== pid) return
      setItems(prev => {
        if (prev.some(x => x.id === data.reply_id)) return prev
        const newItem = {
          id: data.reply_id,
          ticket_id: data.ticket_id,
          ticket_subject: data.ticket_subject ?? null,
          author_id: data.author_id,
          author_name: data.author_name,
          author_email: null,
          author_role: data.author_role,
          content: data.content,
          is_internal: data.is_internal,
          created_at: data.created_at,
        }
        return [...prev, newItem]
      })
      setTotal(prev => prev + 1)
    }
    return subscribeSocketEvent('new_reply', handler)
  }, [projectId])

  const handleSend = async () => {
    const hasText = replyContent.trim().length > 0
    const hasFiles = attachFiles.length > 0
    if (!hasText && !hasFiles) return

    setReplySending(true)
    setSendError('')
    try {
      const content = hasText ? replyContent.trim() : ''

      const newItem = await postProjectDiscussion(projectId, { content, is_internal: replyIsInternal })

      if (hasFiles) {
        const uploaded = []
        for (const file of attachFiles) {
          const result = await uploadAttachment(newItem.ticket_id, file, newItem.id)
          uploaded.push(result)
        }
        setDiscussionAttachments(prev => [...prev, ...uploaded])
      }

      setItems(prev => [...prev, newItem])
      setTotal(prev => prev + 1)
      setReplyContent('')
      setReplyIsInternal(false)
      setAttachFiles([])
    } catch (err) {
      setSendError(err?.response?.data?.detail ?? 'Failed to send message')
    } finally {
      setReplySending(false)
    }
  }

  return (
    <div className="flex flex-col gap-0">
      {loading && items.length === 0 ? (
        <div className="space-y-3 p-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex gap-3 animate-pulse">
              <div className="h-8 w-8 rounded-full bg-slate-200 flex-shrink-0" />
              <div className="flex-1 space-y-1.5 pt-1">
                <div className="h-3 w-24 rounded bg-slate-200" />
                <div className="h-3 w-full rounded bg-slate-100" />
              </div>
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="px-5 py-8 text-sm text-slate-400 text-center">No messages yet. Be the first to send one.</p>
      ) : (
        <div className="divide-y divide-slate-100">
          {items.map(item => (
            <DiscussionItem key={item.id} item={item} attachments={discussionAttachments.filter(a => a.reply_id === item.id)} />
          ))}
        </div>
      )}

      {items.length < total && (
        <div className="px-5 py-3 text-center">
          <button type="button" onClick={() => fetchPage(page + 1)} disabled={loading} className="text-xs text-violet-600 hover:underline disabled:opacity-50">
            {loading ? 'Loading…' : `Load more (${total - items.length} remaining)`}
          </button>
        </div>
      )}

      <div className="px-5 py-4 border-t border-slate-100 space-y-2">
        {sendError && <p className="text-xs text-red-600">{sendError}</p>}

        {/* H.2: attached files queue */}
        {attachFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {attachFiles.map(f => (
              <span key={f.name} className="inline-flex items-center gap-1 text-xs bg-slate-100 text-slate-700 px-2 py-1 rounded-lg">
                <PaperClipIcon className="w-3 h-3" />
                {f.name}
                <button type="button" onClick={() => setAttachFiles(prev => prev.filter(x => x.name !== f.name))} className="ml-0.5 text-slate-400 hover:text-red-500">
                  <XMarkIcon className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        <textarea
          value={replyContent}
          onChange={e => setReplyContent(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSend() }}
          placeholder="Write a message…"
          rows={2}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-400"
        />

        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          accept="image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv"
          onChange={e => {
            const newFiles = Array.from(e.target.files ?? [])
            setAttachFiles(prev => {
              const names = new Set(prev.map(x => x.name))
              return [...prev, ...newFiles.filter(x => !names.has(x.name))]
            })
            e.target.value = ''
          }}
        />

        <div className="flex items-center gap-2">
          {!isCustomer && (
            <label className="flex items-center gap-1.5 text-xs text-slate-600 cursor-pointer select-none">
              <input type="checkbox" checked={replyIsInternal} onChange={e => setReplyIsInternal(e.target.checked)} className="rounded" />
              Internal only
            </label>
          )}
          {/* H.2: attach button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 text-xs transition-colors"
            title="Attach file"
          >
            <PaperClipIcon className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleSend}
            disabled={(!replyContent.trim() && attachFiles.length === 0) || replySending}
            className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 text-white text-xs font-semibold hover:bg-amber-600 disabled:opacity-50 transition-colors"
          >
            {replySending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── MembersPanel (popover) ────────────────────────────────────────────────────────

function MembersPanel({ projectId, members, canManage, onRefresh, onClose }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [addingId, setAddingId] = useState(null)
  const [removingId, setRemovingId] = useState(null)
  const [errors, setErrors] = useState({})
  const [added, setAdded] = useState(new Set())

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    const t = setTimeout(async () => {
      setSearching(true)
      try {
        const data = await listUsers({ search: query.trim(), per_page: 20 })
        setResults(data.items ?? data ?? [])
      } catch { setResults([]) }
      finally { setSearching(false) }
    }, 300)
    return () => clearTimeout(t)
  }, [query])

  const handleAdd = async (u) => {
    setAddingId(u.id)
    setErrors(prev => ({ ...prev, [u.id]: '' }))
    try {
      await addProjectMember(projectId, { user_id: u.id, role: u.role === 'customer' ? 'customer' : 'staff' })
      setAdded(prev => new Set([...prev, u.id]))
      onRefresh()
    } catch (err) {
      setErrors(prev => ({ ...prev, [u.id]: err?.response?.data?.detail ?? 'Failed to add' }))
    } finally { setAddingId(null) }
  }

  const handleRemove = async (m) => {
    setRemovingId(m.user_id)
    try {
      await removeProjectMember(projectId, m.user_id)
      onRefresh()
    } catch { /* ignore */ }
    finally { setRemovingId(null) }
  }

  const ROLE_BADGE = {
    manager: 'bg-amber-100 text-amber-700',
    staff: 'bg-blue-100 text-blue-700',
    customer: 'bg-green-100 text-green-700',
  }

  return (
    <div className="absolute right-0 top-9 z-30 w-72 bg-white border border-slate-200 rounded-xl shadow-xl">
      <div className="px-4 py-2.5 border-b border-slate-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Team Members ({members.length})</span>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 p-0.5 rounded">
          <XMarkIcon className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="max-h-44 overflow-y-auto">
        {members.length === 0 ? (
          <p className="px-4 py-3 text-xs text-slate-400">No members yet.</p>
        ) : (
          <div className="divide-y divide-slate-50">
            {members.map(m => (
              <div key={m.id} className="flex items-center gap-2 px-4 py-2">
                <UserAvatar user={{ full_name: m.user_full_name, email: m.user_email }} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-800 truncate">{m.user_full_name || m.user_email}</p>
                  <p className="text-[10px] text-slate-400 truncate">{m.user_email}</p>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${ROLE_BADGE[m.role] ?? 'bg-slate-100 text-slate-600'}`}>{m.role}</span>
                {canManage && (
                  <button
                    type="button"
                    onClick={() => handleRemove(m)}
                    disabled={removingId === m.user_id}
                    className="flex-shrink-0 text-slate-300 hover:text-red-500 disabled:opacity-40 transition-colors"
                    title="Remove"
                  >
                    {removingId === m.user_id ? <Spinner className="w-3 h-3" /> : <XMarkIcon className="w-3 h-3" />}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {canManage && (
        <>
          <div className="border-t border-slate-100 px-4 pt-2.5 pb-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search to add…"
                className="w-full pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-amber-400"
              />
              {searching && <Spinner className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3 h-3" />}
            </div>
          </div>
          {results.length > 0 && (
            <div className="max-h-36 overflow-y-auto border-t border-slate-50 divide-y divide-slate-50">
              {results.map(u => (
                <div key={u.id} className="flex items-center gap-2 px-4 py-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-800 truncate">{u.full_name || u.email}</p>
                    <p className="text-[10px] text-slate-400 truncate">{u.email}</p>
                    {errors[u.id] && <p className="text-[10px] text-red-600">{errors[u.id]}</p>}
                  </div>
                  {added.has(u.id) ? (
                    <span className="text-[10px] text-green-600 font-semibold flex-shrink-0">Added ✓</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleAdd(u)}
                      disabled={addingId === u.id}
                      className="flex-shrink-0 px-2.5 py-1 rounded-lg bg-amber-500 text-white text-[10px] font-semibold hover:bg-amber-600 disabled:opacity-50 transition-colors"
                    >
                      {addingId === u.id ? '…' : 'Add'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="h-2" />
        </>
      )}
    </div>
  )
}

// ── Tab definitions ─────────────────────────────────────────────────────────────

const TABS = [
  { id: 'overview',    label: 'Overview' },
  { id: 'tasks',       label: 'Tasks' },
  { id: 'discussion',  label: 'Discussion' },
  { id: 'files',       label: 'Files' },
  { id: 'activity',    label: 'Activity' },
]

const PROGRESS_BAR_COLOR = {
  working:   'bg-blue-500',
  completed: 'bg-green-500',
  on_hold:   'bg-amber-500',
  open:      'bg-slate-400',
  cancelled: 'bg-slate-300',
}

// ── Main component ──────────────────────────────────────────────────────────────

export default function ProjectDetailPage() {
  const { id } = useParams()
  const { isCustomer, isAdmin, isStaff } = useRole()
  const taskFormRef = useRef(null)
  const [project, setProject] = useState(null)
  const [tasks, setTasks] = useState([])
  const [documents, setDocuments] = useState([])
  const [linkedTickets, setLinkedTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [error, setError] = useState('')
  const [documentsError, setDocumentsError] = useState('')
  const [updatingTask, setUpdatingTask] = useState(null)
  const [editingTaskId, setEditingTaskId] = useState(null)
  const [taskActionId, setTaskActionId] = useState(null)
  const [selectedTaskId, setSelectedTaskId] = useState(null)
  const [activeTab, setActiveTab] = useState('tasks')
  const [taskStatusFilter, setTaskStatusFilter] = useState('')
  const [taskAssigneeFilter, setTaskAssigneeFilter] = useState('')
  const [taskView, setTaskView] = useState('list')
  const [showMembersPanel, setShowMembersPanel] = useState(false)
  const [members, setMembers] = useState([])
  const membersPanelRef = useRef(null)

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
      const [projectData, taskData, documentData, ticketData] = await Promise.all([
        getProject(id),
        listProjectTasks(id),
        listProjectDocuments(id).catch(() => []),
        getProjectTickets(id).catch(() => []),
      ])
      setProject(projectData)
      setTasks(taskData)
      setDocuments(documentData)
      setLinkedTickets(ticketData)
    } catch (err) {
      setError(err?.response?.data?.detail ?? err?.message ?? 'Failed to load project')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const loadMembers = useCallback(async () => {
    try { setMembers(await listProjectMembers(id)) } catch { /* ignore */ }
  }, [id])

  useEffect(() => { if (id) loadMembers() }, [loadMembers])

  // Close members panel on outside click
  useEffect(() => {
    if (!showMembersPanel) return
    const handler = (e) => {
      if (membersPanelRef.current && !membersPanelRef.current.contains(e.target)) {
        setShowMembersPanel(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showMembersPanel])

  const stats = useMemo(() => {
    const total = tasks.length
    const completed = tasks.filter(t => t.status === 'completed').length
    const inProgress = tasks.filter(t => ['working', 'review'].includes(t.status)).length
    const overdue = tasks.filter(t => {
      if (!t.due_date || ['completed', 'cancelled'].includes(t.status)) return false
      const due = new Date(t.due_date); due.setHours(23, 59, 59, 999)
      return due < new Date()
    }).length
    let daysRemaining = '—'
    if (project?.due_date) {
      const today = new Date(); today.setHours(0, 0, 0, 0)
      const due = new Date(project.due_date); due.setHours(0, 0, 0, 0)
      daysRemaining = Math.ceil((due.getTime() - today.getTime()) / 86400000)
    }
    return { total, completed, inProgress, overdue, daysRemaining }
  }, [project?.due_date, tasks])

  const headerMembers = useMemo(() => members.slice(0, 4), [members])
  const extraMemberCount = Math.max(0, members.length - 4)

  // Unique assignees for task filter dropdown
  const taskAssignees = useMemo(() => {
    const seen = new Map()
    tasks.forEach(t => {
      if (t.assignee_id) seen.set(t.assignee_id, t.assignee_name || t.assignee_email || `#${t.assignee_id}`)
      t.assignees?.forEach(a => {
        if (a.user_id) seen.set(a.user_id, a.full_name || a.email || `#${a.user_id}`)
      })
    })
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }))
  }, [tasks])

  const filteredTasks = useMemo(() => {
    return tasks.filter(t => {
      if (taskStatusFilter && t.status !== taskStatusFilter) return false
      if (taskAssigneeFilter) {
        const uid = Number(taskAssigneeFilter)
        const match = t.assignee_id === uid || t.assignees?.some(a => a.user_id === uid)
        if (!match) return false
      }
      return true
    })
  }, [tasks, taskStatusFilter, taskAssigneeFilter])

  const addTask = async (payload) => { await createProjectTask(id, payload); await load() }
  const changeStatus = async (taskId, status) => {
    setUpdatingTask(taskId)
    try { await updateProjectTaskStatus(taskId, status); await load() }
    finally { setUpdatingTask(null) }
  }
  const saveTask = async (taskId, payload) => {
    await updateProjectTask(taskId, payload)
    setEditingTaskId(null)
    await load()
  }
  const cancelTask = async (taskId) => {
    setTaskActionId(taskId)
    try { await cancelProjectTask(taskId); await load() }
    finally { setTaskActionId(null) }
  }
  const cancel = async () => { await cancelProject(id); await load() }
  const uploadDocument = async (file, isClientVisible) => {
    await uploadProjectDocument(id, file, isClientVisible)
    await loadDocuments()
  }

  if (loading) return (
    <div className="p-6 space-y-4">
      <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {[1,2,3,4].map(i => <div key={i} className="h-28 animate-pulse rounded-2xl bg-slate-200" />)}
      </div>
      <div className="h-80 animate-pulse rounded-2xl bg-slate-200" />
    </div>
  )
  if (error) return (
    <div className="p-6">
      <div className="rounded-2xl border border-red-100 bg-red-50 p-5 text-sm text-red-700">
        <p className="font-semibold">Project could not be loaded.</p>
        <p className="mt-1">{error}</p>
        <button onClick={load} className="mt-4 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700">Retry</button>
      </div>
    </div>
  )
  if (!project) return null

  const projectOverdue = isPastDeadline(project.due_date, project.status)
  const dueDays = daysUntilDeadline(project.due_date)
  const progressPct = Math.max(0, Math.min(100, Number(project.progress_percent ?? 0)))
  const progressColor = PROGRESS_BAR_COLOR[project.status] ?? 'bg-slate-400'

  return (
    <>
      <div className="min-h-full bg-slate-50">

        {/* ── Sticky header + tab bar ───────────────────────────────────────── */}
        <div className="sticky top-0 z-20">

          {/* Project header */}
          <div className="bg-white border-b border-slate-200 shadow-sm">
            <div className="max-w-6xl mx-auto px-6 lg:px-8 py-3">
              <Link to="/projects" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-700 transition-colors mb-2">
                <ArrowLeftIcon className="h-3.5 w-3.5" /> Back to Projects
              </Link>

              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h1 className="text-lg font-bold text-slate-900 truncate">{project.name}</h1>
                    <StatusBadge status={project.status} />
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 capitalize">{project.project_type?.replace('_', ' ')}</span>
                    {!isCustomer && project.org_name && (
                      <span className="text-xs text-slate-400">{project.org_name}</span>
                    )}
                  </div>

                  {/* Progress bar */}
                  <div className="mt-2.5 flex items-center gap-3">
                    <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden max-w-xs">
                      <div className={`h-full rounded-full transition-all duration-500 ${progressColor}`} style={{ width: `${progressPct}%` }} />
                    </div>
                    <span className="text-xs text-slate-500 tabular-nums flex-shrink-0">{Math.round(progressPct)}% complete</span>
                  </div>
                </div>

                {/* Right: due date + member avatars + actions */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  {/* Due date */}
                  {project.due_date && (
                    <div className="text-right hidden sm:block">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wide">Due</p>
                      <p className={`text-xs font-semibold ${projectOverdue ? 'text-red-600' : dueDays !== null && dueDays <= 7 ? 'text-amber-600' : 'text-slate-700'}`}>
                        {projectOverdue ? 'Overdue' : dueDays !== null && dueDays <= 7 ? `${dueDays}d left` : fmtDate(project.due_date)}
                      </p>
                    </div>
                  )}

                  {/* Member avatars + panel */}
                  <div className="relative" ref={membersPanelRef}>
                    <div className="flex -space-x-2 items-center">
                      {headerMembers.map(m => (
                        <UserAvatar
                          key={m.id}
                          user={{ full_name: m.user_full_name, email: m.user_email }}
                          size="sm"
                          className="border-2 border-white cursor-pointer"
                          title={m.user_full_name || m.user_email}
                          onClick={() => setShowMembersPanel(v => !v)}
                        />
                      ))}
                      {extraMemberCount > 0 && (
                        <div
                          className="h-7 w-7 rounded-full border-2 border-white bg-slate-200 flex items-center justify-center text-[10px] font-semibold text-slate-600 cursor-pointer"
                          onClick={() => setShowMembersPanel(v => !v)}
                          title={`${extraMemberCount} more members`}
                        >
                          +{extraMemberCount}
                        </div>
                      )}
                      {!isCustomer && (
                        <button
                          type="button"
                          title="Manage members"
                          onClick={() => setShowMembersPanel(v => !v)}
                          className="h-7 w-7 rounded-full border-2 border-dashed border-slate-300 bg-white flex items-center justify-center text-slate-400 hover:text-slate-600 hover:border-slate-400 transition-colors"
                        >
                          <PlusIcon className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                    {showMembersPanel && (
                      <MembersPanel
                        projectId={id}
                        members={members}
                        canManage={!isCustomer}
                        onRefresh={loadMembers}
                        onClose={() => setShowMembersPanel(false)}
                      />
                    )}
                  </div>

                  {/* Actions */}
                  {!isCustomer && project.status !== 'cancelled' && (
                    <button onClick={cancel} className="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 transition-colors">
                      <ArchiveBoxIcon className="h-3.5 w-3.5" />
                      Archive
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Tab bar */}
          <div className="bg-white border-b border-slate-200">
            <div className="max-w-6xl mx-auto px-6 lg:px-8 flex gap-0 overflow-x-auto scrollbar-none">
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap -mb-px ${
                    activeTab === tab.id
                      ? 'border-amber-500 text-amber-700'
                      : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
                  }`}
                >
                  {tab.label}
                  {tab.id === 'tasks' && tasks.length > 0 && (
                    <span className="ml-1.5 text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">{tasks.length}</span>
                  )}
                  {tab.id === 'files' && documents.length > 0 && (
                    <span className="ml-1.5 text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">{documents.length}</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Tab content ────────────────────────────────────────────────────── */}
        <div className="max-w-6xl mx-auto px-6 lg:px-8 py-6">

          {/* Overview tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Stats row */}
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
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

              {/* 2-col: project info | linked tickets */}
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <div className="space-y-5">
                  <WorkspaceCard title="About Project" icon={FolderIcon}>
                    <div className="px-5 py-5">
                      <p className="text-sm leading-6 text-slate-600 whitespace-pre-wrap">{project.description || 'No project description has been added yet.'}</p>
                      <dl className="mt-5 grid grid-cols-1 gap-3 text-sm">
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
                      </dl>
                    </div>
                  </WorkspaceCard>

                  {/* Team members */}
                  {!isCustomer && headerMembers.length > 0 && (
                    <WorkspaceCard title="Team Members" icon={UserGroupIcon}>
                      <div className="divide-y divide-slate-100">
                        {headerMembers.map(m => (
                          <div key={m.id} className="px-5 py-3 flex items-center gap-3">
                            <UserAvatar user={{ full_name: m.user_full_name, email: m.user_email }} size="sm" />
                            <span className="text-sm font-medium text-slate-800 truncate" title={m.user_full_name || m.user_email}>
                              {m.user_full_name || m.user_email}
                            </span>
                          </div>
                        ))}
                      </div>
                    </WorkspaceCard>
                  )}
                </div>

                {/* Linked tickets */}
                <WorkspaceCard title="Linked Tickets" icon={DocumentTextIcon}>
                  {linkedTickets.length === 0 ? (
                    <EmptyPanel>No tickets linked to this project yet.</EmptyPanel>
                  ) : (
                    <div className="divide-y divide-slate-100">
                      {linkedTickets.map(t => (
                        <Link key={t.id} to={`/tickets/${t.id}`} className="px-5 py-3 flex items-center justify-between gap-3 hover:bg-slate-50 cursor-pointer">
                          <span className="text-sm font-medium text-slate-900 hover:text-amber-600 truncate flex-1">
                            #{t.id} {t.subject}
                          </span>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-[10px] text-slate-400">{fmtDate(t.created_at)}</span>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TICKET_STATUS_BADGE[t.status] ?? 'bg-gray-100 text-gray-500'}`}>
                              {t.status}
                            </span>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </WorkspaceCard>
              </div>
            </div>
          )}

          {/* Tasks tab */}
          {activeTab === 'tasks' && (
            <div className="space-y-4">
              {/* Filter bar */}
              <div className="flex items-center gap-3 flex-wrap">
                {/* Status pills — hidden in board mode (columns are the statuses) */}
                {taskView === 'list' && (
                  <div className="flex gap-1 bg-slate-100 rounded-lg p-1">
                    {['All', 'Open', 'Working', 'Review', 'Approved', 'Completed'].map(s => {
                      const val = s === 'All' ? '' : s.toLowerCase()
                      return (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setTaskStatusFilter(val)}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            taskStatusFilter === val
                              ? 'bg-white shadow text-slate-900'
                              : 'text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          {s}
                        </button>
                      )
                    })}
                  </div>
                )}
                {taskAssignees.length > 0 && (
                  <select
                    value={taskAssigneeFilter}
                    onChange={e => setTaskAssigneeFilter(e.target.value)}
                    className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-amber-400"
                  >
                    <option value="">All assignees</option>
                    {taskAssignees.map(a => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                )}
                {taskView === 'list' && (taskStatusFilter || taskAssigneeFilter) && (
                  <button
                    type="button"
                    onClick={() => { setTaskStatusFilter(''); setTaskAssigneeFilter('') }}
                    className="text-xs text-slate-400 hover:text-slate-700 flex items-center gap-1"
                  >
                    <XMarkIcon className="w-3 h-3" /> Clear filters
                  </button>
                )}
                {taskView === 'list' && (taskStatusFilter || taskAssigneeFilter) && (
                  <span className="text-xs text-slate-400">{filteredTasks.length} of {tasks.length} tasks</span>
                )}
                {/* List / Board view toggle */}
                <div className="flex gap-0.5 bg-slate-100 rounded-lg p-1 ml-auto">
                  {[['list', 'List'], ['board', 'Board']].map(([mode, label]) => (
                    <button
                      key={mode}
                      type="button"
                      onClick={() => setTaskView(mode)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                        taskView === mode
                          ? 'bg-white shadow text-slate-900'
                          : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {!isCustomer && <div ref={taskFormRef}><TaskCreateForm onCreate={addTask} /></div>}

              {/* ── List view ── */}
              {taskView === 'list' && (
                <WorkspaceCard title="Task List" icon={CheckCircleIcon} action={<span className="text-xs text-slate-500">{filteredTasks.length} shown</span>}>
                  {filteredTasks.length === 0 ? (
                    <EmptyPanel>
                      {tasks.length === 0
                        ? (isCustomer ? 'No customer-visible tasks are available yet.' : 'No tasks have been created yet.')
                        : 'No tasks match the current filters.'}
                    </EmptyPanel>
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
                          {filteredTasks.map(task => (
                            <Fragment key={task.id}>
                              <tr className="hover:bg-slate-50/70 cursor-pointer" onClick={() => setSelectedTaskId(task.id)}>
                                <td className="px-4 py-3">
                                  <span className={`flex h-5 w-5 items-center justify-center rounded-full border ${task.status === 'completed' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-300 text-transparent'}`}>
                                    <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
                                  </span>
                                </td>
                                <td className="px-4 py-3 min-w-64">
                                  <p className="font-medium text-slate-900">{task.title}</p>
                                  {task.description && <p className="text-xs text-slate-500 mt-0.5">{task.description}</p>}
                                  <p className="mt-1 text-xs text-slate-400">{TASK_TYPES.find(([v]) => v === task.task_type)?.[1] ?? task.task_type}</p>
                                  {!isCustomer && task.internal_note && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1 mt-2">Internal: {task.internal_note}</p>}
                                </td>
                                <td className="px-4 py-3"><AssigneesPills assignees={task.assignees} /></td>
                                <td className="px-4 py-3">
                                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${PRIORITY_CLASSES[task.priority] ?? PRIORITY_CLASSES.medium}`}>{task.priority}</span>
                                </td>
                                <td className="px-4 py-3"><TaskStatusBadge status={task.status} /></td>
                                {!isCustomer && <td className="px-4 py-3 text-xs text-slate-500">{task.is_client_visible ? <span className="text-green-700">Visible</span> : 'Internal'}</td>}
                                <td className="px-4 py-3 text-slate-500">
                                  <span className="inline-flex items-center gap-1 text-xs">
                                    <CalendarDaysIcon className="w-3.5 h-3.5" aria-hidden="true" />
                                    {fmtDate(task.due_date)}
                                  </span>
                                </td>
                                {!isCustomer && (
                                  <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                                    <div className="flex items-center gap-2">
                                      <select
                                        value={task.status}
                                        disabled={updatingTask === task.id || task.status === 'cancelled'}
                                        onChange={e => changeStatus(task.id, e.target.value)}
                                        className="px-2 py-1 border border-slate-200 rounded bg-white text-xs"
                                      >
                                        {TASK_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
                                      </select>
                                      <button type="button" onClick={() => setEditingTaskId(task.id)} className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-100" title="Edit task">
                                        <PencilSquareIcon className="h-3.5 w-3.5" aria-hidden="true" />
                                      </button>
                                      <button type="button" onClick={() => cancelTask(task.id)} disabled={taskActionId === task.id || task.status === 'cancelled'} className="rounded border border-red-100 p-1.5 text-red-600 hover:bg-red-50 disabled:opacity-40" title="Cancel task">
                                        <XMarkIcon className="h-3.5 w-3.5" aria-hidden="true" />
                                      </button>
                                    </div>
                                  </td>
                                )}
                              </tr>
                              {!isCustomer && editingTaskId === task.id && (
                                <TaskEditRow key={`${task.id}-edit`} task={task} onCancel={() => setEditingTaskId(null)} onSave={(payload) => saveTask(task.id, payload)} />
                              )}
                            </Fragment>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </WorkspaceCard>
              )}

              {/* ── Board view ── */}
              {taskView === 'board' && (
                <div className="overflow-x-auto pb-3 -mx-1 px-1">
                  <div className="flex gap-3" style={{ minWidth: 'max-content' }}>
                    {KANBAN_COLUMNS.map(col => {
                      const colTasks = filteredTasks.filter(t => t.status === col.key)
                      return (
                        <div key={col.key} className="w-60 flex-shrink-0 flex flex-col">
                          {/* Column header */}
                          <div className="flex items-center gap-2 mb-2 px-1">
                            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${col.dot}`} />
                            <span className={`text-xs font-semibold uppercase tracking-wider ${col.head}`}>{col.label}</span>
                            <span className="ml-auto text-xs text-slate-400 bg-white border border-slate-200 px-1.5 py-0.5 rounded-full font-medium">
                              {colTasks.length}
                            </span>
                          </div>
                          {/* Column body */}
                          <div className={`flex-1 rounded-xl p-2 space-y-2 min-h-28 ${col.colBg}`}>
                            {colTasks.map(task => (
                              <KanbanCard
                                key={task.id}
                                task={task}
                                onOpen={() => setSelectedTaskId(task.id)}
                              />
                            ))}
                            {colTasks.length === 0 && (
                              <div className="flex items-center justify-center h-16 text-xs text-slate-300 select-none">
                                Empty
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Discussion tab */}
          {activeTab === 'discussion' && (
            <WorkspaceCard title="Discussion" icon={ChatBubbleLeftRightIcon}>
              <DiscussionPanel projectId={id} isCustomer={isCustomer} />
            </WorkspaceCard>
          )}

          {/* Files tab */}
          {activeTab === 'files' && (
            <WorkspaceCard title="Files" icon={DocumentTextIcon}>
              <DocumentsPanel
                projectId={id}
                documents={documents}
                loading={documentsLoading}
                error={documentsError}
                canUpload={!isCustomer}
                onUpload={uploadDocument}
                onDownload={downloadProjectDocument}
              />
            </WorkspaceCard>
          )}

          {/* Activity tab */}
          {activeTab === 'activity' && (
            <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center">
              <ClockIcon className="mx-auto h-10 w-10 text-slate-300 mb-3" />
              <p className="text-sm font-semibold text-slate-600">Activity timeline coming soon.</p>
              <p className="text-xs text-slate-400 mt-1">We're working on a unified view across all project tasks and discussions.</p>
            </div>
          )}
        </div>
      </div>

      {selectedTaskId && (
        <TaskDetailModal
          taskId={selectedTaskId}
          isCustomer={isCustomer}
          onClose={() => setSelectedTaskId(null)}
        />
      )}

    </>
  )
}
