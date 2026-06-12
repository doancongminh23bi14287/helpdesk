import { useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import { useAuthStore } from '@/hooks/useAuth'
import { useNotificationStore } from '@/hooks/useNotificationStore'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001/api'
const SOCKET_URL = API_URL.replace(/\/api$/, '')

export function useSocket() {
  const { isAuthenticated } = useAuthStore()
  const socketRef = useRef(null)
  const { addToast, incrementUnread } = useNotificationStore()

  useEffect(() => {
    if (!isAuthenticated) return

    const token = localStorage.getItem('access_token')
    if (!token) return

    const socket = io(SOCKET_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
    })

    socketRef.current = socket

    socket.on('notification', (data) => {
      incrementUnread()
      const type = data.type ?? 'info'
      addToast({
        title: data.title ?? 'New notification',
        type,
        ref_ticket_id: data.ref_ticket_id,
      })
    })

    return () => {
      socket.disconnect()
      socketRef.current = null
    }
  }, [isAuthenticated, addToast, incrementUnread])
}
