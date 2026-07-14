import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowLeftIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'

import { uploadAttachment } from '@/api/attachments'
import { listItems } from '@/api/items'
import { getOrgServices, listOrganizations } from '@/api/organizations'
import { getProjectTasks, listProjects } from '@/api/projects'
import { listUsers } from '@/api/users'
import {
  AssignmentModePicker,
  CatalogueItemPicker,
  ServicePreview,
  TicketAttachmentPicker,
  TicketPriorityPicker,
} from '@/components/tickets/TicketFormControls'
import {
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  FormActions,
  FormField,
  Input,
  PageContainer,
  PageHeader,
  Select,
  Spinner,
  Textarea,
} from '@/components/ui'
import { useAuthStore } from '@/hooks/useAuth'
import { useRole } from '@/hooks/useRole'
import { useCreateTicket } from '@/hooks/useTickets'

const TICKET_TYPES = [
  'Question', 'Bug', 'Incident', 'Task Request', 'Change Request',
  'Feature Request', 'Content Request', 'SEO Request',
  'Approval Required', 'Complaint', 'Renewal', 'Other',
]
const CATALOGUE_TYPES = new Set(['Change Request', 'Renewal'])
const MAX_FILE_SIZE = 10 * 1024 * 1024

export default function NewTicketPage() {
  const navigate = useNavigate()
  const { state: navState } = useLocation()
  const { submit, loading, error } = useCreateTicket()
  const { user } = useAuthStore()
  const { isCustomer, isAdmin } = useRole()
  const submittingRef = useRef(false)

  const [orgs, setOrgs] = useState([])
  const [orgsLoading, setOrgsLoading] = useState(true)
  const [selectedOrgId, setSelectedOrgId] = useState(null)
  const [services, setServices] = useState([])
  const [servicesLoading, setServicesLoading] = useState(false)
  const [selectedServiceId, setSelectedServiceId] = useState(null)
  const [projects, setProjects] = useState([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [selectedProjectId, setSelectedProjectId] = useState(null)
  const [projectTasks, setProjectTasks] = useState([])
  const [projectTasksLoading, setProjectTasksLoading] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState(null)
  const [staffList, setStaffList] = useState([])
  const [assignmentMode, setAssignmentMode] = useState('auto')
  const [assigneeIds, setAssigneeIds] = useState([])

  const initialTicketType = TICKET_TYPES.includes(navState?.ticket_type) ? navState.ticket_type : ''
  const [form, setForm] = useState({
    subject: navState?.subject ?? '',
    description: navState?.description ?? '',
    priority: 'Medium',
    ticket_type: initialTicketType,
  })
  const [files, setFiles] = useState([])
  const [errors, setErrors] = useState({})
  const [fileError, setFileError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [createdTicketId, setCreatedTicketId] = useState(null)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [requestedItemId, setRequestedItemId] = useState(null)
  const [catalogueItems, setCatalogueItems] = useState([])
  const [catalogueLoading, setCatalogueLoading] = useState(false)

  useEffect(() => {
    if (!isAdmin) return
    listUsers({ role: 'staff', per_page: 100 })
      .then((data) => setStaffList(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setStaffList([]))
  }, [isAdmin])

  useEffect(() => {
    let active = true
    listOrganizations({ per_page: 200 })
      .then((data) => {
        if (!active) return
        const items = Array.isArray(data) ? data : (data?.items ?? [])
        setOrgs(items)
        const preselectedId = navState?.org_id ?? (isCustomer ? user?.org_id : null)
        if (preselectedId) setSelectedOrgId(Number(preselectedId))
      })
      .catch(() => { if (active) setOrgs([]) })
      .finally(() => { if (active) setOrgsLoading(false) })
    return () => { active = false }
  }, [isCustomer, navState?.org_id, user?.org_id])

  useEffect(() => {
    setSelectedServiceId(null)
    if (!selectedOrgId) {
      setServices([])
      return
    }
    let active = true
    setServicesLoading(true)
    getOrgServices(selectedOrgId)
      .then((data) => {
        if (!active) return
        const nextServices = data ?? []
        setServices(nextServices)
        const preselected = nextServices.find((service) => service.id === Number(navState?.service_id))
        if (preselected) setSelectedServiceId(preselected.id)
      })
      .catch(() => { if (active) setServices([]) })
      .finally(() => { if (active) setServicesLoading(false) })
    return () => { active = false }
  }, [navState?.service_id, selectedOrgId])

  useEffect(() => {
    setSelectedProjectId(null)
    setSelectedTaskId(null)
    if (!selectedOrgId) {
      setProjects([])
      return
    }
    let active = true
    setProjectsLoading(true)
    listProjects({ org_id: selectedOrgId, per_page: 100 })
      .then((data) => { if (active) setProjects(data?.items ?? []) })
      .catch(() => { if (active) setProjects([]) })
      .finally(() => { if (active) setProjectsLoading(false) })
    return () => { active = false }
  }, [selectedOrgId])

  useEffect(() => {
    setSelectedTaskId(null)
    if (!selectedProjectId) {
      setProjectTasks([])
      return
    }
    let active = true
    setProjectTasksLoading(true)
    getProjectTasks(selectedProjectId)
      .then((data) => { if (active) setProjectTasks(Array.isArray(data) ? data : (data?.items ?? [])) })
      .catch(() => { if (active) setProjectTasks([]) })
      .finally(() => { if (active) setProjectTasksLoading(false) })
    return () => { active = false }
  }, [selectedProjectId])

  useEffect(() => {
    if (!CATALOGUE_TYPES.has(form.ticket_type)) {
      setRequestedItemId(null)
      return
    }
    let active = true
    setCatalogueLoading(true)
    listItems({ type: 'hosting' })
      .then((data) => { if (active) setCatalogueItems(Array.isArray(data) ? data : (data?.items ?? [])) })
      .catch(() => { if (active) setCatalogueItems([]) })
      .finally(() => { if (active) setCatalogueLoading(false) })
    return () => { active = false }
  }, [form.ticket_type])

  const isDirty = useMemo(() => Boolean(
    form.subject.trim()
    || form.description.trim()
    || form.ticket_type
    || (!isCustomer && selectedOrgId)
    || selectedServiceId
    || selectedProjectId
    || files.length,
  ), [files.length, form.description, form.subject, form.ticket_type, isCustomer, selectedOrgId, selectedProjectId, selectedServiceId])

  useEffect(() => {
    const handleBeforeUnload = (event) => {
      if (!isDirty || submitted || createdTicketId) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [createdTicketId, isDirty, submitted])

  const validate = () => {
    const nextErrors = {}
    if (!form.subject.trim()) nextErrors.subject = 'Subject is required'
    if (!selectedOrgId) nextErrors.org_id = 'Please select an organization'
    if (isCustomer && !form.ticket_type) nextErrors.ticket_type = 'Please select a ticket type'
    if (isCustomer && !form.description.trim()) nextErrors.description = 'Please describe your issue'
    return nextErrors
  }

  const focusFirstError = (nextErrors) => {
    const order = ['subject', 'org_id', 'ticket_type', 'description']
    const firstKey = order.find((key) => nextErrors[key])
    if (firstKey) requestAnimationFrame(() => document.getElementById('ticket-' + firstKey)?.focus())
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (submittingRef.current || loading || submitted || createdTicketId) return
    const nextErrors = validate()
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors)
      focusFirstError(nextErrors)
      return
    }

    submittingRef.current = true
    setUploadError('')
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
      setCreatedTicketId(ticket.id)
      if (files.length > 0) {
        const results = await Promise.allSettled(files.map((file) => uploadAttachment(ticket.id, file)))
        const failedCount = results.filter((result) => result.status === 'rejected').length
        if (failedCount > 0) {
          setUploadError(
            'Ticket #' + ticket.id + ' was created, but ' + failedCount + ' attachment'
            + (failedCount > 1 ? 's' : '') + ' could not be uploaded.',
          )
          return
        }
      }
      setSubmitted(true)
      window.setTimeout(() => navigate('/tickets/' + ticket.id), 450)
    } catch {
      submittingRef.current = false
    }
  }

  const updateField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: '' }))
  }

  const addFiles = useCallback((newFiles) => {
    const oversized = newFiles.filter((file) => file.size > MAX_FILE_SIZE)
    setFileError(oversized.length > 0 ? 'Each attachment must be 10 MB or smaller.' : '')
    const accepted = newFiles.filter((file) => file.size <= MAX_FILE_SIZE)
    setFiles((current) => {
      const existing = new Set(current.map((file) => file.name + '-' + file.size))
      return [...current, ...accepted.filter((file) => !existing.has(file.name + '-' + file.size))]
    })
  }, [])

  const requestService = useCallback(() => {
    setForm((current) => ({ ...current, subject: "I'd like to request a new service", ticket_type: 'Question' }))
    setErrors((current) => ({ ...current, subject: '', ticket_type: '' }))
  }, [])

  const selectedOrg = orgs.find((organization) => organization.id === selectedOrgId)
  const selectedService = services.find((service) => service.id === selectedServiceId)
  const submitDisabled = loading || submitted || Boolean(createdTicketId)

  return (
    <PageContainer className="max-w-[900px] pb-8">
      <button
        type="button"
        onClick={() => isDirty && !submitted && !createdTicketId ? setCancelOpen(true) : navigate('/tickets')}
        className="mb-4 inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-secondary-foreground hover:text-foreground"
      >
        <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
        Back to tickets
      </button>

      <PageHeader
        title="Create Support Ticket"
        description="Provide the details our support team needs to route and resolve the request."
      />

      <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-5">
        <Card className="-mx-4 rounded-none border-x-0 shadow-none sm:mx-0 sm:rounded-lg sm:border-x sm:shadow-sm">
          <CardContent className="space-y-6 p-4 sm:p-6">
            <FormField label="Subject" required error={errors.subject} id="ticket-subject">
              <Input
                value={form.subject}
                className="min-h-11 sm:min-h-9"
                placeholder="e.g. Cannot access admin panel after update"
                onChange={(event) => updateField('subject', event.target.value)}
              />
            </FormField>

            <section className="grid gap-4 border-t border-border pt-6 sm:grid-cols-2" aria-labelledby="ticket-context-heading">
              <h2 id="ticket-context-heading" className="col-span-full text-sm font-semibold text-foreground">Organization and service</h2>
              <FormField label="Organization" required error={errors.org_id} id="ticket-org_id">
                {isCustomer ? (
                  <Input value={orgsLoading ? 'Loading...' : (selectedOrg?.name ?? '')} disabled />
                ) : (
                  <Select
                    className="min-h-11 sm:min-h-9"
                    value={selectedOrgId ?? ''}
                    disabled={orgsLoading}
                    onChange={(event) => {
                      setSelectedOrgId(Number(event.target.value) || null)
                      setErrors((current) => ({ ...current, org_id: '' }))
                    }}
                  >
                    <option value="">{orgsLoading ? 'Loading...' : 'Select organization'}</option>
                    {orgs.map((organization) => (
                      <option key={organization.id} value={organization.id}>
                        {organization.name}{organization.code ? ' (' + organization.code + ')' : ''}
                      </option>
                    ))}
                  </Select>
                )}
              </FormField>

              <FormField label="Service" helperText="Optional. Select the service related to this request." id="ticket-service_id">
                <Select
                  className="min-h-11 sm:min-h-9"
                  value={selectedServiceId ?? ''}
                  disabled={!selectedOrgId || servicesLoading || services.length === 0}
                  onChange={(event) => setSelectedServiceId(Number(event.target.value) || null)}
                >
                  <option value="">
                    {!selectedOrgId ? 'Select an organization first' : servicesLoading ? 'Loading services...' : 'No service selected'}
                  </option>
                  {services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
                </Select>
              </FormField>

              {selectedOrgId && !servicesLoading && services.length === 0 && (
                <p className="col-span-full text-sm text-secondary-foreground">
                  No active services on this account.{' '}
                  <button type="button" onClick={requestService} className="font-medium text-primary hover:underline">Request a new service</button>
                </p>
              )}
              {selectedService && <div className="col-span-full"><ServicePreview service={selectedService} /></div>}
            </section>

            <section className="grid gap-5 border-t border-border pt-6 sm:grid-cols-2" aria-labelledby="ticket-classification-heading">
              <h2 id="ticket-classification-heading" className="col-span-full text-sm font-semibold text-foreground">Request classification</h2>
              <FormField label="Ticket type" required={isCustomer} error={errors.ticket_type} id="ticket-ticket_type">
                <Select value={form.ticket_type} onChange={(event) => updateField('ticket_type', event.target.value)}>
                  <option value="">Select type</option>
                  {TICKET_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                </Select>
              </FormField>
              <FormField label="Priority" id="ticket-priority" className="sm:col-span-2">
                <TicketPriorityPicker value={form.priority} onChange={(value) => updateField('priority', value)} />
              </FormField>
            </section>

            <FormField
              label="Description"
              required={isCustomer}
              error={errors.description}
              helperText={isCustomer ? 'Include steps to reproduce, error messages, affected device and when the issue started.' : 'Optional. Add context the support team will need.'}
              id="ticket-description"
            >
              <Textarea
                rows={7}
                value={form.description}
                placeholder="Describe the issue in detail..."
                onChange={(event) => updateField('description', event.target.value)}
              />
            </FormField>

            {CATALOGUE_TYPES.has(form.ticket_type) && (
              <FormField label="Hosting plan" helperText="Optional. Select the plan to change or renew.">
                <CatalogueItemPicker
                  items={catalogueItems}
                  selectedId={requestedItemId}
                  onChange={setRequestedItemId}
                  loading={catalogueLoading}
                />
              </FormField>
            )}

            <section className="border-t border-border pt-6" aria-labelledby="ticket-attachments-heading">
              <h2 id="ticket-attachments-heading" className="mb-1 text-sm font-semibold text-foreground">Attachments</h2>
              <p className="mb-3 text-xs text-secondary-foreground">Optional supporting screenshots or documents.</p>
              <TicketAttachmentPicker
                files={files}
                onAdd={addFiles}
                onRemove={(name) => setFiles((current) => current.filter((file) => file.name !== name))}
                error={fileError}
              />
            </section>

            {isAdmin && (
              <section className="border-t border-border pt-6" aria-labelledby="ticket-assignment-heading">
                <h2 id="ticket-assignment-heading" className="mb-3 text-sm font-semibold text-foreground">Assignment</h2>
                <AssignmentModePicker
                  value={assignmentMode}
                  onChange={(value) => {
                    setAssignmentMode(value)
                    if (value !== 'manual') setAssigneeIds([])
                  }}
                  staff={staffList}
                  assigneeIds={assigneeIds}
                  onAssigneesChange={setAssigneeIds}
                />
              </section>
            )}

            {projects.length > 0 && (
              <section className="grid gap-4 border-t border-border pt-6 sm:grid-cols-2" aria-labelledby="ticket-related-heading">
                <h2 id="ticket-related-heading" className="col-span-full text-sm font-semibold text-foreground">Related work</h2>
                <FormField label="Project" helperText="Optional">
                  <Select
                    className="min-h-11 sm:min-h-9"
                    value={selectedProjectId ?? ''}
                    disabled={projectsLoading}
                    onChange={(event) => setSelectedProjectId(Number(event.target.value) || null)}
                  >
                    <option value="">{projectsLoading ? 'Loading...' : 'No project selected'}</option>
                    {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                  </Select>
                </FormField>
                <FormField label="Task" helperText="Optional">
                  <Select
                    className="min-h-11 sm:min-h-9"
                    value={selectedTaskId ?? ''}
                    disabled={!selectedProjectId || projectTasksLoading}
                    onChange={(event) => setSelectedTaskId(Number(event.target.value) || null)}
                  >
                    <option value="">{projectTasksLoading ? 'Loading...' : 'No task selected'}</option>
                    {projectTasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}
                  </Select>
                </FormField>
              </section>
            )}
          </CardContent>
        </Card>

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-md border border-danger/25 bg-danger-muted p-3 text-sm text-danger">
            <ExclamationCircleIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            {error}
          </div>
        )}

        {uploadError && (
          <div role="alert" className="rounded-md border border-warning/30 bg-warning-muted p-3 text-sm text-foreground">
            <p>{uploadError}</p>
            <Link to={'/tickets/' + createdTicketId} className="mt-2 inline-flex font-semibold text-primary hover:underline">Open created ticket</Link>
          </div>
        )}

        <FormActions className="pb-2">
          <Button
            type="button"
            variant="outline"
            className="min-h-11 w-full sm:min-h-9 sm:w-auto"
            onClick={() => isDirty && !submitted && !createdTicketId ? setCancelOpen(true) : navigate('/tickets')}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={submitDisabled} className="min-h-11 w-full sm:min-h-9 sm:w-auto sm:min-w-36">
            {submitted ? (
              <><CheckCircleIcon className="h-4 w-4" aria-hidden="true" /> Submitted</>
            ) : loading ? (
              <><Spinner className="h-4 w-4" label="Submitting ticket" /> Submitting...</>
            ) : createdTicketId ? 'Ticket created' : 'Submit Ticket'}
          </Button>
        </FormActions>
      </form>

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        onConfirm={() => navigate('/tickets')}
        title="Discard ticket draft?"
        description="Your unsaved ticket details and selected attachments will be lost."
        confirmLabel="Discard draft"
        destructive
      />
    </PageContainer>
  )
}
