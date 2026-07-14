import { forwardRef } from 'react'
import { cn } from '@/lib/utils'
import { FormField } from '@/components/ui/FormField'

export const Select = forwardRef(function Select(
  { className, label, error, helperText, required, id, options = [], children, ...props },
  ref,
) {
  const control = (
    <select
      ref={ref}
      id={id}
      required={required}
      className={cn(
        'flex h-11 w-full sm:h-9 rounded-md border border-input bg-surface px-3 text-sm text-foreground shadow-sm',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-60',
        error && 'border-danger focus-visible:ring-danger',
        className,
      )}
      {...props}
    >
      {children || options.map((option) => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  )

  if (!label && !helperText && !error) return control
  return <FormField label={label} required={required} helperText={helperText} error={error} id={id}>{control}</FormField>
})
