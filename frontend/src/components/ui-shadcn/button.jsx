import { Slot } from '@radix-ui/react-slot'
import { ArrowPathIcon } from '@heroicons/react/24/outline'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow-sm hover:bg-primary-hover',
        destructive: 'bg-danger text-white shadow-sm hover:bg-danger/90',
        outline: 'border border-border bg-surface text-foreground shadow-sm hover:bg-surface-muted',
        secondary: 'bg-surface-muted text-secondary-foreground hover:text-foreground',
        ghost: 'text-secondary-foreground hover:bg-surface-muted hover:text-foreground',
        link: 'text-info underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-11 px-4 sm:h-9',
        sm: 'h-11 px-3 text-xs sm:h-8',
        lg: 'h-11 px-5',
        icon: 'h-11 w-11 p-0 sm:h-9 sm:w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export function Button({
  className,
  variant,
  size,
  asChild = false,
  isLoading = false,
  loadingText,
  disabled,
  children,
  ...props
}) {
  const buttonClassName = cn(buttonVariants({ variant, size, className }))

  if (asChild) {
    return (
      <Slot className={buttonClassName} {...props}>
        {children}
      </Slot>
    )
  }

  return (
    <button
      className={buttonClassName}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      {...props}
    >
      {isLoading && <ArrowPathIcon className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {isLoading && loadingText ? loadingText : children}
    </button>
  )
}

export function IconButton({ label, title, className, ...props }) {
  if (!label) throw new Error('IconButton requires an accessible label')
  return (
    <Button
      size="icon"
      variant="ghost"
      aria-label={label}
      title={title || label}
      className={className}
      {...props}
    />
  )
}

export { buttonVariants }
