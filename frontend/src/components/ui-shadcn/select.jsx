import { cn } from '@/lib/utils'

export function Select({ className, label, options = [], ...props }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-sm font-medium text-foreground">{label}</label>}
      <select
        className={cn(
          'flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm shadow-sm',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'transition duration-150',
          className,
        )}
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}
