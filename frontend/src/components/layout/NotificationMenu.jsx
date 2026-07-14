import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BellIcon } from '@heroicons/react/24/outline'
import { AnimatePresence, motion } from 'framer-motion'
import { getNotifications, markAllRead, markRead } from '@/api/notifications'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { useTranslation } from '@/lib/i18n'
import { formatDateTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { IconButton, Spinner } from '@/components/ui'

export function NotificationMenu() {
  const { unreadCount, setUnreadCount, clearUnread } = useNotificationStore()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const ref = useRef(null)
  const { t } = useTranslation()

  useEffect(() => {
    getNotifications()
      .then((data) => {
        const list = Array.isArray(data) ? data : []
        setNotifications(list)
        setUnreadCount(list.filter((item) => !item.is_read).length)
      })
      .catch(() => {})
  }, [setUnreadCount])

  useEffect(() => {
    if (!open) return undefined
    const close = (event) => {
      if (event.key === 'Escape' || (ref.current && !ref.current.contains(event.target))) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const handleOpen = async () => {
    setOpen((value) => !value)
    if (open) return
    setLoading(true)
    try {
      const data = await getNotifications()
      const list = Array.isArray(data) ? data : []
      setNotifications(list)
      setUnreadCount(list.filter((item) => !item.is_read).length)
    } finally {
      setLoading(false)
    }
  }

  const handleMarkAll = async () => {
    await markAllRead()
    setNotifications((items) => items.map((item) => ({ ...item, is_read: true })))
    clearUnread()
  }

  const handleClick = async (notification) => {
    if (!notification.is_read) {
      await markRead(notification.id).catch(() => {})
      setNotifications((items) => items.map((item) => item.id === notification.id ? { ...item, is_read: true } : item))
      setUnreadCount(Math.max(0, unreadCount - 1))
    }
    setOpen(false)
    if (notification.ref_ticket_id) navigate(`/tickets/${notification.ref_ticket_id}`)
  }

  const label = unreadCount > 0 ? `${t('topbar.notifications')} (${unreadCount})` : t('topbar.notifications')

  return (
    <div ref={ref} className="relative">
      <IconButton label={label} onClick={handleOpen} aria-expanded={open} aria-haspopup="menu">
        <BellIcon className="h-5 w-5" aria-hidden="true" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[9px] font-bold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </IconButton>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            role="menu"
            className="fixed inset-x-3 top-[calc(var(--topbar-height)+0.5rem)] z-50 overflow-hidden rounded-lg border border-border bg-surface shadow-md sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-80"
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <span className="card-title">{t('topbar.notifications')}</span>
              {unreadCount > 0 && (
                <button type="button" onClick={handleMarkAll} className="text-xs font-medium text-info hover:underline">
                  {t('topbar.markAllRead')}
                </button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto divide-y divide-border">
              {loading ? (
                <div className="flex justify-center py-8"><Spinner /></div>
              ) : notifications.length === 0 ? (
                <p className="secondary-text py-8 text-center">{t('topbar.allCaughtUp')}</p>
              ) : notifications.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  role="menuitem"
                  onClick={() => handleClick(notification)}
                  className={cn(
                    'w-full px-4 py-3 text-left transition-colors hover:bg-surface-muted focus-visible:bg-surface-muted',
                    !notification.is_read && 'bg-info-muted/40',
                  )}
                >
                  <div className="flex items-start gap-2">
                    {!notification.is_read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-info" />}
                    <div className="min-w-0 flex-1">
                      <p className={cn('text-xs leading-5 text-foreground', !notification.is_read && 'font-semibold')}>{notification.title}</p>
                      {notification.content && <p className="metadata-text mt-0.5 line-clamp-1">{notification.content}</p>}
                      <p className="metadata-text mt-1">{formatDateTime(notification.created_at)}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
