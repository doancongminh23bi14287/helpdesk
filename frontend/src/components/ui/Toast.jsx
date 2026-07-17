import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { XMarkIcon, BellAlertIcon, ExclamationTriangleIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { cn } from '@/lib/utils'

function toastStyles(type) {
  switch (type) {
    case 'sla_breach':
    case 'sla':
      return 'bg-red-50 border-red-200 text-red-800'
    case 'assignment':
      return 'bg-amber-50 border-amber-200 text-amber-800'
    default:
      return 'bg-emerald-50 border-emerald-200 text-emerald-800'
  }
}

function ToastIcon({ type }) {
  const cls = 'w-4 h-4 flex-shrink-0'
  if (type === 'sla_breach' || type === 'sla') return <ExclamationTriangleIcon className={cls} />
  if (type === 'assignment') return <BellAlertIcon className={cls} />
  return <CheckCircleIcon className={cls} />
}

function ToastItem({ toast }) {
  const navigate = useNavigate()
  const { removeToast } = useNotificationStore()

  const handleClick = () => {
    if (toast.ref_ticket_id) navigate(`/tickets/${toast.ref_ticket_id}`)
    removeToast(toast.id)
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -16, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.94, transition: { duration: 0.15 } }}
      className={cn(
        'flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg max-w-sm w-full cursor-pointer',
        toastStyles(toast.type),
      )}
      onClick={handleClick}
    >
      <ToastIcon type={toast.type} />
      <p className="text-sm font-medium flex-1 leading-snug">{toast.title ?? toast.message ?? 'Notification'}</p>
      <button
        onClick={(e) => { e.stopPropagation(); removeToast(toast.id) }}
        className="p-0.5 rounded opacity-60 hover:opacity-100 transition-opacity flex-shrink-0"
      >
        <XMarkIcon className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  )
}

export function ToastContainer() {
  const { toasts } = useNotificationStore()

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  )
}
