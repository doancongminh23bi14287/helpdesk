import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useCreateTicket } from '@/hooks/useTickets'
import { useAuthStore } from '@/hooks/useAuth'
import { useRole } from '@/hooks/useRole'
import { listOrganizations, getOrgServices } from '@/api/organizations'
import { listItems } from '@/api/items'
import { listProjects, getProjectTasks } from '@/api/projects'
import { listUsers } from '@/api/users'
import { Button, Spinner } from '@/components/ui'
import { uploadAttachment } from '@/api/attachments'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeftIcon, DocumentTextIcon, TagIcon,
  PaperClipIcon, XMarkIcon, CloudArrowUpIcon,
  ExclamationCircleIcon, CheckCircleIcon, ChevronDownIcon,
  BuildingOffice2Icon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import { formatDate, daysUntil } from '@/lib/utils'
import { SparklesIcon, ServerStackIcon as SvcServerStackIcon, CubeIcon, ExclamationTriangleIcon, GlobeAltIcon, WrenchScrewdriverIcon } from '@heroicons/react/24/outline'

const TICKET_TYPES = [
  'Question', 'Bug', 'Incident', 'Task Request', 'Change Request',
  'Feature Request', 'Content Request', 'SEO Request',
  'Approval Required', 'Complaint', 'Renewal', 'Other',
]

const CATALOGUE_TYPES = new Set(['Change Request', 'Renewal'])

const SERVICE_TYPE_BADGE = {
  saas:    { label: 'SaaS',    color: 'bg-violet-100 text-violet-700',  Icon: SparklesIcon },
  hosting: { label: 'Hosting', color: 'bg-blue-100 text-blue-700',      Icon: SvcServerStackIcon },
  domain:  { label: 'Domain',  color: 'bg-purple-100 text-purple-700',  Icon: GlobeAltIcon },
  support: { label: 'Support', color: 'bg-orange-100 text-orange-700',  Icon: WrenchScrewdriverIcon },
  other:   { label: 'Other',   color: 'bg-gray-100 text-gray-600',      Icon: CubeIcon },
}

const SVC_STATUS_STYLES = {
  active:    'bg-emerald-100 text-emerald-700',
  inactive:  'bg-gray-100 text-gray-500',
  cancelled: 'bg-red-100 text-red-600',
  past_due:  'bg-amber-100 text-amber-700',
}

function ServicePreviewCard({ service }) {
  const cfg = SERVICE_TYPE_BADGE[service.type] ?? SERVICE_TYPE_BADGE.other
  const statusCls = SVC_STATUS_STYLES[service.status] ?? 'bg-gray-100 text-gray-500'
  const days = daysUntil(service.expiry_date)
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-3 rounded-xl border border-border bg-muted/30 p-4 space-y-3"
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className={cn('px-2 py-0.5 rounded text-xs font-semibold', cfg.color)}>{cfg.label}</span>
          <span className={cn('px-2 py-0.5 rounded text-xs font-semibold capitalize', statusCls)}>
            {service.status?.replace('_', ' ')}
          </span>
        </div>
        {days !== null && (
          days < 0
            ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><ExclamationTriangleIcon className="w-3 h-3" /> Expired</span>
            : days <= 7
              ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><ExclamationTriangleIcon className="w-3 h-3" /> {days}d left</span>
              : days <= 30
                ? <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">{days}d left</span>
                : <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">Expires {formatDate(service.expiry_date)}</span>
        )}
      </div>
      {service.monthly_cost != null && service.monthly_cost > 0 && (
        <p className="text-xs text-muted-foreground">
          Monthly cost:{' '}
          <span className="font-semibold text-foreground">
            {new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(service.monthly_cost)}
          </span>
        </p>
      )}
    </motion.div>
  )
}

/* ── Reusable field wrapper ── */
function Field({ label, required, hint, error, children }) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
        {label}
        {required && <span className="text-rose-500">*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p className="flex items-center gap-1 text-xs text-rose-600">
          <ExclamationCircleIcon className="w-3.5 h-3.5 flex-shrink-0" /> {error}
        </p>
      )}
    </div>
  )
}

