import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default:     'border-transparent bg-primary text-primary-foreground',
        secondary:   'border-transparent bg-secondary text-secondary-foreground',
        destructive: 'border-transparent bg-destructive text-destructive-foreground',
        outline:     'text-foreground',
        success:     'border border-foreground/20 bg-foreground/5 text-foreground',
        warning:     'border border-foreground/30 bg-foreground/8 text-foreground',
        info:        'border border-foreground/20 bg-foreground/5 text-foreground',
        muted:       'border-transparent bg-muted text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  }
)

const statusVariantMap = {
  Open:      'success',
  Replied:   'info',
  Resolved:  'muted',
  Closed:    'muted',
  High:      'destructive',
  Urgent:    'destructive',
  Medium:    'warning',
  Low:       'muted',
  Active:    'success',
  Inactive:  'muted',
  Cancelled: 'destructive',
}

export function Badge({ label, variant, className, ...props }) {
  const resolvedVariant = variant ?? statusVariantMap[label] ?? 'secondary'
  return (
    <span className={cn(badgeVariants({ variant: resolvedVariant }), className)} {...props}>
      {label}
    </span>
  )
}

export { badgeVariants }
