import * as Dialog from '@radix-ui/react-dialog'
import { AnimatePresence, motion } from 'framer-motion'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { Sidebar } from './Sidebar'

export function MobileNavigation({ open, onClose, onOpenSearch }) {
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                key="mobile-navigation-overlay"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm md:hidden"
              />
            </Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div
                key="mobile-navigation-panel"
                initial={{ x: -320 }}
                animate={{ x: 0 }}
                exit={{ x: -320 }}
                transition={{ type: 'spring', stiffness: 320, damping: 34, mass: 0.9 }}
                className="fixed inset-y-0 left-0 z-50 flex w-[19rem] max-w-[calc(100vw-2rem)] outline-none md:hidden [&>aside]:w-full"
              >
                <Dialog.Title className="sr-only">Primary navigation</Dialog.Title>
                <Sidebar
                  onNavigate={onClose}
                  onOpenSearch={() => {
                    onClose()
                    onOpenSearch()
                  }}
                />
                <Dialog.Close asChild>
                  <button
                    type="button"
                    aria-label="Close navigation menu"
                    className="absolute right-3 top-3 flex h-11 w-11 items-center justify-center rounded-md text-sidebar-foreground hover:bg-sidebar-hover hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
                  >
                    <XMarkIcon className="h-5 w-5" aria-hidden="true" />
                  </button>
                </Dialog.Close>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  )
}
