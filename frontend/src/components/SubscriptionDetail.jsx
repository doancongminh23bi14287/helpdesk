import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { erpClient } from '@/erp'
import { useInvoices } from '@/hooks/useInvoices'
import { Card, CardContent, Button, Spinner } from '@/components/ui'
import { formatDate, cn } from '@/lib/utils'
import {
  ArrowLeftIcon, CalendarIcon, ExclamationCircleIcon,
  CheckCircleIcon, XCircleIcon, ArrowPathIcon,
} from '@heroicons/react/24/outline'

// ─── Status colours ───────────────────────────────────────────────────────────

const SUB_STATUS = {
  'Active':        'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  'Cancelled':     'bg-zinc-100 text-zinc-500 border-zinc-200',
  'Completed':     'bg-blue-500/10 text-blue-600 border-blue-500/20',
  'Past Due Date': 'bg-red-500/10 text-red-600 border-red-500/20',
}

const INV_STATUS = {
  'Paid':          'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  'Unpaid':        'bg-amber-500/10 text-amber-600 border-amber-500/20',
  'Overdue':       'bg-red-500/10 text-red-600 border-red-500/20',
  'Partly Paid':   'bg-amber-500/10 text-amber-600 border-amber-500/20',
  'Cancelled':     'bg-zinc-100 text-zinc-500 border-zinc-200',
  'Draft':         'bg-zinc-100 text-zinc-500 border-zinc-200',
}

