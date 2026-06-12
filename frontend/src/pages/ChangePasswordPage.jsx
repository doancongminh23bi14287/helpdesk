import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/hooks/useAuth'
import { Spinner } from '@/components/ui'
import { LockClosedIcon } from '@heroicons/react/24/outline'

export default function ChangePasswordPage() {
  const navigate = useNavigate()
  const { user, checkSession } = useAuthStore()
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.next.length < 6) { setError('New password must be at least 6 characters'); return }
    if (form.next !== form.confirm) { setError('Passwords do not match'); return }
    setLoading(true)
    try {
      await changePassword(form.current, form.next)
      // Refresh user in store so must_change_password becomes false
      await checkSession()
      navigate('/')
    } catch (err) {
      setError(err?.response?.data?.detail ?? err.message ?? 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  const isForced = user?.must_change_password === true

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-3">
            <LockClosedIcon className="w-6 h-6 text-amber-600" />
          </div>
          <p className="font-bold text-xl text-gray-900">Change Password</p>
          {isForced && (
            <p className="text-sm text-amber-600 mt-1">
              You must change your password before continuing.
            </p>
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-8 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                {error}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Current Password</label>
              <input
                type="password"
                value={form.current}
                onChange={set('current')}
                placeholder="••••••••"
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
              <input
                type="password"
                value={form.next}
                onChange={set('next')}
                placeholder="••••••••"
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm New Password</label>
              <input
                type="password"
                value={form.confirm}
                onChange={set('confirm')}
                placeholder="••••••••"
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full h-10 inline-flex items-center justify-center gap-2 text-sm font-medium rounded-lg bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
            >
              {loading ? <><Spinner className="w-4 h-4" /> Changing…</> : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
