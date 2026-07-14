import { forwardRef } from 'react'
import { cn } from '@/lib/utils'
import { FormField } from '@/components/ui/FormField'

export const Textarea = forwardRef(function Textarea(
  { className, label, error, helperText, required, id, ...props },
  ref,
) {
  const control = (
    <textarea
      ref={ref}
      id={id}
      required={required}
      className={cn(
        'flex min-h-20 w-full resize-y rounded-md border border-input bg-surface px-3 py-2 text-sm text-foreground shadow-sm',
        'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-60',
        error && 'border-danger focus-visible:ring-danger',
        className,
      )}
      {...props}
    />
  )

  if (!label && !helperText && !error) return control
  return <FormField label={label} required={required} helperText={helperText} error={error} id={id}>{control}</FormField>
})
