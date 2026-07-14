import { useRef, useState } from 'react'
import {
  CloudArrowUpIcon,
  ExclamationTriangleIcon,
  PaperClipIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

import { Badge, IconButton } from '@/components/ui'
import { cn, daysUntil, formatDate } from '@/lib/utils'

const PRIORITIES = [
  { value: 'Low', dot: 'bg-text-muted' },
  { value: 'Medium', dot: 'bg-warning' },
  { value: 'High', dot: 'bg-danger' },
  { value: 'Urgent', dot: 'bg-danger' },
]

const ASSIGNMENT_MODES = [
  { value: 'none', label: 'None', description: 'Leave the ticket unassigned.' },
  { value: 'auto', label: 'Auto', description: 'Use the current assignment rules.' },
  { value: 'manual', label: 'Manual', description: 'Choose one or more staff members.' },
]

export function TicketPriorityPicker({ value, onChange }) {
  return (
    <fieldset>
      <legend className="sr-only">Priority</legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {PRIORITIES.map((priority) => (
          <label
            key={priority.value}
            className={cn(
              'relative flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition-colors',
              'focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2',
              value === priority.value
                ? 'border-primary bg-primary/5 text-foreground'
                : 'border-border bg-background text-secondary-foreground hover:bg-surface-muted',
            )}
          >
            <input
              type="radio"
              name="ticket-priority"
              value={priority.value}
              checked={value === priority.value}
              onChange={() => onChange(priority.value)}
              className="sr-only"
            />
            <span className={cn('h-2 w-2 rounded-full', priority.dot)} aria-hidden="true" />
            {priority.value}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

export function AssignmentModePicker({ value, onChange, staff, assigneeIds, onAssigneesChange }) {
  return (
    <div className="space-y-3">
      <fieldset>
        <legend className="sr-only">Assignment mode</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {ASSIGNMENT_MODES.map((mode) => (
            <label
              key={mode.value}
              className={cn(
                'cursor-pointer rounded-md border p-3 transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2',
                value === mode.value
                  ? 'border-primary bg-primary/5'
                  : 'border-border bg-background hover:bg-surface-muted',
              )}
            >
              <input
                type="radio"
                name="assignment-mode"
                value={mode.value}
                checked={value === mode.value}
                onChange={() => onChange(mode.value)}
                className="sr-only"
              />
              <span className="block text-sm font-semibold text-foreground">{mode.label}</span>
              <span className="mt-1 block text-xs text-secondary-foreground">{mode.description}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {value === 'manual' && (
        <fieldset className="max-h-44 overflow-y-auto rounded-md border border-border">
          <legend className="sr-only">Select assignees</legend>
          {staff.length === 0 ? (
            <p className="px-3 py-3 text-sm text-secondary-foreground">No staff available</p>
          ) : staff.map((person) => {
            const personId = String(person.id)
            return (
              <label key={person.id} className="flex cursor-pointer items-center gap-3 border-b border-border px-3 py-2.5 last:border-0 hover:bg-surface-muted">
                <input
                  type="checkbox"
                  checked={assigneeIds.includes(personId)}
                  onChange={(event) => onAssigneesChange(event.target.checked
                    ? [...assigneeIds, personId]
                    : assigneeIds.filter((id) => id !== personId))}
                  className="h-4 w-4 accent-primary"
                />
                <span className="min-w-0 flex-1 text-sm font-medium text-foreground">{person.full_name}</span>
                <span className="hidden truncate text-xs text-secondary-foreground sm:block">{person.email}</span>
              </label>
            )
          })}
        </fieldset>
      )}
    </div>
  )
}

export function TicketAttachmentPicker({ files, onAdd, onRemove, error }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const addFiles = (fileList) => onAdd(Array.from(fileList || []))

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          addFiles(event.dataTransfer.files)
        }}
        className={cn(
          'flex min-h-24 w-full items-center justify-center gap-3 rounded-md border border-dashed px-4 py-4 text-left transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          dragging ? 'border-primary bg-primary/5' : 'border-border bg-surface-muted hover:border-primary/50',
        )}
      >
        <CloudArrowUpIcon className="h-6 w-6 shrink-0 text-secondary-foreground" aria-hidden="true" />
        <span>
          <span className="block text-sm font-medium text-foreground">Add files or drop them here</span>
          <span className="mt-0.5 block text-xs text-secondary-foreground">PNG, JPG, PDF, ZIP, Office and text files, up to 10 MB each</span>
        </span>
      </button>
      <input
        ref={inputRef}
        id="ticket-attachments"
        type="file"
        multiple
        className="sr-only"
        aria-label="Ticket attachments"
        accept="image/*,.pdf,.zip,.xlsx,.xls,.docx,.doc,.pptx,.ppt,.txt,.csv"
        onChange={(event) => { addFiles(event.target.files); event.target.value = '' }}
      />

      {error && <p role="alert" className="text-xs font-medium text-danger">{error}</p>}

      {files.length > 0 && (
        <ul className="divide-y divide-border rounded-md border border-border" aria-label="Selected attachments">
          {files.map((file) => (
            <li key={`${file.name}-${file.size}`} className="flex items-center gap-3 px-3 py-2.5">
              <PaperClipIcon className="h-4 w-4 shrink-0 text-secondary-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground" title={file.name}>{file.name}</span>
              <span className="text-xs text-secondary-foreground">{formatFileSize(file.size)}</span>
              <IconButton
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Remove ${file.name}`}
                onClick={() => onRemove(file.name)}
              >
                <XMarkIcon className="h-4 w-4" />
              </IconButton>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ServicePreview({ service }) {
  const remainingDays = daysUntil(service.expiry_date)
  const isAtRisk = remainingDays !== null && remainingDays <= 30

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface-muted px-3 py-2 text-xs">
      <Badge variant="secondary">{service.type || 'Service'}</Badge>
      <span className="font-medium capitalize text-foreground">{service.status?.replace('_', ' ') || 'Unknown status'}</span>
      {remainingDays !== null && (
        <span className={cn('inline-flex items-center gap-1', isAtRisk ? 'text-warning' : 'text-secondary-foreground')}>
          {isAtRisk && <ExclamationTriangleIcon className="h-3.5 w-3.5" aria-hidden="true" />}
          {remainingDays < 0 ? 'Expired' : `Expires ${formatDate(service.expiry_date)}`}
        </span>
      )}
    </div>
  )
}

export function CatalogueItemPicker({ items, selectedId, onChange, loading }) {
  if (loading) return <p className="text-sm text-secondary-foreground">Loading catalogue...</p>
  if (items.length === 0) return <p className="text-sm text-secondary-foreground">No catalogue items available.</p>

  return (
    <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          aria-pressed={selectedId === item.id}
          onClick={() => onChange(selectedId === item.id ? null : item.id)}
          className={cn(
            'w-full rounded-md border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            selectedId === item.id ? 'border-primary bg-primary/5' : 'border-border hover:bg-surface-muted',
          )}
        >
          <span className="block text-sm font-medium text-foreground">{item.name}</span>
          {item.description && <span className="mt-1 block line-clamp-2 text-xs text-secondary-foreground">{item.description}</span>}
        </button>
      ))}
    </div>
  )
}

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