function StyledInput({ className, ...props }) {
  return (
    <input
      className={cn(
        'w-full rounded-xl border border-border bg-background px-3.5 py-2.5 text-sm',
        'text-foreground placeholder:text-muted-foreground/60',
        'ring-offset-background transition-all outline-none',
        'focus:border-primary/50 focus:ring-2 focus:ring-primary/10',
        'disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

function StyledTextarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        'w-full rounded-xl border border-border bg-background px-3.5 py-3 text-sm',
        'text-foreground placeholder:text-muted-foreground/60',
        'ring-offset-background transition-all outline-none resize-none',
        'focus:border-primary/50 focus:ring-2 focus:ring-primary/10',
        'disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

function StyledSelect({ className, error, ...props }) {
  return (
    <div className="relative">
      <select
        className={cn(
          'w-full appearance-none rounded-xl border border-border bg-background px-3.5 py-2.5 pr-10 text-sm',
          'text-foreground ring-offset-background transition-all outline-none',
          'focus:border-primary/50 focus:ring-2 focus:ring-primary/10',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          error && 'border-rose-400',
          className,
        )}
        {...props}
      />
      <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
    </div>
  )
}

/* ── Priority selector ── */
const priorities = [
  { value: 'Low',    color: 'text-zinc-600 border-zinc-200 bg-zinc-50',    dot: 'bg-zinc-400' },
  { value: 'Medium', color: 'text-amber-700 border-amber-200 bg-amber-50',  dot: 'bg-amber-500' },
  { value: 'High',   color: 'text-rose-700 border-rose-200 bg-rose-50',     dot: 'bg-rose-500' },
  { value: 'Urgent', color: 'text-rose-800 border-rose-300 bg-rose-100',    dot: 'bg-rose-600' },
]

function PriorityPicker({ value, onChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {priorities.map((p) => (
        <button
          key={p.value}
          type="button"
          onClick={() => onChange(p.value)}
          className={cn(
            'flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-semibold border transition-all',
            value === p.value
              ? `${p.color} ring-2 ring-offset-1 ring-current/30 scale-[1.02] shadow-sm`
              : 'border-border text-muted-foreground bg-background hover:bg-muted',
          )}
        >
          <span className={cn('w-2 h-2 rounded-full flex-shrink-0', p.dot)} />
          {p.value}
        </button>
      ))}
    </div>
  )
}

/* ── Attachment drop zone ── */
function AttachmentZone({ files, onAdd, onRemove }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    onAdd(Array.from(e.dataTransfer.files))
  }, [onAdd])

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-8 px-4 cursor-pointer transition-all',
          dragging ? 'border-primary/60 bg-primary/5' : 'border-border hover:border-primary/40 hover:bg-muted/40',
        )}
      >
        <div className="p-3 rounded-2xl bg-muted">
          <CloudArrowUpIcon className="w-6 h-6 text-muted-foreground" />
        </div>
        <p className="text-sm font-semibold text-foreground">
          {dragging ? 'Drop files here' : 'Drop files or click to browse'}
        </p>
        <p className="text-xs text-muted-foreground">PNG, JPG, PDF, ZIP, Excel, Word — max 10 MB each</p>
        <input ref={inputRef} type="file" multiple className="hidden"
          accept="image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv"
          onChange={(e) => { onAdd(Array.from(e.target.files)); e.target.value = '' }} />
      </div>
      <AnimatePresence initial={false}>
        {files.map((file) => (
          <motion.div
            key={file.name}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-muted/40"
          >
            <PaperClipIcon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <span className="text-sm font-medium flex-1 truncate">{file.name}</span>
            <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</span>
            <button type="button" onClick={() => onRemove(file.name)}
              className="p-1 rounded-lg text-muted-foreground hover:text-rose-500 transition-colors">
              <XMarkIcon className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

function ItemCard({ item, selected, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const lines = item.description ? item.description.split(' | ') : []
  return (
    <div
      onClick={() => onSelect(selected ? null : item.id)}
      className={cn(
        'rounded-xl border p-3 cursor-pointer transition-all',
        selected
          ? 'border-primary bg-primary/5 ring-1 ring-primary/40'
          : 'border-border hover:border-primary/30 hover:bg-muted/30',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground">{item.name}</p>
          {!expanded && lines[0] && (
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{lines[0]}</p>
          )}
          {expanded && (
            <div className="mt-1.5 space-y-0.5">
              {lines.map((l, i) => (
                <p key={i} className="text-xs text-muted-foreground">{l.trim()}</p>
              ))}
            </div>
          )}
        </div>
        {lines.length > 1 && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
            className="text-xs text-primary hover:underline flex-shrink-0 pt-0.5"
          >
            {expanded ? 'Thu gọn' : 'Xem thêm'}
          </button>
        )}
      </div>
    </div>
  )
}

function FormBlock({ step, title, description, icon: Icon, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden"
    >
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-muted/30">
        <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary text-primary-foreground text-xs font-bold flex-shrink-0">
          {step}
        </div>
        <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <div>
          <p className="text-sm font-bold text-foreground leading-tight">{title}</p>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      </div>
      <div className="px-6 py-5 space-y-5">
        {children}
      </div>
    </motion.div>
  )
}

/* ── Main page ── */
export default function NewTicketPage() {
  const navigate = useNavigate()
  const { state: navState } = useLocation()
  const { submit, loading, error } = useCreateTicket()
  const { user } = useAuthStore()
  const { isCustomer, isStaff, isAdmin } = useRole()

  // Org state
  const [orgs, setOrgs] = useState([])
  const [orgsLoading, setOrgsLoading] = useState(true)
  const [selectedOrgId, setSelectedOrgId] = useState(null)

  // Service state
  const [services, setServices] = useState([])
  const [servicesLoading, setServicesLoading] = useState(false)
  const [selectedServiceId, setSelectedServiceId] = useState(null)

  // Project state
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState(null)
  const [projectTasks, setProjectTasks] = useState([])
  const [projectTasksLoading, setProjectTasksLoading] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState(null)

  // Staff list for assignee picker (admin only)
  const [staffList, setStaffList] = useState([])
  const [assignmentMode, setAssignmentMode] = useState('auto')
  const [assigneeIds, setAssigneeIds] = useState([])

  // Form state
  const initialTicketType = TICKET_TYPES.includes(navState?.ticket_type)
    ? navState.ticket_type
    : ''
  const [form, setForm] = useState({
    subject:     navState?.subject     ?? '',
    description: navState?.description ?? '',
    priority:    'Medium',
    ticket_type: initialTicketType,
  })
  const [files, setFiles] = useState([])
  const [submitted, setSubmitted] = useState(false)
  const [errors, setErrors] = useState({})
  const [uploadError, setUploadError] = useState('')

  // Catalogue state (Change Request / Renewal)
  const [requestedItemId, setRequestedItemId] = useState(null)
  const [catalogueItems, setCatalogueItems] = useState([])
  const [catalogueLoading, setCatalogueLoading] = useState(false)

  // Load staff list for assignee dropdown (admin only)
  useEffect(() => {
    if (!isAdmin) return
    listUsers({ role: 'staff', per_page: 100 })
      .then((data) => {
        const items = Array.isArray(data) ? data : (data?.items ?? [])
        setStaffList(items)
      })
      .catch(() => {})
  }, [isCustomer])

  // Load orgs
  useEffect(() => {
    listOrganizations({ per_page: 200 })
      .then((data) => {
        const items = Array.isArray(data) ? data : (data?.items ?? [])
        setOrgs(items)
        // Pre-select: nav state, or customer's own org
        const preOrgId = navState?.org_id ?? (isCustomer ? user?.org_id : null)
        if (preOrgId) setSelectedOrgId(Number(preOrgId))
        else if (isCustomer && user?.org_id) setSelectedOrgId(user.org_id)
      })
      .finally(() => setOrgsLoading(false))
  }, [isCustomer, user?.org_id, navState?.org_id])

  // Load services when org changes
  useEffect(() => {
    if (!selectedOrgId) { setServices([]); setSelectedServiceId(null); return }
    setServicesLoading(true)
    setSelectedServiceId(null)
    getOrgServices(selectedOrgId)
      .then((data) => {
        setServices(data ?? [])
        // Pre-select service from nav state
        if (navState?.service_id) {
          const match = (data ?? []).find((s) => s.id === Number(navState.service_id))
          if (match) setSelectedServiceId(match.id)
        }
      })
      .finally(() => setServicesLoading(false))
  }, [selectedOrgId, navState?.service_id])

  // Load projects when org changes
  useEffect(() => {
    if (!selectedOrgId) { setProjects([]); setSelectedProjectId(null); return }
    setProjectsLoading(true)
    setSelectedProjectId(null)
    listProjects({ org_id: selectedOrgId, per_page: 100 })
      .then((data) => setProjects(data?.items ?? []))
      .catch(() => setProjects([]))
      .finally(() => setProjectsLoading(false))
  }, [selectedOrgId])

  // Load tasks when project changes
  useEffect(() => {
    if (!selectedProjectId) { setProjectTasks([]); setSelectedTaskId(null); return }
    setProjectTasksLoading(true)
    setSelectedTaskId(null)
    getProjectTasks(selectedProjectId)
      .then(data => setProjectTasks(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setProjectTasks([]))
      .finally(() => setProjectTasksLoading(false))
  }, [selectedProjectId])

  // Load hosting catalogue when ticket type requires item selection
  useEffect(() => {
    if (!CATALOGUE_TYPES.has(form.ticket_type)) {
      setRequestedItemId(null)
      return
    }
    setCatalogueLoading(true)
    listItems({ type: 'hosting' })
      .then((data) => setCatalogueItems(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setCatalogueItems([]))
      .finally(() => setCatalogueLoading(false))
  }, [form.ticket_type])

  const validate = () => {
    const e = {}
    if (!selectedOrgId)       e.org_id  = 'Please select an organization'
    if (!form.subject.trim()) e.subject = 'Subject is required'
    // Customers must select a ticket type and provide a description (service is optional)
    if (isCustomer) {
      if (!form.ticket_type)        e.ticket_type = 'Please select a ticket type'
      if (!form.description.trim()) e.description = 'Please describe your issue'
    }
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    try {
      const ticket = await submit({
        org_id: selectedOrgId,
        ...(selectedServiceId ? { service_id: selectedServiceId } : {}),
        ...(selectedProjectId ? { project_id: selectedProjectId } : {}),
        ...(selectedTaskId ? { task_id: selectedTaskId } : {}),
        ...(requestedItemId ? { requested_item_id: requestedItemId } : {}),
        ticket_type: form.ticket_type || 'Question',
        priority: form.priority,
        subject: form.subject,
        ...(form.description.trim() ? { description: form.description } : {}),
        ...(isAdmin ? {
          assignment_mode: assignmentMode,
          ...(assignmentMode === 'manual' && assigneeIds.length > 0
            ? { assignee_ids: assigneeIds.map(Number) }
            : {}),
        } : {}),
      })
      // Upload attachments after ticket created; surface backend validation errors.
      if (files.length > 0) {
        const results = await Promise.allSettled(files.map((f) => uploadAttachment(ticket.id, f)))
        const failed = results.find((result) => result.status === 'rejected')
        if (failed) {
          setUploadError(failed.reason?.message ?? 'Attachment upload failed')
          return
        }
      }
      setUploadError('')
      setSubmitted(true)
      setTimeout(() => navigate(`/tickets/${ticket.id}`), 600)
    } catch {}
  }

  const setField = (key) => (val) => setForm((f) => ({ ...f, [key]: val }))
  const clearErr  = (key) => setErrors((x) => ({ ...x, [key]: '' }))

  const requestService = useCallback(() => {
    setForm((f) => ({ ...f, subject: "I'd like to request a new service", ticket_type: 'Question' }))
  }, [])

  const selectedOrg = orgs.find((o) => o.id === selectedOrgId)

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <Link to="/tickets"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground mb-6 transition-colors group">
        <ArrowLeftIcon className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to tickets
      </Link>

      <motion.div className="mb-7" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-display font-bold text-2xl lg:text-3xl text-foreground tracking-tight">
          Create Support Ticket
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Fill in the details below and our team will get back to you as soon as possible.
        </p>
      </motion.div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden"
        >
          <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-muted/30">
            <DocumentTextIcon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <p className="text-sm font-bold text-foreground">Ticket Details</p>
          </div>

          <div className="px-6 py-5 space-y-5">
            {/* 2-col grid: left = Subject; right = all selectors */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* LEFT: Subject */}
              <div className="flex flex-col gap-5">
                <Field label="Subject" required error={errors.subject}>
                  <StyledInput
                    placeholder="e.g. Cannot access admin panel after update"
                    value={form.subject}
                    onChange={(e) => { setField('subject')(e.target.value); clearErr('subject') }}
                  />
                </Field>
              </div>

              {/* RIGHT: all picker fields */}
              <div className="space-y-4">

                {/* Organization */}
                <Field label="Organization" required error={errors.org_id}>
                  {isCustomer ? (
                    <StyledInput
                      value={orgsLoading ? 'Loading…' : (selectedOrg?.name ?? user?.org_id ?? '')}
                      disabled
                      className="bg-muted/40"
                    />
                  ) : (
                    <StyledSelect
                      value={selectedOrgId ?? ''}
                      onChange={(e) => { setSelectedOrgId(Number(e.target.value) || null); clearErr('org_id') }}
                      disabled={orgsLoading}
                      error={errors.org_id}
                    >
                      <option value="">{orgsLoading ? 'Loading…' : 'Select organization'}</option>
                      {orgs.map((o) => (
                        <option key={o.id} value={o.id}>{o.name}{o.code ? ` (${o.code})` : ''}</option>
                      ))}
                    </StyledSelect>
                  )}
                </Field>

                {/* Service */}
                <Field label="Service" hint="Optional — select the service related to your issue" error={errors.service_id}>
                  {services.length === 0 && !servicesLoading && selectedOrgId ? (
                    <p className="text-sm text-muted-foreground">
                      No active services on this account yet.{' '}
                      <button type="button" onClick={requestService} className="text-amber-600 hover:text-amber-700 font-medium">
                        + Request one
                      </button>
                    </p>
                  ) : (
                    <StyledSelect
                      value={selectedServiceId ?? ''}
                      onChange={(e) => { setSelectedServiceId(Number(e.target.value) || null); clearErr('service_id') }}
                      disabled={!selectedOrgId || servicesLoading}
                      error={errors.service_id}
                    >
                      <option value="">
                        {!selectedOrgId ? 'Select an organization first' :
                         servicesLoading ? 'Loading services…' :
                         '— Không chọn —'}
                      </option>
                      {services.map((s) => {
                        const typeLabel = SERVICE_TYPE_BADGE[s.type]?.label ?? s.type
                        const statusLabel = s.status ? ` — ${s.status.replace('_', ' ')}` : ''
                        return (
                          <option key={s.id} value={s.id}>[{typeLabel}] {s.name}{statusLabel}</option>
                        )
                      })}
                    </StyledSelect>
                  )}
                  {selectedServiceId && (() => {
                    const svc = services.find((s) => s.id === selectedServiceId)
                    return svc ? <ServicePreviewCard service={svc} /> : null
                  })()}
                </Field>

                {/* Project + Task */}
                {projects.length > 0 && (
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Project" hint="Optional">
                      <StyledSelect
                        value={selectedProjectId ?? ''}
                        onChange={(e) => setSelectedProjectId(Number(e.target.value) || null)}
                        disabled={projectsLoading}
                      >
                        <option value="">{projectsLoading ? 'Loading…' : 'None'}</option>
                        {projects.map((p) => (
                          <option key={p.id} value={p.id}>{p.name}</option>
                        ))}
                      </StyledSelect>
                    </Field>
                    <Field label="Task" hint="Optional">
                      <StyledSelect
                        value={selectedTaskId ?? ''}
                        onChange={(e) => setSelectedTaskId(Number(e.target.value) || null)}
                        disabled={!selectedProjectId || projectTasksLoading}
                      >
                        <option value="">{projectTasksLoading ? 'Loading…' : 'None'}</option>
                        {projectTasks.map((t) => (
                          <option key={t.id} value={t.id}>{t.title}</option>
                        ))}
                      </StyledSelect>
                    </Field>
                  </div>
                )}

                {/* Type + Priority */}
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Ticket Type" required={isCustomer} error={errors.ticket_type}>
                    <StyledSelect
                      value={form.ticket_type}
                      onChange={(e) => { setField('ticket_type')(e.target.value); clearErr('ticket_type') }}
                      error={errors.ticket_type}
                    >
                      <option value="">Select type</option>
                      {TICKET_TYPES.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </StyledSelect>
                  </Field>

                  <Field label="Priority">
                    <StyledSelect
                      value={form.priority}
                      onChange={(e) => setField('priority')(e.target.value)}
                    >
                      {priorities.map((p) => (
                        <option key={p.value} value={p.value}>{p.value}</option>
                      ))}
                    </StyledSelect>
                  </Field>
                </div>

                {/* Hosting catalogue — shown for Change Request / Renewal */}
                <AnimatePresence>
                  {CATALOGUE_TYPES.has(form.ticket_type) && (
                    <motion.div
                      key="catalogue"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Field label="Gói hosting muốn chuyển / gia hạn" hint="Tùy chọn — chọn gói nếu có">
                        {catalogueLoading ? (
                          <p className="text-sm text-muted-foreground">Đang tải danh sách gói…</p>
                        ) : catalogueItems.length === 0 ? (
                          <p className="text-sm text-muted-foreground">Không có gói nào.</p>
                        ) : (
                          <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                            {catalogueItems.map((item) => (
                              <ItemCard
                                key={item.id}
                                item={item}
                                selected={requestedItemId === item.id}
                                onSelect={setRequestedItemId}
                              />
                            ))}
                          </div>
                        )}
                      </Field>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Assignment mode (admin only) — 3-button toggle */}
                {isAdmin && (
                  <div className="space-y-3">
                    <Field label="Assignment Mode">
                      <div className="flex gap-1 bg-muted rounded-lg p-1">
                        {[
                          { value: 'none', label: 'None' },
                          { value: 'auto', label: 'Auto' },
                          { value: 'manual', label: 'Manual' },
                        ].map(({ value, label }) => (
                          <button
                            key={value}
                            type="button"
                            onClick={() => { setAssignmentMode(value); if (value !== 'manual') setAssigneeIds([]) }}
                            className={cn(
                              'flex-1 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors',
                              assignmentMode === value
                                ? 'bg-white shadow text-foreground'
                                : 'text-muted-foreground hover:text-foreground',
                            )}
                          >
                            {label}
                          </button>
                        ))}
                      </div>
                    </Field>

                    {assignmentMode === 'manual' && (
                      <Field label="Assignees" hint="Select one or more staff members">
                        <div className="max-h-36 overflow-y-auto border border-border rounded-lg divide-y divide-border">
                          {staffList.length === 0 && (
                            <p className="px-3 py-2 text-xs text-muted-foreground">No staff available</p>
                          )}
                          {staffList.map((s) => (
                            <label key={s.id} className="flex items-center gap-2.5 px-3 py-2 hover:bg-muted/50 cursor-pointer">
                              <input
                                type="checkbox"
                                value={s.id}
                                checked={assigneeIds.includes(String(s.id))}
                                onChange={(e) => {
                                  const sid = String(s.id)
                                  setAssigneeIds((prev) =>
                                    e.target.checked ? [...prev, sid] : prev.filter((x) => x !== sid)
                                  )
                                }}
                                className="accent-primary"
                              />
                              <span className="text-sm text-foreground">{s.full_name}</span>
                              <span className="text-xs text-muted-foreground ml-auto">{s.email}</span>
                            </label>
                          ))}
                        </div>
                      </Field>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Description — full width, 4 rows */}
            <Field label="Description" required={isCustomer} error={errors.description}
              hint={isCustomer ? "Include steps to reproduce, error messages, device info, and when the issue started." : "Optional — describe the issue if needed"}>
              <StyledTextarea
                placeholder="Describe the issue in detail — include error messages, affected device, time of occurrence…"
                value={form.description}
                onChange={(e) => { setField('description')(e.target.value); clearErr('description') }}
                rows={4}
              />
            </Field>

            {/* Attachments */}
            <AttachmentZone
              files={files}
              onAdd={(newFiles) => setFiles((f) => {
                const names = new Set(f.map((x) => x.name))
                return [...f, ...newFiles.filter((x) => !names.has(x.name))]
              })}
              onRemove={(name) => setFiles((f) => f.filter((x) => x.name !== name))}
            />
            {uploadError && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm">
                <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
                {uploadError}
              </div>
            )}
          </div>
        </motion.div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm"
            >
              <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-3 pt-1">
          <Button type="submit" disabled={loading || submitted}
            className={cn('gap-2 min-w-[140px]', submitted && 'bg-emerald-600 hover:bg-emerald-600')}>
            {submitted ? (
              <><CheckCircleIcon className="w-4 h-4" /> Submitted!</>
            ) : loading ? (
              <><Spinner className="w-4 h-4" /> Submitting…</>
            ) : (
              'Submit Ticket'
            )}
          </Button>
          <Link to="/tickets">
            <Button type="button" variant="ghost" className="text-muted-foreground">Cancel</Button>
          </Link>
        </div>

      </form>
    </div>
  )
}
