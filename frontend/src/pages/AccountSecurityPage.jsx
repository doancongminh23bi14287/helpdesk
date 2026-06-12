import { useEffect, useState } from 'react'
import { listSessions, revokeSession, logoutAllSessions } from '@/api/auth'
import { clearTokens } from '@/api/client'
import { Spinner } from '@/components/ui'
import { useAuthStore } from '@/hooks/useAuth'
import { formatDateTime as fmt } from '@/lib/utils'

export default function AccountSecurityPage() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [revoking, setRevoking] = useState(null)
  const { logout } = useAuthStore()

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      setSessions(await listSessions())
    } catch (err) {
      setError(err?.message ?? 'Failed to load sessions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const revoke = async (session) => {
    setRevoking(session.id)
    setError('')
    try {
      await revokeSession(session.id)
      if (session.is_current) {
        clearTokens()
        await logout()
        window.location.href = '/login'
        return
      }
      await load()
    } catch (err) {
      setError(err?.message ?? 'Failed to revoke session')
    } finally {
      setRevoking(null)
    }
  }

  const logoutAll = async () => {
    setError('')
    try {
      await logoutAllSessions()
      clearTokens()
      await logout()
      window.location.href = '/login'
    } catch (err) {
      setError(err?.message ?? 'Failed to log out all sessions')
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Account Security</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Review active sessions and revoke devices you no longer use.</p>
        </div>
        <button
          onClick={logoutAll}
          className="px-3 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700"
        >
          Log out all
        </button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16"><Spinner className="w-5 h-5" /></div>
        ) : sessions.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">No sessions found.</div>
        ) : (
          <div className="divide-y divide-border">
            {sessions.map((session) => (
              <div key={session.id} className="p-4 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-medium text-foreground">Session #{session.id}</p>
                    {session.is_current && <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700">Current</span>}
                    {!session.is_active && <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">Revoked</span>}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1 truncate">{session.user_agent || 'Unknown device'}</p>
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-muted-foreground">
                    <span>IP: {session.ip_address || '—'}</span>
                    <span>Created: {fmt(session.created_at)}</span>
                    <span>Expires: {fmt(session.expires_at)}</span>
                  </div>
                </div>
                {session.is_active && (
                  <button
                    onClick={() => revoke(session)}
                    disabled={revoking === session.id}
                    className="px-3 py-2 rounded-lg border border-input text-sm font-medium hover:bg-muted disabled:opacity-50 flex items-center gap-2"
                  >
                    {revoking === session.id && <Spinner className="w-3.5 h-3.5" />}
                    Revoke
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
