import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { forgotPassword, verifyOtp, resetPassword } from '@/api/auth'
import { Spinner } from '@/components/ui'
import { ExclamationCircleIcon, CheckCircleIcon, ArrowLeftIcon } from '@heroicons/react/24/outline'

const EXPIRY_SECONDS = 600 // 10 minutes

export default function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1) // 1=email, 2=otp, 3=new-password
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [countdown, setCountdown] = useState(0)
  const timerRef = useRef(null)

  // countdown timer for step 2
  useEffect(() => {
    if (step === 2 && countdown > 0) {
      timerRef.current = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1) {
            clearInterval(timerRef.current)
            return 0
          }
          return c - 1
        })
      }, 1000)
    }
    return () => clearInterval(timerRef.current)
  }, [step, countdown])

  const startCountdown = () => setCountdown(EXPIRY_SECONDS)

  const fmtCountdown = (s) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  // Step 1 — request OTP
  const handleRequestOtp = async (e) => {
    e.preventDefault()
    if (!email.trim()) { setError('Enter your email address'); return }
    setLoading(true)
    setError('')
    try {
      await forgotPassword(email.trim())
      setStep(2)
      startCountdown()
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // Step 2 — verify OTP
  const handleVerifyOtp = async (e) => {
    e.preventDefault()
    if (otp.length !== 6) { setError('Enter the 6-digit code'); return }
    setLoading(true)
    setError('')
    try {
      const data = await verifyOtp(email.trim(), otp)
      setResetToken(data.reset_token)
      setStep(3)
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Invalid or expired code'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  // Step 3 — set new password
  const handleResetPassword = async (e) => {
    e.preventDefault()
    if (newPassword.length < 6) { setError('Password must be at least 6 characters'); return }
    if (newPassword !== confirmPassword) { setError('Passwords do not match'); return }
    setLoading(true)
    setError('')
    try {
      await resetPassword(resetToken, newPassword)
      setSuccess('Password updated! Redirecting to login…')
      setTimeout(() => navigate('/login'), 2000)
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Could not reset password. Try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const resendCode = async () => {
    setError('')
    setLoading(true)
    try {
      await forgotPassword(email.trim())
      startCountdown()
      setOtp('')
    } catch {
      setError('Failed to resend code')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <p className="font-bold text-2xl text-gray-900">WorkDesk</p>
          <p className="text-sm text-gray-400 mt-1">Client Support & Workload Management System</p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6 sm:p-8 shadow-sm">
          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-6">
            {[1,2,3].map(n => (
              <div key={n} className={`h-1.5 flex-1 rounded-full transition-colors ${
                n <= step ? 'bg-gray-900' : 'bg-gray-200'
              }`} />
            ))}
          </div>

          {step === 1 && (
            <>
              <div className="mb-6">
                <h1 className="font-semibold text-xl text-gray-900">Reset password</h1>
                <p className="text-sm text-gray-400 mt-1">
                  Enter your email and we&apos;ll send a reset code.
                </p>
              </div>
              <form onSubmit={handleRequestOtp} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    required
                    autoFocus
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400"
                  />
                </div>
                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                    <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
                    {error}
                  </div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full h-10 inline-flex items-center justify-center gap-2 text-sm font-medium rounded-lg bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors">
                  {loading ? <><Spinner className="w-4 h-4" /> Sending&hellip;</> : 'Send reset code'}
                </button>
              </form>
            </>
          )}

          {step === 2 && (
            <>
              <div className="mb-6">
                <h1 className="font-semibold text-xl text-gray-900">Enter code</h1>
                <p className="text-sm text-gray-400 mt-1">
                  We sent a 6-digit code to <strong>{email}</strong>.
                </p>
              </div>
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">6-digit code</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={otp}
                    onChange={e => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="123456"
                    autoFocus
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm tracking-widest font-mono focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400"
                  />
                </div>
                {countdown > 0 ? (
                  <p className="text-xs text-gray-400 text-center">
                    Code expires in <span className="font-mono font-medium">{fmtCountdown(countdown)}</span>
                  </p>
                ) : (
                  <p className="text-xs text-gray-400 text-center">
                    Code expired.{' '}
                    <button type="button" onClick={resendCode}
                      className="text-amber-600 hover:text-amber-700 font-medium">
                      Resend code
                    </button>
                  </p>
                )}
                {countdown > 0 && (
                  <p className="text-xs text-gray-400 text-center">
                    Didn&apos;t receive it?{' '}
                    <button type="button" onClick={resendCode} disabled={loading}
                      className="text-amber-600 hover:text-amber-700 font-medium disabled:opacity-50">
                      Resend code
                    </button>
                  </p>
                )}
                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                    <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
                    {error}
                  </div>
                )}
                <button type="submit" disabled={loading || otp.length !== 6}
                  className="w-full h-10 inline-flex items-center justify-center gap-2 text-sm font-medium rounded-lg bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors">
                  {loading ? <><Spinner className="w-4 h-4" /> Verifying&hellip;</> : 'Verify code'}
                </button>
              </form>
            </>
          )}

          {step === 3 && !success && (
            <>
              <div className="mb-6">
                <h1 className="font-semibold text-xl text-gray-900">New password</h1>
                <p className="text-sm text-gray-400 mt-1">Choose a new password (min 6 characters).</p>
              </div>
              <form onSubmit={handleResetPassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    placeholder="&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;"
                    autoFocus
                    minLength={6}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Confirm password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;&#x2022;"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900/20 focus:border-gray-400"
                  />
                </div>
                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                    <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
                    {error}
                  </div>
                )}
                <button type="submit" disabled={loading}
                  className="w-full h-10 inline-flex items-center justify-center gap-2 text-sm font-medium rounded-lg bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors">
                  {loading ? <><Spinner className="w-4 h-4" /> Updating&hellip;</> : 'Update password'}
                </button>
              </form>
            </>
          )}

          {success && (
            <div className="text-center py-4">
              <CheckCircleIcon className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
              <p className="font-semibold text-gray-900">{success}</p>
            </div>
          )}
        </div>

        <p className="mt-5 text-center text-sm text-gray-400">
          <Link to="/login" className="inline-flex items-center gap-1 font-medium text-gray-900 hover:text-gray-600 transition-colors">
            <ArrowLeftIcon className="w-3.5 h-3.5" />
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
