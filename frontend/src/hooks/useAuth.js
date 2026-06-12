import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { login as apiLogin, logout as apiLogout, getMe } from '@/api/auth'
import { clearTokens } from '@/api/client'

/**
 * Auth store — JWT Bearer token auth against FastAPI backend.
 * Persists { user, isAuthenticated } to localStorage key 'auth-store'.
 */
export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,           // { id, email, full_name, role, org_id } | null
      isAuthenticated: false,
      isLoading: false,

      /**
       * Authenticate with email + password.
       * 1. apiLogin stores tokens in localStorage.
       * 2. getMe fetches the full user object.
       * Rethrows on error so the LoginPage can surface the message.
       */
      login: async (email, password) => {
        set({ isLoading: true })
        try {
          await apiLogin(email, password)
          const user = await getMe()
          set({ user, isAuthenticated: true })
          return true
        } catch (err) {
          set({ user: null, isAuthenticated: false })
          throw err
        } finally {
          set({ isLoading: false })
        }
      },

      /**
       * Log out and clear local state.
       * Clears state even if the API call fails.
       */
      logout: async () => {
        try {
          await apiLogout()
        } catch {
          // Local logout must remain reliable even if the server-side revoke fails.
        } finally {
          set({ user: null, isAuthenticated: false })
        }
      },

      /**
       * Replace the persisted user record with a fresh server-truth profile.
       * Used after profile/avatar updates so the sidebar/topbar reflect
       * changes without a full page reload.
       */
      setUser: (user) => set({ user }),

      /**
       * Check whether a valid session exists.
       * 1. Short-circuits if no access_token in localStorage.
       * 2. Calls getMe() to validate the token and refresh user data.
       * Returns true if authenticated, false otherwise.
       */
      checkSession: async () => {
        if (!localStorage.getItem('access_token')) {
          set({ isAuthenticated: false, isLoading: false })
          return false
        }
        set({ isLoading: true })
        try {
          const user = await getMe()
          set({ user, isAuthenticated: true, isLoading: false })
          return true
        } catch {
          set({ user: null, isAuthenticated: false, isLoading: false })
          clearTokens()
          return false
        }
      },
    }),
    {
      name: 'auth-store',
      // Persist only session identity — exclude transient/functional fields.
      partialize: (s) => ({ user: s.user, isAuthenticated: s.isAuthenticated }),
    },
  ),
)
