import { cn } from '@/lib/utils'

export function Input({ className, label, error, ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium text-foreground">{label}</label>}
      <input
        className={cn(
          'flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm shadow-sm',
          'placeholder:text-muted-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'transition duration-150',
          error && 'border-destructive focus-visible:ring-destructive',
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
