import { cn } from '@/lib/utils'

export function FilterBar({ children, className }) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-3 rounded-lg border border-border bg-surface p-3 sm:flex-row sm:flex-wrap sm:items-end', className)}>
      {children}
    </div>
  )
}