function StatusBadge({ status, map }) {
  const cls = (map ?? SUB_STATUS)[status] ?? 'bg-zinc-100 text-zinc-500 border-zinc-200'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-semibold border ${cls}`}>
      {status ?? '—'}
    </span>
  )
}

// ─── Info row ─────────────────────────────────────────────────────────────────

function InfoRow({ label, value }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wider mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-foreground">{value || '—'}</p>
    </div>
  )
}

// ─── Action button with loading + feedback ────────────────────────────────────

function ActionButton({ label, icon: Icon, variant = 'outline', onConfirm, confirmMessage, disabled }) {
  const [state, setState] = useState('idle') // idle | loading | done | error
  const [errMsg, setErrMsg] = useState('')

  const handleClick = async () => {
    if (!window.confirm(confirmMessage)) return
    setState('loading')
    setErrMsg('')
    try {
      await onConfirm()
      setState('done')
      setTimeout(() => setState('idle'), 2000)
    } catch (e) {
      setState('error')
      setErrMsg(e.message ?? 'Action failed')
      setTimeout(() => setState('idle'), 3000)
    }
  }

  const icon = state === 'loading' ? <Spinner className="w-4 h-4" />
    : state === 'done'    ? <CheckCircleIcon className="w-4 h-4" />
    : state === 'error'   ? <XCircleIcon className="w-4 h-4" />
    : <Icon className="w-4 h-4" />

  return (
    <div className="flex flex-col gap-1">
      <Button
        variant={variant}
        onClick={handleClick}
        disabled={disabled || state === 'loading'}
        className={cn(
          'gap-2',
          state === 'done'  && 'border-emerald-500 text-emerald-600',
          state === 'error' && 'border-red-400 text-red-600',
        )}
      >
        {icon}
        {state === 'done' ? 'Done' : state === 'error' ? 'Failed' : label}
      </Button>
      {state === 'error' && errMsg && (
        <p className="text-xs text-red-600">{errMsg}</p>
      )}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function SubscriptionDetail({ subscriptionName: nameProp, onBack }) {
  // Works both as a standalone component (nameProp + onBack)
  // and as a route page (reads :name from URL, navigates on back).
  const params  = useParams()
  const navigate = useNavigate()
  const name = nameProp ?? decodeURIComponent(params.name ?? '')

  const [sub, setSub]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  const { data: invoices, loading: invLoading } = useInvoices(name)

  const load = () => {
    setLoading(true)
    setError(null)
    erpClient.subscription.get(name)
      .then((res) => setSub(res.data ?? res))
      .catch((e)  => setError(e.message))
      .finally(()  => setLoading(false))
  }

  useEffect(() => { if (name) load() }, [name]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleBack = onBack ?? (() => navigate('/subscriptions'))

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner className="w-6 h-6" />
      </div>
    )
  }

  // ── Error ──────────────────────────────────────────────────────────────────
  if (error || !sub) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl mx-auto space-y-4">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors group"
        >
          <ArrowLeftIcon className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to subscriptions
        </button>
        <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
          <div className="p-4 bg-destructive/10 rounded-2xl">
            <ExclamationCircleIcon className="w-8 h-8 text-destructive" />
          </div>
          <div>
            <p className="font-semibold text-foreground">Failed to load subscription</p>
            <p className="text-sm text-muted-foreground mt-1">{error ?? 'Subscription not found'}</p>
          </div>
          <Button variant="outline" onClick={load} className="gap-2">
            <ArrowPathIcon className="w-4 h-4" /> Retry
          </Button>
        </div>
      </div>
    )
  }

  const plans = sub.plans ?? []

  // ── Detail ─────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto space-y-6 animate-fade-in">
      {/* Back link */}
      <button
        onClick={handleBack}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors group"
      >
        <ArrowLeftIcon className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to subscriptions
      </button>

      {/* Header card */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <Card>
          <CardContent className="p-5">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <p className="text-xs font-mono text-muted-foreground">{sub.name}</p>
                <h1 className="font-display font-bold text-xl text-foreground mt-0.5">{sub.party}</h1>
                <p className="text-xs text-muted-foreground mt-0.5">{sub.party_type}</p>
              </div>
              <StatusBadge status={sub.status} map={SUB_STATUS} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 pt-4 border-t border-border">
              <InfoRow label="Start Date"       value={formatDate(sub.start_date)} />
              <InfoRow label="End Date"         value={formatDate(sub.end_date)} />
              <InfoRow label="Invoice Start"    value={formatDate(sub.current_invoice_start)} />
              <InfoRow label="Invoice End"      value={formatDate(sub.current_invoice_end)} />
              <InfoRow label="Company"          value={sub.company} />
              <InfoRow label="Invoice At"       value={sub.generate_invoice_at} />
              <InfoRow label="Auto-cancel"      value={sub.cancel_at_period_end ? 'Yes' : 'No'} />
              <InfoRow label="Auto-submit"      value={sub.submit_invoice ? 'Yes' : 'No'} />
            </div>

            {/* Plans */}
            {plans.length > 0 && (
              <div className="mt-4 pt-4 border-t border-border">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">Plans</p>
                <div className="flex flex-wrap gap-2">
                  {plans.map((row, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-muted border border-border text-sm font-medium text-foreground"
                    >
                      {row.plan}
                      <span className="text-xs text-muted-foreground">× {row.qty}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Actions */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.06 }}
      >
        <h2 className="font-display font-bold text-base text-foreground mb-3">Actions</h2>
        <div className="flex flex-wrap gap-3">
          <ActionButton
            label="Cancel Subscription"
            icon={XCircleIcon}
            variant="outline"
            confirmMessage="Are you sure you want to cancel this subscription? This cannot be undone."
            onConfirm={() => erpClient.subscription.cancel(sub.name).then(load)}
            disabled={sub.status === 'Cancelled'}
          />
          <ActionButton
            label="Restart Subscription"
            icon={ArrowPathIcon}
            variant="outline"
            confirmMessage="Restart this subscription from the next billing cycle?"
            onConfirm={() => erpClient.subscription.restart(sub.name).then(load)}
            disabled={sub.status === 'Active'}
          />
        </div>
      </motion.div>

      {/* Invoice history */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h2 className="font-display font-bold text-base text-foreground mb-3">Invoice History</h2>
        <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-sm">
          {invLoading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner className="w-5 h-5" />
            </div>
          ) : invoices.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-sm text-muted-foreground">No invoices for this subscription.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  {['Invoice', 'Status', 'Amount', 'Due Date'].map((h) => (
                    <th
                      key={h}
                      className={cn(
                        'px-5 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground',
                        h === 'Amount' && 'text-right',
                      )}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {invoices.map((inv) => (
                  <tr key={inv.name} className="hover:bg-muted/30 transition-colors">
                    <td className="px-5 py-3.5 font-mono text-xs text-foreground">{inv.name}</td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={inv.status} map={INV_STATUS} />
                    </td>
                    <td className="px-5 py-3.5 text-right tabular-nums font-semibold text-foreground">
                      {inv.grand_total?.toLocaleString() ?? '—'}
                    </td>
                    <td className="px-5 py-3.5 text-muted-foreground">{formatDate(inv.due_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </motion.div>
    </div>
  )
}
