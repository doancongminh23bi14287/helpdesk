import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-surface-muted text-secondary-foreground',
        destructive: 'border-danger/20 bg-danger-muted text-danger',
        outline: 'border-border bg-surface text-foreground',
        success: 'border-success/20 bg-success-muted text-success',
        warning: 'border-warning/20 bg-warning-muted text-warning',
        info: 'border-info/20 bg-info-muted text-info',
        muted: 'border-transparent bg-surface-muted text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'secondary' },
  },
)

export function Badge({ label, children, variant, className, ...props }) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props}>
      {children ?? label}
    </span>
  )
}

export { badgeVariants }
