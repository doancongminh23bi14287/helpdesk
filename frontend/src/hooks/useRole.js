import { useAuthStore } from './useAuth'

export function useRole() {
  const { user } = useAuthStore()
  const role = user?.role

  return {
    role,
    isAdmin: role === 'admin',
    isStaff: role === 'staff',
    isCustomer: role === 'customer',
  }
}
