import { useEffect, useRef } from 'react'
import { io } from 'socket.io-client'
import { useAuthStore } from '@/hooks/useAuth'
import { useNotificationStore } from '@/hooks/useNotificationStore'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001/api'
const SOCKET_URL = API_URL.replace(/\/api$/, '')

// Module-level singleton so any component can subscribe without re-connecting
let _socket = null
const _listeners = new Map() // event → Set<handler>

export function getSocket() { return _socket }

export function subscribeSocketEvent(event, handler) {
  if (!_listeners.has(event)) _listeners.set(event, new Set())
  _listeners.get(event).add(handler)
  if (_socket) _socket.on(event, handler)
  return () => unsubscribeSocketEvent(event, handler)
}

export function unsubscribeSocketEvent(event, handler) {
  _listeners.get(event)?.delete(handler)
  if (_socket) _socket.off(event, handler)
}

// Called by Layout; creates the global socket and registers existing listeners
export function useSocket() {
  const { isAuthenticated } = useAuthStore()
  const socketRef = useRef(null)
  const { addToast, incrementUnread } = useNotificationStore()

  useEffect(() => {
    if (!isAuthenticated) return

    const token = localStorage.getItem('access_token')
    if (!token) return

    // auth as a callback so every (re)connect attempt reads the CURRENT token —
    // a static object would resend the token captured at mount, which expires
    // after 30 min and floods the server with ExpiredSignatureError rejections
    const socket = io(SOCKET_URL, {
      auth: (cb) => cb({ token: localStorage.getItem('access_token') }),
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
    })

    socketRef.current = socket
    _socket = socket

    socket.on('notification', (data) => {
      incrementUnread()
      addToast({
        title: data.title ?? 'New notification',
        type: data.type ?? 'info',
        ref_ticket_id: data.ref_ticket_id,
      })
    })

    // Re-attach any listeners registered before socket connected
    for (const [event, handlers] of _listeners.entries()) {
      for (const handler of handlers) {
        socket.on(event, handler)
      }
    }

    return () => {
      // Remove all handlers first so a zombie socket (e.g. from React StrictMode
      // double-invoke in dev) cannot fire events after we've cleared the refs.
      socket.removeAllListeners()
      // Only disconnect if actually connected; avoids "WebSocket closed before
      // connection established" browser warning in dev StrictMode.
      if (socket.connected) {
        socket.disconnect()
      }
      socketRef.current = null
      _socket = null
    }
  }, [isAuthenticated, addToast, incrementUnread])
}
