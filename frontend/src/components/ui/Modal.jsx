import * as Dialog from '@radix-ui/react-dialog'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import { IconButton } from '@/components/ui-shadcn/button'

const sizeClasses = {
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-none sm:h-[calc(100dvh-2rem)] sm:max-w-[calc(100vw-2rem)]',
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
  size = 'md',
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(value) => !value && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm" />
        <Dialog.Content
          className={cn(
            'fixed inset-x-0 bottom-0 z-50 flex max-h-[100dvh] flex-col overflow-hidden rounded-t-lg border border-b-0 border-x-0 border-border bg-surface shadow-md',
            'sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:w-[calc(100%-2rem)] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-lg sm:border',
            sizeClasses[size],
            className,
          )}
        >
          <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
            <div className="min-w-0">
              <Dialog.Title className="section-title">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="page-description mt-1">{description}</Dialog.Description>
              ) : (
                <Dialog.Description className="sr-only">Dialog content for {title}.</Dialog.Description>
              )}
            </div>
            <Dialog.Close asChild>
              <IconButton label="Close dialog" className="-mr-2 -mt-1 shrink-0">
                <XMarkIcon className="h-5 w-5" aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
          {footer && <div className="shrink-0 border-t border-border bg-surface px-5 py-4 sm:px-6">{footer}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function ModalFooter({ children, className }) {
  return (
    <div className={cn('sticky -bottom-5 -mx-5 -mb-5 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface px-5 py-4 sm:-mx-6 sm:px-6 sm:flex-row sm:justify-end', className)}>
      {children}
    </div>
  )
}
