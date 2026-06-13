import { useState, useRef, useEffect, useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useTicket } from '@/hooks/useTickets'
import { useAuthStore } from '@/hooks/useAuth'
import { useRole } from '@/hooks/useRole'
import { updateTicket, assignTicket, getTransferRequest, createTransferRequest, acceptTransfer, declineTransfer } from '@/api/tickets'
import { listUsers } from '@/api/users'
import { getAttachments, uploadAttachment } from '@/api/attachments'
import { Spinner } from '@/components/ui'
import AttachmentList from '@/components/ui/AttachmentList'
import { formatDateTime, formatDate, daysUntil } from '@/lib/utils'
import { cn } from '@/lib/utils'
import {
  ArrowLeftIcon,
  PaperAirplaneIcon,
  PaperClipIcon,
  TagIcon,
  UserCircleIcon,
  UserPlusIcon,
  CalendarDaysIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  LockClosedIcon,
  ChevronDownIcon,
  BuildingOffice2Icon,
  ServerStackIcon,
  SparklesIcon,
  CubeIcon,
  BanknotesIcon,
  CircleStackIcon,
  FolderIcon,
} from '@heroicons/react/24/outline'

const STATUS_STYLES = {
  Open:          'bg-blue-50 text-blue-700 border border-blue-200',
  'In Progress': 'bg-amber-50 text-amber-700 border border-amber-200',
  Waiting:       'bg-purple-50 text-purple-700 border border-purple-200',
  Resolved:      'bg-green-50 text-green-700 border border-green-200',
  Closed:        'bg-gray-100 text-gray-600 border border-gray-200',
}

const PRIORITY_STYLES = {
  Low:    'bg-gray-100 text-gray-500',
  Medium: 'bg-yellow-50 text-yellow-700',
  High:   'bg-orange-50 text-orange-700',
  Urgent: 'bg-red-50 text-red-700',
}

const VALID_NEXT = {
  Open:          ['In Progress'],
  'In Progress': ['Waiting', 'Resolved'],
  Waiting:       ['In Progress', 'Resolved'],
  Resolved:      ['Closed', 'In Progress'],
  Closed:        ['Open'],
}

function activityLabel(a) {
  switch (a.action) {
    case 'created':        return 'Ticket created'
    case 'status_change':  return `Status changed: ${a.from_value} → ${a.to_value}`
    case 'priority_change':return `Priority changed: ${a.from_value} → ${a.to_value}`
    case 'assigned':       return 'Ticket assigned'
    case 'auto_assigned':  return 'Auto-assigned by system'
    case 'replied':        return 'Reply added'
    case 'deleted':        return 'Ticket deleted'
    default:               return a.action
  }
}

function StatusBadge({ label }) {
  const cls = STATUS_STYLES[label] ?? 'bg-gray-100 text-gray-600 border border-gray-200'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>{label}</span>
}

function PriorityBadge({ label }) {
  const cls = PRIORITY_STYLES[label] ?? 'bg-gray-100 text-gray-600'
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
}

function SlaBar({ sla }) {
  if (!sla || sla.state === 'unknown') return null
  if (sla.state === 'met') {
    return (
      <div className="flex items-center gap-1.5 text-xs font-semibold text-green-600">
        <CheckCircleIcon className="w-3.5 h-3.5" /> SLA met
      </div>
    )
  }
  if (sla.state === 'breached' && sla.percent_remaining === null) {
    return (
      <div className="flex items-center gap-1.5 text-xs font-semibold text-red-600">
        <ExclamationTriangleIcon className="w-3.5 h-3.5" /> SLA breached
      </div>
    )
  }
  const pct = sla.percent_remaining ?? 0
  const hrs = sla.hours_remaining ?? 0
  const barColor = sla.state === 'green' ? 'bg-green-500' : sla.state === 'amber' ? 'bg-amber-500' : 'bg-red-500'
  const textColor = sla.state === 'green' ? 'text-green-700' : sla.state === 'amber' ? 'text-amber-700' : 'text-red-700'
  return (
    <div className="flex flex-col gap-1 min-w-[180px]">
      <div className="flex items-center justify-between text-[10px] font-medium text-gray-400 uppercase tracking-wide">
        <span>Resolution SLA</span>
        <span className={cn('font-semibold', textColor)}>
          {sla.state === 'breached' ? 'Breached' : `${Math.max(0, hrs).toFixed(1)}h left`}
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', barColor)} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="text-[10px] text-gray-400 text-right">{pct.toFixed(0)}% remaining</span>
      {sla.paused_total_seconds > 0 && (
        <span className="text-[10px] text-gray-400 text-right">
          Paused {Math.round(sla.paused_total_seconds / 60)}m total
        </span>
      )}
    </div>
  )
}

