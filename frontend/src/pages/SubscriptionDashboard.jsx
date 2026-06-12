import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useSubscriptions } from '@/hooks/useSubscriptions'
import { Card, CardContent, Button, EmptyState } from '@/components/ui'
import CreateSubscriptionForm from '@/components/CreateSubscriptionForm'
import { formatDate, cn } from '@/lib/utils'
import {
  ArrowPathIcon, PlusIcon, CalendarIcon, ExclamationCircleIcon,
} from '@heroicons/react/24/outline'

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_CLS = {
  'Active':        'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  'Cancelled':     'bg-zinc-100 text-zinc-500 border-zinc-200',
  'Completed':     'bg-blue-500/10 text-blue-600 border-blue-500/20',
  'Past Due Date': 'bg-red-500/10 text-red-600 border-red-500/20',
}

const TABS = [
  { label: 'All',       value: '' },
  { label: 'Active',    value: 'Active' },
  { label: 'Cancelled', value: 'Cancelled' },
  { label: 'Completed', value: 'Completed' },
]

// ─── Shared primitives ────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const cls = STATUS_CLS[status] ?? 'bg-zinc-100 text-zinc-500 border-zinc-200'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${cls}`}>
      {status ?? '—'}
    </span>
  )
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-3 animate-pulse">
      <div className="flex items-start justify-between">
        <div className="space-y-1.5">
          <div className="h-2.5 bg-muted rounded w-36" />
          <div className="h-4 bg-muted rounded w-28" />
        </div>
        <div className="h-5 bg-muted rounded-md w-16" />
      </div>
      <div className="h-3 bg-muted rounded w-44" />
      <div className="h-px bg-border" />
      <div className="flex gap-1.5">
        <div className="h-5 bg-muted rounded-md w-20" />
        <div className="h-5 bg-muted rounded-md w-16" />
      </div>
    </div>
  )
}

// ─── Subscription card ────────────────────────────────────────────────────────

function SubscriptionCard({ sub, index, onClick }) {
  const plans = sub.plans ?? []
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
    >
      <button onClick={() => onClick(sub.name)} className="w-full text-left group">
        <Card className="transition-all duration-200 hover:shadow-md hover:border-primary/30 hover:-translate-y-0.5">
          <CardContent className="p-5 space-y-3">
            {/* Header row */}
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[11px] font-mono text-muted-foreground group-hover:text-primary transition-colors truncate">
                  {sub.name}
                </p>
                <p className="text-sm font-semibold text-foreground mt-0.5 truncate">
                  {sub.party || '—'}
                </p>
              </div>
              <StatusBadge status={sub.status} />
            </div>

            {/* Invoice period */}
            {(sub.current_invoice_start || sub.current_invoice_end) && (
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <CalendarIcon className="w-3.5 h-3.5 flex-shrink-0" />
                <span>
                  {formatDate(sub.current_invoice_start)}
                  {' → '}
                  {formatDate(sub.current_invoice_end)}
                </span>
              </div>
            )}

            {/* Plans */}
            {plans.length > 0 && (
              <>
                <div className="h-px bg-border" />
                <div className="flex flex-wrap gap-1.5">
                  {plans.map((row, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-[11px] font-medium text-muted-foreground border border-border"
                    >
                      {row.plan}
                      {row.qty > 1 && (
                        <span className="font-semibold text-primary">×{row.qty}</span>
                      )}
                    </span>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </button>
    </motion.div>
  )
}

// ─── Create modal overlay ─────────────────────────────────────────────────────

function CreateModal({ onClose, onCreated }) {
  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.97, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 16 }}
          transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          className="relative w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-2xl bg-background border border-border shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-6 py-4 border-b border-border">
            <h2 className="font-display font-bold text-lg text-foreground">New Subscription</h2>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="p-6">
            <CreateSubscriptionForm onSuccess={onCreated} onCancel={onClose} />
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SubscriptionDashboard() {
  const [statusFilter, setStatusFilter] = useState('')
  const [showCreate, setShowCreate]     = useState(false)
  const [refreshKey, setRefreshKey]     = useState(0)
  const navigate = useNavigate()

  const filters = statusFilter ? { status: statusFilter } : {}
  const { data: subscriptions, loading, error } = useSubscriptions(filters)

  const handleCreated = () => {
    setShowCreate(false)
    setRefreshKey((k) => k + 1) // triggers a re-mount of the data hook
    navigate('/subscriptions')
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="font-display font-bold text-2xl text-foreground tracking-tight">
            Subscriptions
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your active and past subscription plans.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2 flex-shrink-0">
          <PlusIcon className="w-4 h-4" />
          New Subscription
        </Button>
      </div>

      {/* Status filter tabs */}
      <div className="flex gap-1 p-1 bg-muted rounded-xl w-fit">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => setStatusFilter(t.value)}
            className={cn(
              'px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-150',
              statusFilter === t.value
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
          <div className="p-4 bg-destructive/10 rounded-2xl">
            <ExclamationCircleIcon className="w-8 h-8 text-destructive" />
          </div>
          <div>
            <p className="font-semibold text-foreground">Failed to load subscriptions</p>
            <p className="text-sm text-muted-foreground mt-1 max-w-xs">{error}</p>
          </div>
          <Button variant="outline" onClick={() => setRefreshKey((k) => k + 1)} className="gap-2">
            <ArrowPathIcon className="w-4 h-4" />
            Retry
          </Button>
        </div>
      ) : subscriptions.length === 0 ? (
        <EmptyState
          icon={ArrowPathIcon}
          title="No subscriptions found"
          description={
            statusFilter
              ? `No ${statusFilter.toLowerCase()} subscriptions to show.`
              : 'Create your first subscription to get started.'
          }
          action={
            <Button onClick={() => setShowCreate(true)} className="gap-2">
              <PlusIcon className="w-4 h-4" />
              New Subscription
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {subscriptions.map((sub, i) => (
            <SubscriptionCard
              key={sub.name}
              sub={sub}
              index={i}
              onClick={(name) => navigate(`/subscriptions/${encodeURIComponent(name)}`)}
            />
          ))}
        </div>
      )}

      {/* Create overlay */}
      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  )
}
