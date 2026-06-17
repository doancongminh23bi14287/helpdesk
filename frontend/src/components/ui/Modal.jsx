import * as Dialog from '@radix-ui/react-dialog'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

export function Modal({ open, onClose, title, children, className }) {
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            'fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2',
            'bg-card border border-border rounded-xl p-6 w-full max-w-lg z-50 shadow-xl',
            'max-h-[90vh] overflow-y-auto',
            className,
          )}
        >
          <div className="flex items-center justify-between mb-5">
            <Dialog.Title className="text-base font-semibold text-foreground">{title}</Dialog.Title>
            <Dialog.Close asChild>
              <button className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                <XMarkIcon className="w-4 h-4" />
              </button>
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
