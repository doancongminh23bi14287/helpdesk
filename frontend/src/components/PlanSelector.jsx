import { useState, useEffect } from 'react'
import { erpClient } from '@/erp'
import { Spinner } from '@/components/ui'
import { cn } from '@/lib/utils'
import { CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'

const INTERVAL_LABEL = {
  Day:   'd',
  Week:  'wk',
  Month: 'mo',
  Year:  'yr',
}

const PRICE_DET_CLS = {
  'Fixed Rate':           'bg-blue-500/10 text-blue-600 border-blue-500/20',
  'Based On Price List':  'bg-purple-500/10 text-purple-600 border-purple-500/20',
  'Monthly Rate':         'bg-amber-500/10 text-amber-600 border-amber-500/20',
}

function PlanCard({ plan, selected, onSelect }) {
  const intervalText = plan.billing_interval
    ? `Every ${plan.billing_interval_count ?? 1} ${INTERVAL_LABEL[plan.billing_interval] ?? plan.billing_interval}`
    : null
  const priceCls = PRICE_DET_CLS[plan.price_determination] ?? 'bg-zinc-100 text-zinc-500 border-zinc-200'

  return (
    <button
      type="button"
      onClick={() => onSelect(plan)}
      className={cn(
        'relative w-full text-left rounded-xl border p-4 transition-all duration-150',
        'hover:border-primary/40 hover:bg-primary/5',
        selected
          ? 'border-primary bg-primary/5 ring-2 ring-primary/20'
          : 'border-border bg-card',
      )}
    >
      {selected && (
        <CheckCircleIcon className="absolute top-3 right-3 w-4 h-4 text-primary" />
      )}

      <p className="text-sm font-bold text-foreground pr-6">{plan.plan_name}</p>

      {/* Cost + interval */}
      <div className="flex items-baseline gap-1 mt-1">
        <span className="text-lg font-bold text-foreground tabular-nums">
          {plan.cost?.toLocaleString() ?? '—'}
        </span>
        <span className="text-xs text-muted-foreground">{plan.currency}</span>
        {intervalText && (
          <span className="text-xs text-muted-foreground">/ {intervalText}</span>
        )}
      </div>

      {/* Price determination badge */}
      {plan.price_determination && (
        <span className={`inline-flex items-center mt-2 px-2 py-0.5 rounded-md text-[10px] font-semibold border ${priceCls}`}>
          {plan.price_determination}
        </span>
      )}
    </button>
  )
}

export default function PlanSelector({ selectedPlan, onSelect, className }) {
  const [plans, setPlans]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    setLoading(true)
    erpClient.plan.list()
      .then((res) => setPlans(res.data ?? []))
      .catch((e)  => setError(e.message))
      .finally(()  => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Spinner className="w-4 h-4" />
        Loading plans…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-red-600">
        <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
        {error}
      </div>
    )
  }

  if (plans.length === 0) {
    return (
      <p className="py-4 text-sm text-muted-foreground">No subscription plans available.</p>
    )
  }

  return (
    <div className={cn('grid grid-cols-1 sm:grid-cols-2 gap-3', className)}>
      {plans.map((plan) => (
        <PlanCard
          key={plan.name}
          plan={plan}
          selected={selectedPlan?.name === plan.name}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}
