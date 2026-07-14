import { Children, cloneElement, isValidElement, useId } from 'react'
import { cn } from '@/lib/utils'

export function FormField({
  label,
  required = false,
  helperText,
  error,
  children,
  className,
  id,
}) {
  const generatedId = useId()
  const controlId = id || (isValidElement(children) && children.props.id) || generatedId
  const helperId = helperText ? `${controlId}-helper` : undefined
  const errorId = error ? `${controlId}-error` : undefined
  const describedBy = [helperId, errorId].filter(Boolean).join(' ') || undefined
  const control = Children.only(children)

  return (
    <div className={cn('space-y-1.5', className)}>
      {label && (
        <label htmlFor={controlId} className="block text-sm font-medium text-foreground">
          {label}
          {required && <span className="ml-1 text-danger" aria-hidden="true">*</span>}
          {required && <span className="sr-only"> required</span>}
        </label>
      )}
      {cloneElement(control, {
        id: controlId,
        'aria-invalid': Boolean(error) || undefined,
        'aria-describedby': describedBy,
      })}
      {helperText && !error && <p id={helperId} className="metadata-text">{helperText}</p>}
      {error && <p id={errorId} className="text-xs font-medium text-danger">{error}</p>}
    </div>
  )
}

export function FormActions({ children, className }) {
  return (
    <div className={cn('flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:justify-end', className)}>
      {children}
    </div>
  )
}
