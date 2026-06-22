import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { login } from '@/api/auth'
import { useAuthStore } from '@/hooks/useAuth'
import { Input, Spinner } from '@/components/ui'
import { ExclamationCircleIcon } from '@heroicons/react/24/outline'

export default function LoginPage() {
  const [form, setForm] = useState({ usr: '', pwd: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { checkSession } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.usr, form.pwd)
      const ok = await checkSession()
      if (ok) {
        navigate('/')
      } else {
        setError('Sign-in succeeded but session could not be verified. Please try again.')
      }
    } catch (err) {
      setError(err.message || 'Invalid credentials. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <p className="font-bold text-2xl text-gray-900">
            CustomerHub
          </p>
          <p className="text-sm text-gray-400 mt-1">Client Support & Workload Management System</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 sm:p-8 shadow-sm">
          <div className="mb-6">
            <h1 className="font-semibold text-xl text-gray-900">Sign in</h1>
            <p className="text-sm text-gray-400 mt-1">Enter your credentials to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              placeholder="you@company.com"
              value={form.usr}
              onChange={(e) => setForm({ ...form, usr: e.target.value })}
              required
              autoFocus
            />
            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              value={form.pwd}
              onChange={(e) => setForm({ ...form, pwd: e.target.value })}
              required
            />

            <div className="flex justify-end">
              <Link to="/forgot-password" className="text-xs text-gray-500 hover:text-gray-700 transition-colors">
                Forgot password?
              </Link>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full h-10 inline-flex items-center justify-center gap-2 text-sm font-medium rounded-lg bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? <><Spinner className="w-4 h-4" /> Signing in…</> : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-sm text-gray-400">
          Don&apos;t have an account?{' '}
          <Link to="/register" className="font-medium text-gray-900 hover:text-gray-600 transition-colors">
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}
