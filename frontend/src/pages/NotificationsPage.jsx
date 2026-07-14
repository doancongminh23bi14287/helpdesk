import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getNotifications, markAllRead, markRead } from '@/api/notifications'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { Card, Spinner, EmptyState } from '@/components/ui'
import { formatDateTime } from '@/lib/utils'
import { BellIcon, BellAlertIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

export default function NotificationsPage() {
  const navigate = useNavigate()
  const { setUnreadCount } = useNotificationStore()
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getNotifications()
      .then((data) => {
        const list = Array.isArray(data) ? data : []
        setNotifications(list)
        setUnreadCount(list.filter((n) => !n.is_read).length)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [setUnreadCount])

  const handleMarkAll = async () => {
    await markAllRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    setUnreadCount(0)
  }

  const handleClick = async (n) => {
    if (!n.is_read) {
      await markRead(n.id).catch(() => {})
      setNotifications((prev) => prev.map((x) => x.id === n.id ? { ...x, is_read: true } : x))
    }
    if (n.ref_ticket_id) navigate(`/tickets/${n.ref_ticket_id}`)
  }

  const unread = notifications.filter((n) => !n.is_read).length

  return (
    <div className="px-4 py-5 sm:p-6 lg:p-8 max-w-3xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display font-bold text-2xl lg:text-3xl text-foreground">Notifications</h1>
          <p className="text-sm text-muted-foreground mt-1">Your recent account activity</p>
        </div>
        {unread > 0 && (
          <button
            onClick={handleMarkAll}
            className="text-sm font-medium text-primary hover:underline"
          >
            Mark all read
          </button>
        )}
      </div>

      <Card>
        {loading ? (
          <div className="flex items-center justify-center py-16"><Spinner /></div>
        ) : notifications.length === 0 ? (
          <EmptyState icon={BellIcon} title="All caught up" description="No new notifications." />
        ) : (
          <div className="divide-y divide-border">
            {notifications.map((n) => {
              const Icon = !n.is_read ? BellAlertIcon : BellIcon
              return (
                <button
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={cn(
                    'w-full text-left flex items-start gap-4 px-5 py-4 hover:bg-muted/30 transition-colors',
                    !n.is_read && 'bg-primary/[0.025]',
                  )}
                >
                  <div className={cn('mt-0.5 p-2 rounded-lg flex-shrink-0', !n.is_read ? 'bg-primary/10' : 'bg-muted')}>
                    <Icon className={cn('w-4 h-4', !n.is_read ? 'text-primary' : 'text-muted-foreground')} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-sm leading-snug', !n.is_read ? 'font-semibold text-foreground' : 'text-foreground/80')}>
                      {n.title}
                    </p>
                    {n.content && <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.content}</p>}
                    <p className="text-xs text-muted-foreground mt-1">{formatDateTime(n.created_at)}</p>
                  </div>
                  {!n.is_read && (
                    <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0 mt-1.5" />
                  )}
                </button>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
