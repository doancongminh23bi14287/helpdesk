import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/hooks/useAuth'

export default function AdminRoute({ children }) {
  const { user } = useAuthStore()
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return children
}
