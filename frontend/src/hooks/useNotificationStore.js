import { create } from 'zustand'

let _toastId = 0

export const useNotificationStore = create((set, get) => ({
  toasts: [],
  unreadCount: 0,

  addToast: (toast) => {
    const id = ++_toastId
    const entry = { id, ...toast }
    set((s) => ({ toasts: [...s.toasts, entry] }))
    setTimeout(() => get().removeToast(id), 4000)
    return id
  },

  removeToast: (id) => {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
  },

  setUnreadCount: (count) => set({ unreadCount: count }),
  incrementUnread: () => set((s) => ({ unreadCount: s.unreadCount + 1 })),
  clearUnread: () => set({ unreadCount: 0 }),
}))