function ReplyItem({ reply, isCustomerReply, replyAttachments = [] }) {
  const initial = (reply.author_email || '?').charAt(0).toUpperCase()
  // Customer replies: left-aligned white bubble. Staff/admin: right-aligned blue bubble.
  const isRight = !isCustomerReply

  return (
    <div className={cn('flex gap-3 py-3', isRight && 'flex-row-reverse')}>
      <div
        className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-[11px] font-bold mt-0.5"
        style={isRight
          ? { background: '#DBEAFE', color: '#1D4ED8' }
          : { background: '#F3F4F6', color: '#4B5563' }}
      >
        {initial}
      </div>
      <div className={cn('flex-1 min-w-0', isRight && 'flex flex-col items-end')}>
        <div className={cn('flex items-baseline gap-2 mb-1 flex-wrap', isRight && 'flex-row-reverse')}>
          <span className="text-xs font-semibold text-gray-800">{reply.author_email ?? 'Unknown'}</span>
          <span className="text-[11px] text-gray-400">{formatDateTime(reply.created_at)}</span>
          {reply.is_internal && (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-gray-200 text-gray-600">
              <LockClosedIcon className="w-2.5 h-2.5" /> Internal
            </span>
          )}
        </div>
        <div className={cn(
          'border rounded-lg px-3 py-2 text-sm leading-relaxed max-w-[85%]',
          reply.is_internal
            ? 'bg-gray-50 border-gray-200 text-gray-700'
            : isRight
              ? 'bg-blue-50 border-blue-100 text-blue-900'
              : 'bg-white border-gray-200 text-gray-700',
        )}>
          <p className="whitespace-pre-wrap break-words">{reply.content}</p>
          {replyAttachments.length > 0 && (
            <AttachmentList attachments={replyAttachments} />
          )}
        </div>
      </div>
    </div>
  )
}

function ActivityItem({ activity }) {
  return (
    <div className="flex gap-2 text-xs text-gray-400 py-1">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-300 flex-shrink-0 mt-1.5" />
      <span className="flex-1">{activityLabel(activity)}</span>
      <span className="flex-shrink-0">{formatDateTime(activity.created_at)}</span>
    </div>
  )
}

const SVC_TYPE_STYLES = {
  saas:    { label: 'SaaS',    icon: SparklesIcon,  color: 'bg-violet-100 text-violet-700' },
  hosting: { label: 'Hosting', icon: ServerStackIcon, color: 'bg-blue-100 text-blue-700' },
  other:   { label: 'Other',   icon: CubeIcon,       color: 'bg-gray-100 text-gray-600' },
}

const SVC_STATUS_STYLES = {
  active:    'bg-emerald-100 text-emerald-700',
  inactive:  'bg-gray-100 text-gray-500',
  cancelled: 'bg-red-100 text-red-600',
  past_due:  'bg-amber-100 text-amber-700',
}

function ServiceExpiryChip({ dateStr }) {
  const days = daysUntil(dateStr)
  if (days === null) return null
  if (days < 0)   return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><ExclamationTriangleIcon className="w-3 h-3" /> Expired</span>
  if (days <= 7)  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><ExclamationTriangleIcon className="w-3 h-3" /> {days}d left</span>
  if (days <= 30) return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">{days}d left</span>
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">Expires {formatDate(dateStr)}</span>
}

