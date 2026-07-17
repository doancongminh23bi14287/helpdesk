import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import {
  ArrowPathIcon,
  ArchiveBoxIcon,
  ArrowUturnLeftIcon,
  CubeIcon,
  DocumentTextIcon,
  EllipsisVerticalIcon,
  ExclamationTriangleIcon,
  GlobeAltIcon,
  PencilSquareIcon,
  ServerStackIcon,
  SparklesIcon,
  TrashIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'

import { deleteServicePermanently, archiveService, listServices, restoreService, updateService } from '@/api/services'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { useRole } from '@/hooks/useRole'
import {
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  EmptyState,
  FormField,
  Input,
  LoadingState,
  Modal,
  PageHeader,
  PageShell,
  Select,
  StatusBadge,
} from '@/components/ui'
import { TypeBadge } from '@/components/TypeBadge'
import { cn, daysUntil, formatDate } from '@/lib/utils'

const TYPE_CONFIG = {
  saas:    { label: 'SaaS',    icon: SparklesIcon,          color: 'bg-amber-100 text-amber-700' },
  hosting: { label: 'Hosting', icon: ServerStackIcon,       color: 'bg-cyan-100 text-cyan-700' },
  domain:  { label: 'Domain',  icon: GlobeAltIcon,          color: 'bg-purple-100 text-purple-700' },
  support: { label: 'Support', icon: WrenchScrewdriverIcon, color: 'bg-orange-100 text-orange-700' },
  other:   { label: 'Other',   icon: CubeIcon,              color: 'bg-slate-100 text-slate-600' },
}

const FILTERS = [
  { key: 'active', label: 'Active' },
  { key: 'archived', label: 'Archived' },
  { key: 'all', label: 'All' },
]

function formatCurrency(value) {
  if (value == null || Number.isNaN(Number(value)) || Number(value) <= 0) return null
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(Number(value))
}

function resolveServiceStatus(service) {
  if (service.is_archived) return 'archived'
  if (service.status === 'past_due') return 'past_due'
  if (service.status === 'cancelled') return 'cancelled'
  const remaining = daysUntil(service.expiry_date)
  if (remaining !== null && remaining < 0) return 'expired'
  return service.status || 'inactive'
}

function ExpiryChip({ dateStr }) {
  const days = daysUntil(dateStr)
  if (days === null || days < 0) return null
  if (days <= 7) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
        <ExclamationTriangleIcon className="h-3 w-3" aria-hidden="true" />
        {days === 0 ? 'Expires today' : `${days}d left`}
      </span>
    )
  }
  if (days <= 30) {
    return <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">{days}d left</span>
  }
  return <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">Expires {formatDate(dateStr)}</span>
}

