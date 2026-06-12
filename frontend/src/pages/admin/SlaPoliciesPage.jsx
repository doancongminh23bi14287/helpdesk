import { useState, useEffect } from 'react'
import { ShieldCheckIcon, CheckIcon } from '@heroicons/react/24/outline'
import { Spinner } from '@/components/ui'
import { listSlaPolicies, updateSlaPolicy } from '@/api/sla'

const PRIORITY_BADGE = {
  Urgent: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  High:   'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  Medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  Low:    'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
}

export default function SlaPoliciesPage() {
  const [policies, setPolicies] = useState([])
  const [edits, setEdits] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listSlaPolicies()
      .then((data) => {
        setPolicies(data)
        const initial = {}
        data.forEach((p) => {
          initial[p.id] = { response_hours: p.response_hours, resolution_hours: p.resolution_hours }
        })
        setEdits(initial)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleChange = (id, field, value) => {
    setEdits((prev) => ({ ...prev, [id]: { ...prev[id], [field]: value } }))
    setSaved(false)
  }

  const handleSave = async () => {
    setError('')
    setSaving(true)
    try {
      await Promise.all(
        policies.map((p) =>
          updateSlaPolicy(p.id, {
            response_hours: Number(edits[p.id]?.response_hours ?? p.response_hours),
            resolution_hours: Number(edits[p.id]?.resolution_hours ?? p.resolution_hours),
          }),
        ),
      )
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  const isDirty = policies.some(
    (p) =>
      Number(edits[p.id]?.response_hours) !== Number(p.response_hours) ||
      Number(edits[p.id]?.resolution_hours) !== Number(p.resolution_hours),
  )

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">SLA Policies</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Configure response and resolution time targets per priority
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || (!isDirty && !saved)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {saving ? (
            <Spinner className="w-3.5 h-3.5" />
          ) : saved ? (
            <CheckIcon className="w-4 h-4" />
          ) : null}
          {saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      {error && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner className="w-6 h-6" />
          </div>
        ) : policies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <ShieldCheckIcon className="w-10 h-10 text-muted-foreground mb-3" />
            <p className="font-medium text-foreground">No SLA policies found</p>
            <p className="text-sm text-muted-foreground mt-1">Run database seeder to create default policies</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="text-left px-5 py-3 font-medium text-muted-foreground">Priority</th>
                <th className="text-left px-5 py-3 font-medium text-muted-foreground">Response Time (hours)</th>
                <th className="text-left px-5 py-3 font-medium text-muted-foreground">Resolution Time (hours)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {policies.map((p) => (
                <tr key={p.id} className="hover:bg-muted/20 transition-colors">
                  <td className="px-5 py-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${PRIORITY_BADGE[p.priority] ?? 'bg-muted text-muted-foreground'}`}>
                      {p.priority}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <input
                      type="number"
                      min="0.5"
                      step="0.5"
                      value={edits[p.id]?.response_hours ?? p.response_hours}
                      onChange={(e) => handleChange(p.id, 'response_hours', e.target.value)}
                      className="w-24 px-3 py-1.5 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </td>
                  <td className="px-5 py-4">
                    <input
                      type="number"
                      min="0.5"
                      step="0.5"
                      value={edits[p.id]?.resolution_hours ?? p.resolution_hours}
                      onChange={(e) => handleChange(p.id, 'resolution_hours', e.target.value)}
                      className="w-24 px-3 py-1.5 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Changes apply to new tickets. Existing tickets are not retroactively updated.
      </p>
    </div>
  )
}
