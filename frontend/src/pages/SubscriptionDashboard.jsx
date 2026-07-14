import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowPathIcon,
  CalendarDaysIcon,
  CreditCardIcon,
} from '@heroicons/react/24/outline'
import { useSubscriptions } from '@/hooks/useSubscriptions'
import { useAuthStore } from '@/hooks/useAuth'
import {
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorState,
  LoadingState,
  PageContainer,
  PageHeader,
  StatusBadge,
} from '@/components/ui'
import { cn, formatDate } from '@/lib/utils'

const TABS = [
  { label: 'All', value: '' },
  { label: 'Active', value: 'active' },
  { label: 'Trial', value: 'trial' },
  { label: 'Scheduled', value: 'scheduled' },
  { label: 'Past Due', value: 'past_due' },
  { label: 'Expired', value: 'expired' },
  { label: 'Cancelled', value: 'cancelled' },
]

function formatMoney(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('vi-VN').format(Number(value))
}

function SubscriptionCard({ subscription, onOpen }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(subscription.id)}
      className="w-full rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2"
      aria-label={`View subscription ${subscription.plan_name || subscription.id}`}
    >
      <Card className="h-full transition-colors hover:border-primary/40">
        <CardContent className="space-y-4 p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-foreground">
                {subscription.plan_name || `Subscription #${subscription.id}`}
              </p>
              <p className="mt-1 truncate text-xs text-muted-foreground">
                {subscription.org_name || `Organization #${subscription.org_id}`}
              </p>
            </div>
            <StatusBadge status={subscription.status} />
          </div>

          <div className="grid grid-cols-2 gap-3 border-t border-border pt-4 text-sm">
            <div>
              <p className="text-xs text-muted-foreground">Billing cycle</p>
              <p className="mt-1 font-medium capitalize text-foreground">{subscription.billing_cycle}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground">Amount</p>
              <p className="mt-1 font-medium tabular-nums text-foreground">
                {formatMoney(subscription.unit_price)}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <CalendarDaysIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{formatDate(subscription.start_date)} – {formatDate(subscription.end_date || subscription.current_period_end)}</span>
          </div>
        </CardContent>
      </Card>
    </button>
  )
}

export default function SubscriptionDashboard() {
  const [statusFilter, setStatusFilter] = useState('')
  const user = useAuthStore((state) => state.user)
  const navigate = useNavigate()
  const filters = useMemo(
    () => (statusFilter ? { status: statusFilter } : {}),
    [statusFilter],
  )
  const { data, loading, error, refetch } = useSubscriptions(filters)

  return (
    <PageContainer>
      <PageHeader
        title="Subscriptions"
        description="Review service plans, billing periods, and current subscription status."
        actions={user?.role === 'admin' ? (
          <Button type="button" onClick={() => navigate('/admin/subscriptions')}>
            Manage subscriptions
          </Button>
        ) : null}
      />

      <div className="flex max-w-full gap-1 overflow-x-auto rounded-lg bg-muted p-1" role="tablist" aria-label="Subscription status">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={statusFilter === tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={cn(
              'min-h-11 shrink-0 rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
              statusFilter === tab.value
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <LoadingState label="Loading subscriptions" rows={5} />
      ) : error ? (
        <ErrorState
          title="Unable to load subscriptions"
          description={error}
          onRetry={refetch}
        />
      ) : data.length === 0 ? (
        <EmptyState
          icon={CreditCardIcon}
          title={statusFilter ? 'No subscriptions match this status' : 'No subscriptions yet'}
          description={statusFilter ? 'Choose another status to continue.' : 'Subscriptions will appear after an administrator creates one.'}
          action={statusFilter ? (
            <Button type="button" variant="outline" onClick={() => setStatusFilter('')}>
              Clear filter
            </Button>
          ) : null}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((subscription) => (
            <SubscriptionCard
              key={subscription.id}
              subscription={subscription}
              onOpen={(id) => navigate(`/subscriptions/${id}`)}
            />
          ))}
        </div>
      )}

      {!loading && !error && data.length > 0 && (
        <Button type="button" variant="ghost" size="sm" onClick={refetch}>
          <ArrowPathIcon className="h-4 w-4" aria-hidden="true" />
          Refresh
        </Button>
      )}
    </PageContainer>
  )
}