function ServiceCard({ service, isAdmin, onEdit, onArchive, onRestore, onDelete, onRenewal }) {
  const cfg = TYPE_CONFIG[service.type] ?? TYPE_CONFIG.other
  const Icon = cfg.icon
  const displayStatus = resolveServiceStatus(service)
  const remaining = daysUntil(service.expiry_date)
  const showExpiry = !service.is_archived && service.expiry_date && remaining !== null && remaining >= 0 && remaining <= 30

  return (
    <Card className="relative overflow-visible rounded-2xl border-border shadow-sm transition-shadow hover:shadow-md">
      <CardContent className="p-5">
        <div className="absolute right-3 top-3">
          {isAdmin ? (
            <ServiceActionMenu
              service={service}
              onEdit={onEdit}
              onArchive={onArchive}
              onRestore={onRestore}
              onDelete={onDelete}
            />
          ) : null}
        </div>

        <div className="flex items-start gap-4 pr-10">
          <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl', cfg.color.split(' ')[0])}>
            <Icon className={cn('h-5 w-5', cfg.color.split(' ')[1])} aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start gap-2 pr-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-semibold text-foreground">{service.name}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <StatusBadge status={displayStatus} />
                  <TypeBadge type={service.type} />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-4 space-y-3 border-t border-border pt-4">
          {service.domain && (
            <div>
              <p className="text-xs text-secondary-foreground">Domain</p>
              <p className="mt-0.5 truncate text-sm font-semibold text-foreground">{service.domain}</p>
            </div>
          )}

          {service.monthly_cost != null && Number(service.monthly_cost) > 0 && (
            <div>
              <p className="text-xs text-secondary-foreground">Monthly cost</p>
              <p className="mt-0.5 text-sm font-semibold text-foreground">{formatCurrency(service.monthly_cost)}</p>
            </div>
          )}

          {service.disk_usage && (
            <div>
              <p className="mb-1 text-xs text-secondary-foreground">Disk usage</p>
              <DiskBar usage={service.disk_usage} />
            </div>
          )}

          {showExpiry && <ExpiryChip dateStr={service.expiry_date} />}

          {!service.is_archived ? (
            <button
              type="button"
              onClick={() => onRenewal(service)}
              className="mt-2 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-gray-900 px-3 text-sm font-semibold text-white transition-colors hover:bg-gray-800"
            >
              <ArrowPathIcon className="h-4 w-4" aria-hidden="true" />
              Request renewal
            </button>
          ) : (
            <p className="rounded-lg border border-dashed border-border px-3 py-2 text-xs text-secondary-foreground">
              Archived services stay in history and can be restored from the action menu.
            </p>
          )}

          <Link
            to="/invoices"
            className="mt-2 flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm font-medium text-secondary-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
          >
            <DocumentTextIcon className="h-4 w-4" aria-hidden="true" />
            View invoices
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}

function DiskBar({ usage }) {
  if (!usage) return null
  const match = usage.match(/([\d.]+)\s*\w+\s*\/\s*([\d.]+)/)
  if (!match) return <p className="text-sm font-semibold text-foreground">{usage}</p>
  const pct = Math.min(100, Math.round((parseFloat(match[1]) / parseFloat(match[2])) * 100))
  const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-cyan-500'
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs text-secondary-foreground">Disk usage</span>
        <span className="text-xs font-semibold text-foreground">{usage}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function ServiceActionMenu({ service, onEdit, onArchive, onRestore, onDelete }) {
  const canRestore = Boolean(service.is_archived)
  const canDelete = Boolean(service.can_hard_delete)
  const actionClassName = 'flex min-h-11 w-full cursor-pointer select-none items-center gap-2.5 rounded-lg px-3.5 py-2.5 text-left text-sm font-medium text-foreground outline-none transition-colors data-[highlighted]:bg-surface-muted data-[highlighted]:text-foreground focus-visible:ring-2 focus-visible:ring-ring'

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type='button'
          aria-label={'Actions for ' + service.name}
          className='-mr-1 -mt-1 inline-flex h-11 w-11 items-center justify-center rounded-md text-secondary-foreground transition-colors hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=open]:bg-surface-muted data-[state=open]:text-foreground sm:h-9 sm:w-9'
        >
          <EllipsisVerticalIcon className='h-4 w-4' aria-hidden='true' />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align='end'
          side='bottom'
          sideOffset={8}
          collisionPadding={8}
          className='z-[100] max-h-[calc(100dvh-1rem)] w-[min(17rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-border p-1.5 text-foreground shadow-md backdrop-blur-md'
          style={{ backgroundColor: 'hsl(var(--surface) / 0.94)' }}
        >
          <DropdownMenu.Item className={actionClassName} onSelect={() => onEdit(service)}>
            <PencilSquareIcon className='h-4 w-4 shrink-0 text-secondary-foreground' aria-hidden='true' />
            <span>Edit service</span>
          </DropdownMenu.Item>

          {canRestore ? (
            <DropdownMenu.Item className={actionClassName} onSelect={() => onRestore(service)}>
              <ArrowUturnLeftIcon className='h-4 w-4 shrink-0 text-secondary-foreground' aria-hidden='true' />
              <span>Restore service</span>
            </DropdownMenu.Item>
          ) : (
            <DropdownMenu.Item className={actionClassName} onSelect={() => onArchive(service)}>
              <ArchiveBoxIcon className='h-4 w-4 shrink-0 text-secondary-foreground' aria-hidden='true' />
              <span>Archive service</span>
            </DropdownMenu.Item>
          )}

          <DropdownMenu.Separator className='my-1.5 h-px bg-border' />

          {canDelete ? (
            <DropdownMenu.Item
              className={cn(actionClassName, 'text-danger data-[highlighted]:bg-danger/10 data-[highlighted]:text-danger')}
              onSelect={() => onDelete(service)}
            >
              <TrashIcon className='h-4 w-4 shrink-0' aria-hidden='true' />
              <span>Delete permanently</span>
            </DropdownMenu.Item>
          ) : (
            <div
              className='flex gap-2.5 rounded-lg border border-warning/20 bg-warning-muted/70 px-3 py-2.5 text-secondary-foreground'
              role='note'
            >
              <ExclamationTriangleIcon className='mt-0.5 h-4 w-4 shrink-0 text-warning' aria-hidden='true' />
              <p className='text-xs leading-5'>
                Service này đã có dữ liệu liên quan nên không thể xóa vĩnh viễn. Bạn vẫn có thể lưu trữ.
              </p>
            </div>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}

function ServiceEditModal({ service, open, onClose, onSave, saving }) {
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!service) return
    setForm({
      name: service.name ?? '',
      type: service.type ?? 'saas',
      domain: service.domain ?? '',
      expiry_date: service.expiry_date ?? '',
      disk_usage: service.disk_usage ?? '',
      monthly_cost: service.monthly_cost == null ? '' : String(service.monthly_cost),
      billing_cycle: service.billing_cycle ?? 'monthly',
    })
    setError('')
  }, [service])

  if (!service || !form) return null

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    try {
      await onSave(service.id, {
        name: form.name.trim(),
        type: form.type,
        domain: form.domain.trim() || null,
        expiry_date: form.expiry_date || null,
        disk_usage: form.disk_usage.trim() || null,
        monthly_cost: form.monthly_cost === '' ? null : Number(form.monthly_cost),
        billing_cycle: form.billing_cycle,
      })
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to update service')
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Edit service"
      description="Update service metadata used across tickets, billing, and the catalog."
      size="lg"
      footer={(
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" form="service-edit-form" isLoading={saving} loadingText="Saving">
            Save changes
          </Button>
        </div>
      )}
    >
      <form id="service-edit-form" className="space-y-4" onSubmit={submit}>
        {error && <p className="rounded-lg border border-danger/20 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
        <FormField label="Service name" required id="service-name">
          <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} />
        </FormField>
        <div className="grid gap-4 md:grid-cols-2">
          <FormField label="Type" id="service-type">
            <Select value={form.type} onChange={(event) => setForm((current) => ({ ...current, type: event.target.value }))}>
              {Object.entries(TYPE_CONFIG).map(([value, cfg]) => (
                <option key={value} value={value}>{cfg.label}</option>
              ))}
            </Select>
          </FormField>
          <FormField label="Billing cycle" id="service-billing_cycle">
            <Select value={form.billing_cycle} onChange={(event) => setForm((current) => ({ ...current, billing_cycle: event.target.value }))}>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="yearly">Yearly</option>
            </Select>
          </FormField>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <FormField label="Domain" id="service-domain">
            <Input value={form.domain} onChange={(event) => setForm((current) => ({ ...current, domain: event.target.value }))} />
          </FormField>
          <FormField label="Monthly cost" id="service-monthly_cost">
            <Input type="number" min="0" step="0.01" value={form.monthly_cost} onChange={(event) => setForm((current) => ({ ...current, monthly_cost: event.target.value }))} />
          </FormField>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <FormField label="Expiry date" id="service-expiry_date">
            <Input type="date" value={form.expiry_date || ''} onChange={(event) => setForm((current) => ({ ...current, expiry_date: event.target.value }))} />
          </FormField>
          <FormField label="Disk usage" id="service-disk_usage">
            <Input value={form.disk_usage} onChange={(event) => setForm((current) => ({ ...current, disk_usage: event.target.value }))} />
          </FormField>
        </div>
      </form>
    </Modal>
  )
}

function DeleteServiceDialog({ service, open, onClose, onConfirm, deleting, confirmText, onConfirmTextChange }) {
  if (!service) return null

  const canDelete = confirmText.trim() === service.name.trim()

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Delete service permanently"
      description="This removes the service record only when there are no linked subscriptions, tickets, projects, or payment history."
      size="md"
      footer={(
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onClose} disabled={deleting}>Cancel</Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={!canDelete} isLoading={deleting} loadingText="Deleting">
            Delete permanently
          </Button>
        </div>
      )}
    >
      <div className="space-y-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
          <p className="font-semibold">Service name: {service.name}</p>
          <p className="mt-1">Type the exact service name to confirm this action.</p>
        </div>
        <FormField label="Confirm service name" required id="service-delete-confirm">
          <Input
            value={confirmText}
            onChange={(event) => onConfirmTextChange(event.target.value)}
            placeholder={service.name}
          />
        </FormField>
      </div>
    </Modal>
  )
}