function ServiceDiskBar({ usage }) {
  if (!usage) return null
  const match = usage.match(/([\d.]+)\s*\w+\s*\/\s*([\d.]+)/)
  if (!match) return <p className="text-xs font-semibold">{usage}</p>
  const pct = Math.min(100, Math.round((parseFloat(match[1]) / parseFloat(match[2])) * 100))
  const barColor = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-emerald-500'
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-[10px] text-gray-400">Disk Usage</span>
        <span className="text-xs font-semibold">{usage}</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function DetailRow({ icon: Icon, label, value }) {
  if (!value) return null
  return (
    <div className="flex items-start gap-2.5 py-2.5 border-b border-gray-50 last:border-0">
      <Icon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-0.5">{label}</p>
        <p className="text-xs font-medium text-gray-800 truncate">{value}</p>
      </div>
    </div>
  )
}

export default function TicketDetailPage() {
  const { id } = useParams()
  const { ticket, comments: replies, activities, sla, loading, reply, refetch } = useTicket(id)
  const { user } = useAuthStore()
  const { isStaff, isAdmin } = useRole()
  const isStaffOrAdmin = isStaff || isAdmin

  const [message, setMessage] = useState('')
  const [isInternal, setIsInternal] = useState(false)
  const [sending, setSending] = useState(false)
  const [statusUpdating, setStatusUpdating] = useState(false)
  const [attachments, setAttachments] = useState([])
  const [replyFiles, setReplyFiles] = useState([])
  const [uploadError, setUploadError] = useState('')
  const fileInputRef = useRef(null)
  const bottomRef = useRef(null)
  const [staffList, setStaffList] = useState([])
  const [transferReq, setTransferReq] = useState(null)
  const [assignUpdating, setAssignUpdating] = useState(false)
  const [showTransferModal, setShowTransferModal] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [replies])

  useEffect(() => {
    if (!id || !ticket) return
    getAttachments(id).then(setAttachments).catch(() => {})
  }, [id, ticket])

  const loadTransferReq = useCallback(() => {
    if (!id || !isStaffOrAdmin) return
    getTransferRequest(id).then(setTransferReq).catch(() => {})
  }, [id, isStaffOrAdmin])

  useEffect(() => {
    if (!isStaffOrAdmin) return
    listUsers({ role: 'staff', per_page: 100 })
      .then(d => setStaffList(Array.isArray(d) ? d : (d?.items ?? [])))
      .catch(() => {})
  }, [isStaffOrAdmin])

  useEffect(() => { loadTransferReq() }, [loadTransferReq])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!message.trim() && replyFiles.length === 0) return
    setSending(true)
    try {
      const created = await reply(message.trim() || '(attachment)', isInternal)
      // Upload reply attachments linked to this specific reply
      if (replyFiles.length > 0) {
        const results = await Promise.allSettled(replyFiles.map((f) => uploadAttachment(id, f, created?.id)))
        const failed = results.find((result) => result.status === 'rejected')
        setUploadError(failed ? (failed.reason?.message ?? 'Attachment upload failed') : '')
        setReplyFiles([])
      }
      setMessage('')
      setIsInternal(false)
      // Refresh attachments
      getAttachments(id).then(setAttachments).catch(() => {})
    } finally {
      setSending(false)
    }
  }

  const handleStatusChange = useCallback(async (newStatus) => {
    if (!ticket || statusUpdating) return
    setStatusUpdating(true)
    try {
      await updateTicket(ticket.id, { status: newStatus })
      await refetch()
    } catch (err) {
      console.error('Status update failed', err)
    } finally {
      setStatusUpdating(false)
    }
  }, [ticket, statusUpdating, refetch])

  const handleAssign = async (newAssigneeId) => {
    if (!newAssigneeId || assignUpdating) return
    setAssignUpdating(true)
    try {
      await assignTicket(ticket.id, Number(newAssigneeId))
      await refetch()
      loadTransferReq()
    } catch (err) {
      console.error('Assign failed', err)
    } finally {
      setAssignUpdating(false)
    }
  }

  const handleRequestTransfer = async (toStaffId) => {
    try {
      const req = await createTransferRequest(ticket.id, toStaffId)
      setTransferReq(req)
      setShowTransferModal(false)
    } catch (err) {
      console.error('Transfer request failed', err)
    }
  }

  const handleAcceptTransfer = async () => {
    if (!transferReq) return
    try {
      await acceptTransfer(ticket.id, transferReq.id)
      await refetch()
      setTransferReq(null)
      loadTransferReq()
    } catch (err) { console.error(err) }
  }

  const handleDeclineTransfer = async () => {
    if (!transferReq) return
    try {
      await declineTransfer(ticket.id, transferReq.id)
      setTransferReq(null)
      loadTransferReq()
    } catch (err) { console.error(err) }
  }

  if (loading) return <div className="flex items-center justify-center h-96"><Spinner className="w-5 h-5" /></div>
  if (!ticket) return <div className="p-8 text-gray-400 text-sm">Ticket not found.</div>

  const isClosed = ticket.status === 'Closed'
  const validNext = VALID_NEXT[ticket.status] ?? []
  const visibleReplies = user?.role === 'customer'
    ? replies.filter((reply) => !reply.is_internal)
    : replies

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <Link to="/tickets" className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors mb-3">
          <ArrowLeftIcon className="w-3.5 h-3.5" /> Back to tickets
        </Link>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0 flex-1">
            <h1 className="text-[20px] font-semibold text-gray-900 leading-tight tracking-tight">{ticket.subject}</h1>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              <span className="text-xs text-gray-400 font-mono">#{ticket.id}</span>
              <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{ticket.source}</span>
              {ticket.ticket_type && (
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">{ticket.ticket_type}</span>
              )}
              <PriorityBadge label={ticket.priority} />

              {isStaffOrAdmin ? (
                <div className="relative inline-flex">
                  <div className={cn(
                    'flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border cursor-pointer',
                    STATUS_STYLES[ticket.status] ?? 'bg-gray-100 text-gray-600 border-gray-200',
                  )}>
                    <select
                      value=""
                      onChange={(e) => e.target.value && handleStatusChange(e.target.value)}
                      disabled={statusUpdating || validNext.length === 0}
                      className="absolute inset-0 opacity-0 cursor-pointer w-full disabled:cursor-not-allowed"
                    >
                      <option value="">Change status…</option>
                      {validNext.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    {statusUpdating ? <Spinner className="w-3 h-3" /> : ticket.status}
                    {validNext.length > 0 && <ChevronDownIcon className="w-3 h-3 opacity-60" />}
                  </div>
                </div>
              ) : (
                <StatusBadge label={ticket.status} />
              )}
            </div>
          </div>

          {sla && sla.state !== 'unknown' && (
            <div className="flex-shrink-0 bg-gray-50 border border-gray-100 rounded-lg px-4 py-2.5">
              <SlaBar sla={sla} />
            </div>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden flex">
        <div className="flex-1 flex flex-col overflow-hidden">
          {ticket.description && (
            <div className="mx-6 mt-4 bg-white border border-gray-100 rounded-lg px-4 py-3 text-sm text-gray-600 leading-relaxed">
              <p className="whitespace-pre-wrap">{ticket.description}</p>
            </div>
          )}

          {attachments.filter(a => !a.reply_id).length > 0 && (
            <div className="mx-6 mt-2 px-4 pb-3 bg-white border border-gray-100 rounded-lg">
              <p className="text-xs font-medium text-gray-400 mb-1 pt-3">Attachments</p>
              <AttachmentList attachments={attachments.filter(a => !a.reply_id)} />
            </div>
          )}

          <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-2">
            {visibleReplies.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 gap-2">
                <CheckCircleIcon className="w-8 h-8 text-gray-200" />
                <p className="text-sm text-gray-400">No replies yet</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {visibleReplies.map((r) => (
                  <ReplyItem
                    key={r.id}
                    reply={r}
                    isCustomerReply={r.author_email === ticket.raised_by_email}
                    replyAttachments={attachments.filter(a => a.reply_id === r.id)}
                  />
                ))}
              </div>
            )}

            {activities && activities.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">Activity</p>
                <div className="space-y-0.5">
                  {activities.map((a) => <ActivityItem key={a.id} activity={a} />)}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {!isClosed ? (
            <div className="border-t border-gray-100 bg-white px-6 py-4">
              <form onSubmit={handleSend} className="space-y-2">
                {replyFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-2">
                    {replyFiles.map((f) => (
                      <span key={f.name} className="flex items-center gap-1 text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-lg">
                        <PaperClipIcon className="w-3 h-3" />
                        {f.name}
                        <button type="button" onClick={() => setReplyFiles(fs => fs.filter(x => x.name !== f.name))}
                          className="ml-1 text-gray-400 hover:text-red-500">×</button>
                      </span>
                    ))}
                  </div>
                )}
                {uploadError && (
                  <div className="text-xs text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                    {uploadError}
                  </div>
                )}
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(e) }
                  }}
                  placeholder="Write a reply… (Enter to send, Shift+Enter for new line)"
                  rows={2}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-200 bg-white text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400 resize-none transition"
                />
                <input
                  type="file"
                  multiple
                  ref={fileInputRef}
                  className="hidden"
                  accept="image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv"
                  onChange={(e) => {
                    const newFiles = Array.from(e.target.files)
                    setReplyFiles(fs => {
                      const names = new Set(fs.map(x => x.name))
                      return [...fs, ...newFiles.filter(x => !names.has(x.name))]
                    })
                    e.target.value = ''
                  }}
                />
                <div className="flex items-center gap-3">
                  {isStaffOrAdmin && (
                    <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={isInternal}
                        onChange={(e) => setIsInternal(e.target.checked)}
                        className="rounded border-gray-300"
                      />
                      <LockClosedIcon className="w-3.5 h-3.5" />
                      Internal note (hidden from customer)
                    </label>
                  )}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="h-9 px-3 inline-flex items-center gap-1.5 text-sm font-medium rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors"
                    title="Attach files"
                  >
                    <PaperClipIcon className="w-4 h-4" />
                  </button>
                  <button
                    type="submit"
                    disabled={(!message.trim() && replyFiles.length === 0) || sending}
                    className="ml-auto h-9 px-4 inline-flex items-center gap-1.5 text-sm font-medium rounded-lg bg-amber-400 text-amber-900 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {sending ? <Spinner className="w-4 h-4" /> : <PaperAirplaneIcon className="w-4 h-4" />}
                    Send
                  </button>
                </div>
              </form>
            </div>
          ) : (
            <div className="border-t border-gray-100 px-6 py-3 text-center text-xs text-gray-400 bg-gray-50">
              This ticket is <span className="font-medium">{ticket.status.toLowerCase()}</span> and no longer accepts replies.
            </div>
          )}
        </div>

        <div className="w-72 flex-shrink-0 border-l border-gray-100 bg-white overflow-y-auto scrollbar-thin">
          <div className="p-4 space-y-5">
            {/* Ticket Details */}
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Details</p>
              <DetailRow icon={CalendarDaysIcon} label="Created" value={formatDateTime(ticket.created_at)} />
              <DetailRow icon={CalendarDaysIcon} label="Updated" value={formatDateTime(ticket.updated_at)} />
              <DetailRow icon={TagIcon} label="Type" value={ticket.ticket_type} />
              <DetailRow icon={UserCircleIcon} label="Raised By" value={ticket.raised_by_email} />
            </div>

            {/* Assignment — Admin: direct dropdown; Staff: transfer request */}
            {isStaffOrAdmin && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-2">Assignment</p>

                {/* Current assignee */}
                <div className="flex items-center gap-2 mb-3">
                  <UserCircleIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span className="text-xs text-gray-700 font-medium">
                    {ticket.assignee_name
                      ? ticket.assignee_name
                      : ticket.assignee_id
                        ? `Staff #${ticket.assignee_id}`
                        : <span className="text-gray-400 italic">Unassigned</span>}
                  </span>
                </div>

                {/* Admin: direct assign dropdown */}
                {isAdmin && (
                  <div className="flex items-center gap-2">
                    <select
                      value={ticket.assignee_id ?? ''}
                      onChange={e => handleAssign(e.target.value)}
                      disabled={assignUpdating}
                      className="flex-1 text-xs px-2 py-1.5 border border-gray-200 rounded-lg bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:opacity-50"
                    >
                      <option value="">— Unassigned —</option>
                      {staffList.map(s => (
                        <option key={s.id} value={s.id}>{s.full_name}</option>
                      ))}
                    </select>
                    {assignUpdating && <Spinner className="w-3.5 h-3.5 flex-shrink-0" />}
                  </div>
                )}

                {/* Staff: transfer request flow */}
                {isStaff && (
                  <>
                    {/* Incoming transfer request (user is the target) */}
                    {transferReq && transferReq.to_staff_id === user.id && (
                      <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 space-y-2">
                        <p className="text-xs font-semibold text-amber-800">Transfer Request</p>
                        <p className="text-xs text-amber-700">
                          <span className="font-medium">{transferReq.from_staff_name}</span> wants to hand this ticket to you.
                        </p>
                        <div className="flex gap-2">
                          <button onClick={handleAcceptTransfer}
                            className="flex-1 px-2 py-1 text-xs font-medium rounded bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
                            Accept
                          </button>
                          <button onClick={handleDeclineTransfer}
                            className="flex-1 px-2 py-1 text-xs font-medium rounded border border-red-300 text-red-600 hover:bg-red-50 transition-colors">
                            Decline
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Outgoing pending request (user sent it) */}
                    {transferReq && transferReq.from_staff_id === user.id && (
                      <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
                        <p className="text-xs text-blue-700">
                          Waiting for <span className="font-medium">{transferReq.to_staff_name}</span> to accept the transfer.
                        </p>
                      </div>
                    )}

                    {/* No pending request + user is current assignee → show Request Transfer button */}
                    {!transferReq && ticket.assignee_id === user.id && (
                      <button onClick={() => setShowTransferModal(true)}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-dashed border-gray-300 text-gray-500 hover:border-blue-400 hover:text-blue-600 transition-colors">
                        <UserPlusIcon className="w-3.5 h-3.5" />
                        Request Transfer
                      </button>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Service Info */}
            {ticket.service_id && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">Service Info</p>
                <div className="space-y-3">
                  {/* Organization */}
                  <div className="flex items-start gap-2.5">
                    <BuildingOffice2Icon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-0.5">Organization</p>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs font-medium text-gray-800 truncate">
                          {ticket.org_name ?? `Org #${ticket.org_id}`}
                        </span>
                        {ticket.org_code && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gray-100 text-gray-500 font-mono">
                            {ticket.org_code}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Service name + type + status */}
                  <div className="flex items-start gap-2.5">
                    <ServerStackIcon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-0.5">Service</p>
                      <p className="text-xs font-medium text-gray-800 truncate mb-1">{ticket.service_name}</p>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {ticket.service_type && (() => {
                          const cfg = SVC_TYPE_STYLES[ticket.service_type] ?? SVC_TYPE_STYLES.other
                          return (
                            <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-semibold', cfg.color)}>
                              {cfg.label}
                            </span>
                          )
                        })()}
                        {ticket.service_status && (
                          <span className={cn(
                            'px-1.5 py-0.5 rounded text-[10px] font-semibold capitalize',
                            SVC_STATUS_STYLES[ticket.service_status] ?? 'bg-gray-100 text-gray-500',
                          )}>
                            {ticket.service_status.replace('_', ' ')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expiry */}
                  {ticket.service_expiry_date && (
                    <div className="flex items-start gap-2.5">
                      <CalendarDaysIcon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-0.5">Expiry</p>
                        <ServiceExpiryChip dateStr={ticket.service_expiry_date} />
                      </div>
                    </div>
                  )}

                  {/* Monthly Cost */}
                  {ticket.service_monthly_cost != null && ticket.service_monthly_cost > 0 && (
                    <div className="flex items-start gap-2.5">
                      <BanknotesIcon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-0.5">Monthly Cost</p>
                        <p className="text-xs font-semibold text-gray-800">
                          {new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(ticket.service_monthly_cost)}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Disk Usage */}
                  {ticket.service_disk_usage && (
                    <div className="flex items-start gap-2.5">
                      <CircleStackIcon className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[10px] font-medium text-gray-400 uppercase tracking-wide mb-1">Disk Usage</p>
                        <ServiceDiskBar usage={ticket.service_disk_usage} />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Org row when no service_id */}
            {!ticket.service_id && (
              <div>
                <DetailRow icon={BuildingOffice2Icon} label="Organization" value={ticket.org_name ?? `Org #${ticket.org_id}`} />
              </div>
            )}

            {/* Project badge */}
            {ticket.project_id && (
              <Link
                to={`/projects/${ticket.project_id}`}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-violet-50 text-violet-700 hover:bg-violet-100 transition-colors"
              >
                <FolderIcon className="w-3.5 h-3.5" aria-hidden="true" />
                Project #{ticket.project_id}
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Transfer Request Modal */}
      {showTransferModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-80 space-y-4">
            <h3 className="font-semibold text-gray-900">Request Transfer</h3>
            <p className="text-sm text-gray-500">Select a staff member to hand this ticket to. They must accept before the ticket is reassigned.</p>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {staffList.filter(s => s.id !== user.id).map(s => (
                <button key={s.id} onClick={() => handleRequestTransfer(s.id)}
                  className="w-full text-left px-3 py-2 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-300 text-sm text-gray-700 transition-colors">
                  <span className="font-medium">{s.full_name}</span>
                  <span className="text-xs text-gray-400 ml-1">({s.email})</span>
                </button>
              ))}
            </div>
            <button onClick={() => setShowTransferModal(false)}
              className="w-full px-4 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
