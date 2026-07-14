import {
  ExclamationTriangleIcon,
  InboxIcon,
  MagnifyingGlassIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui-shadcn/button'

export function LoadingState({ label = 'Loading…', rows = 4, className }) {
  return (
    <div className={cn('space-y-3 py-6', className)} role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="skeleton-shimmer h-10 rounded-md" />
      ))}
    </div>
  )
}

export function EmptyState({
  icon: Icon = InboxIcon,
  title,
  description,
  action,
  className,
}) {
  return (
    <div className={cn('flex min-h-48 flex-col items-center justify-center px-4 py-10 text-center', className)}>
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-surface-muted">
        <Icon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
      </div>
      <p className="card-title">{title}</p>
      {description && <p className="secondary-text mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorState({ title = 'Unable to load data', description, onRetry, className }) {
  return (
    <div className={cn('rounded-lg border border-danger/25 bg-danger-muted px-4 py-4', className)} role="alert">
      <div className="flex items-start gap-3">
        <ExclamationTriangleIcon className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-danger">{title}</p>
          {description && <p className="mt-1 text-sm text-secondary-foreground">{description}</p>}
          {onRetry && <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onRetry}>Try again</Button>}
        </div>
      </div>
    </div>
  )
}

export function NoSearchResults({ description = 'Try changing or clearing your filters.', ...props }) {
  return <EmptyState icon={MagnifyingGlassIcon} title="No matching results" description={description} {...props} />
}

export function PermissionDeniedState({ ...props }) {
  return (
    <EmptyState
      icon={ShieldExclamationIcon}
      title="Permission denied"
      description="You do not have permission to view this content."
      {...props}
    />
  )
}