export default function ServicesPage() {
  const navigate = useNavigate()
  const addToast = useNotificationStore((state) => state.addToast)
  const { isAdmin } = useRole()

  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('active')
  const [editTarget, setEditTarget] = useState(null)
  const [archiveTarget, setArchiveTarget] = useState(null)
  const [restoreTarget, setRestoreTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [savingId, setSavingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const loadServices = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listServices({ lifecycle: isAdmin ? 'all' : 'active' })
      setServices(Array.isArray(data) ? data : [])
    } catch {
      setServices([])
    } finally {
      setLoading(false)
    }
  }, [isAdmin])

  useEffect(() => {
    loadServices()
  }, [loadServices])

  const counts = useMemo(() => ({
    active: services.filter((service) => !service.is_archived).length,
    archived: services.filter((service) => service.is_archived).length,
    all: services.length,
  }), [services])

  const visibleServices = useMemo(() => {
    if (!isAdmin) return services.filter((service) => !service.is_archived)
    if (filter === 'archived') return services.filter((service) => service.is_archived)
    if (filter === 'all') return services
    return services.filter((service) => !service.is_archived)
  }, [filter, isAdmin, services])

  const handleRenewal = (service) => {
    navigate('/tickets/new', {
      state: {
        subject: `Renewal Request: ${service.name}`,
        ticket_type: 'Renewal',
        org_id: service.org_id,
        service_id: service.id,
      },
    })
  }

  const handleEditSave = async (serviceId, payload) => {
    setSavingId(serviceId)
    try {
      await updateService(serviceId, payload)
      addToast({ type: 'success', title: 'Service updated' })
      await loadServices()
    } catch (error) {
      throw error
    } finally {
      setSavingId(null)
    }
  }

  const handleArchive = async (service) => {
    setSavingId(service.id)
    try {
      await archiveService(service.id)
      addToast({ type: 'success', title: 'Service archived' })
      await loadServices()
    } catch (error) {
      addToast({ type: 'error', title: error?.response?.data?.detail ?? 'Failed to archive service' })
    } finally {
      setSavingId(null)
    }
  }

  const handleRestore = async (service) => {
    setSavingId(service.id)
    try {
      await restoreService(service.id)
      addToast({ type: 'success', title: 'Service restored' })
      await loadServices()
    } catch (error) {
      addToast({ type: 'error', title: error?.response?.data?.detail ?? 'Failed to restore service' })
    } finally {
      setSavingId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeletingId(deleteTarget.id)
    try {
      await deleteServicePermanently(deleteTarget.id)
      addToast({ type: 'success', title: 'Service deleted permanently' })
      setDeleteTarget(null)
      setDeleteConfirmText('')
      await loadServices()
    } catch (error) {
      addToast({ type: 'error', title: error?.response?.data?.detail ?? 'Failed to delete service' })
    } finally {
      setDeletingId(null)
    }
  }

  if (loading) {
    return (
      <PageShell>
        <LoadingState label="Loading services" rows={6} />
      </PageShell>
    )
  }

  const emptyTitle = !isAdmin || filter === 'active'
    ? 'No active services'
    : filter === 'archived'
      ? 'No archived services'
      : 'No services found'
  const emptyDescription = !isAdmin || filter === 'active'
    ? 'Active services appear here and can be used in tickets and subscriptions.'
    : filter === 'archived'
      ? 'Archive a service to keep it out of selectors while preserving history.'
      : 'There are no service records for this account yet.'

  return (
    <PageShell>
      <PageHeader
        title="Services"
        description="Manage active and archived services without exposing unsafe delete actions."
      />

      {isAdmin && (
        <div className="mt-5 flex flex-wrap gap-2">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFilter(item.key)}
              className={cn(
                'inline-flex min-h-10 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors',
                filter === item.key
                  ? 'border-primary bg-primary/10 text-foreground'
                  : 'border-border bg-surface text-secondary-foreground hover:bg-surface-muted hover:text-foreground',
              )}
            >
              {item.label}
              <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', filter === item.key ? 'bg-primary text-primary-foreground' : 'bg-muted text-secondary-foreground')}>
                {counts[item.key] ?? 0}
              </span>
            </button>
          ))}
        </div>
      )}

      {visibleServices.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            icon={ServerStackIcon}
            title={emptyTitle}
            description={emptyDescription}
          />
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visibleServices.map((service) => (
            <ServiceCard
              key={service.id}
              service={service}
              isAdmin={isAdmin}
              onEdit={setEditTarget}
              onArchive={setArchiveTarget}
              onRestore={setRestoreTarget}
              onDelete={(target) => {
                setDeleteTarget(target)
                setDeleteConfirmText('')
              }}
              onRenewal={handleRenewal}
            />
          ))}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(archiveTarget)}
        onClose={() => setArchiveTarget(null)}
        onConfirm={async () => {
          if (!archiveTarget) return
          await handleArchive(archiveTarget)
          setArchiveTarget(null)
        }}
        title="Archive service?"
        description="Archived services disappear from the active list and selectors, but tickets and invoices remain accessible."
        confirmLabel="Archive"
        destructive={false}
        isLoading={savingId === archiveTarget?.id}
      />

      <ConfirmDialog
        open={Boolean(restoreTarget)}
        onClose={() => setRestoreTarget(null)}
        onConfirm={async () => {
          if (!restoreTarget) return
          await handleRestore(restoreTarget)
          setRestoreTarget(null)
        }}
        title="Restore service?"
        description="This returns the service to the active list and makes it available in selectors again."
        confirmLabel="Restore"
        destructive={false}
        isLoading={savingId === restoreTarget?.id}
      />

      <ServiceEditModal
        service={editTarget}
        open={Boolean(editTarget)}
        onClose={() => setEditTarget(null)}
        onSave={handleEditSave}
        saving={savingId === editTarget?.id}
      />

      <DeleteServiceDialog
        service={deleteTarget}
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        deleting={deletingId === deleteTarget?.id}
        confirmText={deleteConfirmText}
        onConfirmTextChange={setDeleteConfirmText}
      />
    </PageShell>
  )
}
