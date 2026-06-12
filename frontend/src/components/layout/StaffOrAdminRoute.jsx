import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/hooks/useAuth'

export default function StaffOrAdminRoute({ children }) {
  const { user } = useAuthStore()
  if (user?.role !== 'admin' && user?.role !== 'staff') return <Navigate to="/" replace />
  return children
}
