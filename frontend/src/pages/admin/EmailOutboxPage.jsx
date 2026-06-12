import { useCallback, useEffect, useState } from 'react'
import { listEmailOutbox, retryEmailOutbox } from '@/api/emailOutbox'
import { Spinner } from '@/components/ui'
import { formatDateTime as fmt } from '@/lib/utils'

const STATUS = {
  pending: 'bg-amber-100 text-amber-700',
  sending: 'bg-blue-100 text-blue-700',
  sent: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
}

function StatusBadge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS[status] ?? 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}

export default function EmailOutboxPage() {
  const [rows, setRows] = useState([])
  const [status, setStatus] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listEmailOutbox({ status, limit: 100 })
      setRows(data?.items ?? [])
    } catch (err) {
      setError(err?.message ?? 'Failed to load email outbox')
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => { load() }, [load])

  const retry = async (row) => {
    setRetrying(row.id)
    setError('')
    try {
      await retryEmailOutbox(row.id)
      await load()
    } catch (err) {
      setError(err?.message ?? 'Failed to retry email')
    } finally {
      setRetrying(null)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Email Outbox</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Queued invoice and ticket email delivery attempts.</p>
        </div>
        <button onClick={load} className="px-3 py-2 rounded-lg border border-input text-sm font-medium hover:bg-muted">Refresh</button>
      </div>

      {error && <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}

      <div className="flex gap-3 mb-4">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="px-3 py-2 border border-input rounded-lg bg-background text-sm"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="sending">Sending</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16"><Spinner className="w-5 h-5" /></div>
        ) : rows.length === 0 ? (
          <div className="py-16 text-center text-sm text-muted-foreground">No outbox emails found.</div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 border-b border-border">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Recipient</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Subject</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Retries</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Related</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Scheduled</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr key={row.id} className={row.status === 'failed' ? 'bg-red-50/70' : ''}>
                  <td className="px-4 py-3 text-foreground">{row.recipient_email}</td>
                  <td className="px-4 py-3 text-foreground max-w-xs">
                    <div className="truncate">{row.subject}</div>
                    {row.last_error && <div className="text-xs text-red-700 mt-1 line-clamp-2">{row.last_error}</div>}
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{row.retry_count}/{row.max_retries}</td>
                  <td className="px-4 py-3 text-muted-foreground">{row.related_type || '—'} {row.related_id || ''}</td>
                  <td className="px-4 py-3 text-muted-foreground">{fmt(row.scheduled_at)}</td>
                  <td className="px-4 py-3 text-right">
                    {row.status !== 'sent' && (
                      <button
                        onClick={() => retry(row)}
                        disabled={retrying === row.id}
                        className="px-2.5 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 inline-flex items-center gap-1"
                      >
                        {retrying === row.id && <Spinner className="w-3 h-3" />}
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </div>
  )
}
