import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/hooks/useAuth'
import { Spinner } from '@/components/ui'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, checkSession, user } = useAuthStore()
  const [checking, setChecking] = useState(true)
  const location = useLocation()

  useEffect(() => {
    checkSession().finally(() => setChecking(false))
  }, [])

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />

  // Force password change — block all navigation except /change-password
  if (user?.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  return children
}
