import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { erpClient } from '@/erp'
import { Button, Spinner } from '@/components/ui'
import PlanSelector from '@/components/PlanSelector'
import { cn } from '@/lib/utils'
import {
  PlusIcon, TrashIcon, ExclamationCircleIcon, CheckCircleIcon,
  UserIcon, CalendarIcon, DocumentTextIcon,
} from '@heroicons/react/24/outline'

// ─── Reusable form primitives (matches NewTicketPage style) ───────────────────

function Field({ label, required, error, hint, children }) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
        {label}
        {required && <span className="text-rose-500">*</span>}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p className="flex items-center gap-1 text-xs text-rose-600">
          <ExclamationCircleIcon className="w-3.5 h-3.5 flex-shrink-0" />
          {error}
        </p>
      )}
    </div>
  )
}

function StyledInput({ className, ...props }) {
  return (
    <input
      className={cn(
        'w-full rounded-xl border border-border bg-background px-3.5 py-2.5 text-sm',
        'text-foreground placeholder:text-muted-foreground/60',
        'ring-offset-background transition-all outline-none',
        'focus:border-primary/50 focus:ring-2 focus:ring-primary/10',
        'disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

function StyledSelect({ className, children, ...props }) {
  return (
    <div className="relative">
      <select
        className={cn(
          'w-full appearance-none rounded-xl border border-border bg-background px-3.5 py-2.5 pr-10 text-sm',
          'text-foreground ring-offset-background transition-all outline-none',
          'focus:border-primary/50 focus:ring-2 focus:ring-primary/10',
          'disabled:opacity-50',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      <svg
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground"
        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  )
}

function FormBlock({ step, title, description, icon: Icon, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl border border-border bg-card shadow-sm overflow-hidden"
    >
      <div className="flex items-center gap-3 px-5 py-3.5 border-b border-border bg-muted/30">
        <div className="flex items-center justify-center w-6 h-6 rounded-lg bg-primary text-primary-foreground text-xs font-bold flex-shrink-0">
          {step}
        </div>
        <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <div>
          <p className="text-sm font-bold text-foreground leading-tight">{title}</p>
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      </div>
      <div className="px-5 py-4 space-y-4">
        {children}
      </div>
    </motion.div>
  )
}

// ─── Plan rows manager ────────────────────────────────────────────────────────

function PlanRows({ rows, onAdd, onRemove, onQtyChange, error }) {
  const [showSelector, setShowSelector] = useState(false)

  const handleSelect = (plan) => {
    if (rows.some((r) => r.plan === plan.name)) return // already added
    onAdd({ plan: plan.name, qty: 1 })
    setShowSelector(false)
  }

  return (
    <div className="space-y-3">
      {/* Existing rows */}
      <AnimatePresence initial={false}>
        {rows.map((row, i) => (
          <motion.div
            key={row.plan}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-border bg-muted/40"
          >
            <span className="text-sm font-medium text-foreground flex-1 truncate">{row.plan}</span>
            <label className="flex items-center gap-1.5 text-xs text-muted-foreground flex-shrink-0">
              Qty
              <input
                type="number"
                min={1}
                value={row.qty}
                onChange={(e) => onQtyChange(i, Math.max(1, parseInt(e.target.value) || 1))}
                className="w-14 rounded-lg border border-border bg-background px-2 py-1 text-sm text-foreground text-center outline-none focus:border-primary/50 focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </label>
            <button
              type="button"
              onClick={() => onRemove(i)}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-rose-500 hover:bg-rose-50 transition-colors flex-shrink-0"
            >
              <TrashIcon className="w-3.5 h-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>

      {/* Add plan button */}
      <button
        type="button"
        onClick={() => setShowSelector((v) => !v)}
        className="inline-flex items-center gap-1.5 text-sm text-primary font-medium hover:underline"
      >
        <PlusIcon className="w-4 h-4" />
        {showSelector ? 'Close selector' : 'Add plan'}
      </button>

      {/* Plan selector */}
      <AnimatePresence>
        {showSelector && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <PlanSelector
              selectedPlan={null}
              onSelect={handleSelect}
              className="mt-1"
            />
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <p className="flex items-center gap-1 text-xs text-rose-600">
          <ExclamationCircleIcon className="w-3.5 h-3.5" /> {error}
        </p>
      )}
    </div>
  )
}

// ─── Main form ────────────────────────────────────────────────────────────────

const INITIAL = {
  party_type:           'Customer',
  party:                '',
  generate_invoice_at:  '',
  start_date:           '',
  cancel_at_period_end: false,
  submit_invoice:       false,
}

const GENERATE_AT_OPTIONS = [
  'Beginning of the current subscription period',
  'End of the current subscription period',
]

export default function CreateSubscriptionForm({ onSuccess, onCancel }) {
  const [form, setForm]       = useState(INITIAL)
  const [planRows, setPlanRows] = useState([])
  const [errors, setErrors]   = useState({})
  const [submitError, setSubmitError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone]       = useState(false)

  const set = (key) => (val) => {
    setForm((f) => ({ ...f, [key]: val }))
    setErrors((e) => ({ ...e, [key]: '' }))
  }

  const validate = () => {
    const e = {}
    if (!form.party_type)          e.party_type          = 'Party type is required'
    if (!form.party.trim())        e.party               = 'Party name is required'
    if (!form.generate_invoice_at) e.generate_invoice_at = 'Select when to generate invoice'
    if (planRows.length === 0)     e.plans               = 'Add at least one plan'
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }

    setLoading(true)
    setSubmitError('')
    try {
      await erpClient.subscription.create({
        ...form,
        plans: planRows,
      })
      setDone(true)
      setTimeout(() => onSuccess?.(), 600)
    } catch (err) {
      setSubmitError(err.message ?? 'Failed to create subscription')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Block 1 — Party */}
      <FormBlock step="1" title="Party" description="Who is this subscription for?" icon={UserIcon}>
        <Field label="Party Type" required error={errors.party_type}>
          <StyledSelect
            value={form.party_type}
            onChange={(e) => set('party_type')(e.target.value)}
          >
            <option value="Customer">Customer</option>
            <option value="Supplier">Supplier</option>
          </StyledSelect>
        </Field>

        <Field label={form.party_type} required error={errors.party}
          hint={`Enter the exact ${form.party_type} name as it appears in ERPNext`}>
          <StyledInput
            placeholder={`e.g. Aloha Vietnam`}
            value={form.party}
            onChange={(e) => set('party')(e.target.value)}
          />
        </Field>
      </FormBlock>

      {/* Block 2 — Plans */}
      <FormBlock step="2" title="Plans" description="Select one or more subscription plans" icon={DocumentTextIcon}>
        <PlanRows
          rows={planRows}
          onAdd={(row)         => setPlanRows((r) => [...r, row])}
          onRemove={(i)        => setPlanRows((r) => r.filter((_, idx) => idx !== i))}
          onQtyChange={(i, qty) => setPlanRows((r) => r.map((row, idx) => idx === i ? { ...row, qty } : row))}
          error={errors.plans}
        />
      </FormBlock>

      {/* Block 3 — Billing */}
      <FormBlock step="3" title="Billing" description="Invoice schedule and options" icon={CalendarIcon}>
        <Field label="Generate Invoice At" required error={errors.generate_invoice_at}>
          <StyledSelect
            value={form.generate_invoice_at}
            onChange={(e) => set('generate_invoice_at')(e.target.value)}
          >
            <option value="" disabled>Select timing…</option>
            {GENERATE_AT_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </StyledSelect>
        </Field>

        <Field label="Start Date" hint="Optional — leave blank to start immediately">
          <StyledInput
            type="date"
            value={form.start_date}
            onChange={(e) => set('start_date')(e.target.value)}
          />
        </Field>

        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2.5 cursor-pointer group">
            <input
              type="checkbox"
              checked={form.cancel_at_period_end}
              onChange={(e) => set('cancel_at_period_end')(e.target.checked)}
              className="w-4 h-4 rounded border-border text-primary"
            />
            <span className="text-sm text-foreground group-hover:text-foreground/80 transition-colors">
              Cancel at end of period
            </span>
          </label>
          <label className="flex items-center gap-2.5 cursor-pointer group">
            <input
              type="checkbox"
              checked={form.submit_invoice}
              onChange={(e) => set('submit_invoice')(e.target.checked)}
              className="w-4 h-4 rounded border-border text-primary"
            />
            <span className="text-sm text-foreground group-hover:text-foreground/80 transition-colors">
              Auto-submit generated invoices
            </span>
          </label>
        </div>
      </FormBlock>

      {/* Global error */}
      <AnimatePresence>
        {submitError && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm"
          >
            <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
            {submitError}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-1">
        <Button
          type="submit"
          disabled={loading || done}
          className={cn('gap-2 min-w-[160px] transition-all', done && 'bg-emerald-600 hover:bg-emerald-600')}
        >
          {done ? (
            <><CheckCircleIcon className="w-4 h-4" /> Created!</>
          ) : loading ? (
            <><Spinner className="w-4 h-4" /> Creating…</>
          ) : (
            'Create Subscription'
          )}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" className="text-muted-foreground" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
