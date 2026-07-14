import { Badge } from '@/components/ui-shadcn/badge'
import { cn } from '@/lib/utils'

const STATUS_VARIANTS = {
  Open: 'info',
  'In Progress': 'warning',
  Waiting: 'warning',
  Resolved: 'success',
  Closed: 'muted',
  Replied: 'info',
  open: 'info',
  working: 'warning',
  on_hold: 'warning',
  completed: 'success',
  cancelled: 'destructive',
  review: 'info',
  approved: 'success',
  active: 'success',
  trial: 'info',
  scheduled: 'info',
  past_due: 'warning',
  expired: 'destructive',
  inactive: 'muted',
  suspended: 'warning',
  draft: 'muted',
  sent: 'info',
  paid: 'success',
  overdue: 'destructive',
}

const LABELS = {
  on_hold: 'On Hold',
  scheduled: 'Scheduled',
  past_due: 'Past Due',
}

export function StatusBadge({ status, label, className = '' }) {
  const value = status ?? label ?? ''
  return (
    <Badge variant={STATUS_VARIANTS[value] ?? 'secondary'} className={cn('whitespace-nowrap', className)}>
      {LABELS[value] ?? value}
    </Badge>
  )
}

const PRIORITY_VARIANTS = {
  Urgent: 'destructive',
  High: 'destructive',
  Medium: 'warning',
  Low: 'muted',
  urgent: 'destructive',
  high: 'destructive',
  medium: 'warning',
  low: 'muted',
}

export function PriorityBadge({ priority, label, className }) {
  const value = priority ?? label ?? ''
  return <Badge variant={PRIORITY_VARIANTS[value] ?? 'secondary'} className={className}>{value}</Badge>
}

export default StatusBadge
