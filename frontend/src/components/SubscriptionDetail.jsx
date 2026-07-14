import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeftIcon,
  CalendarDaysIcon,
  CreditCardIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import { cancelSubscription, getSubscription } from '@/api/subscriptions'
import { useInvoices } from '@/hooks/useInvoices'
import { useAuthStore } from '@/hooks/useAuth'
import {
  Button,
  Card,
  CardContent,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  LoadingState,
  PageContainer,
  PageHeader,
  StatusBadge,
} from '@/components/ui'
import { formatDate } from '@/lib/utils'

function formatMoney(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('vi-VN').format(Number(value))
}

function InfoItem({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words text-sm font-medium text-foreground">{value ?? '—'}</dd>
    </div>
  )
}

function InvoiceList({ invoices }) {
  if (invoices.length === 0) {
    return (
      <EmptyState
        icon={DocumentTextIcon}
        title="No invoices for this subscription"
        description="Generated invoices will appear here."
        className="min-h-40"
      />
    )
  }

  return (
    <>
      <div className="space-y-3 md:hidden">
        {invoices.map((invoice) => (
          <Card key={invoice.id}>
            <CardContent className="space-y-3 p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="font-mono text-xs font-semibold text-foreground">{invoice.invoice_number}</p>
                <StatusBadge status={invoice.status} />
              </div>
              <dl className="grid grid-cols-2 gap-3">
                <InfoItem label="Total" value={formatMoney(invoice.total)} />
                <InfoItem label="Due date" value={formatDate(invoice.due_date)} />
              </dl>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
        <table className="w-full min-w-[620px] text-sm">
          <thead className="sticky top-0 bg-muted">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Invoice</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Status</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">Total</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground">Due date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="hover:bg-muted/40">
                <td className="px-4 py-3 font-mono text-xs text-foreground">{invoice.invoice_number}</td>
                <td className="px-4 py-3"><StatusBadge status={invoice.status} /></td>
                <td className="px-4 py-3 text-right font-medium tabular-nums text-foreground">{formatMoney(invoice.total)}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{formatDate(invoice.due_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default function SubscriptionDetail({ subscriptionName: idProp, onBack }) {
  const params = useParams()
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const subscriptionId = Number(idProp ?? params.name)
  const [subscription, setSubscription] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [cancelError, setCancelError] = useState(null)
  const { data: invoices, loading: invoiceLoading, error: invoiceError } = useInvoices(subscriptionId)

  const load = useCallback(async () => {
    if (!Number.isInteger(subscriptionId) || subscriptionId <= 0) {
      setError('Invalid subscription identifier')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setSubscription(await getSubscription(subscriptionId))
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to load subscription')
    } finally {
      setLoading(false)
    }
  }, [subscriptionId])

  useEffect(() => {
    load()
  }, [load])

  const handleBack = onBack ?? (() => navigate('/subscriptions'))

  const handleCancel = async () => {
    setCancelling(true)
    setCancelError(null)
    try {
      const updated = await cancelSubscription(subscriptionId)
      setSubscription(updated)
      setCancelOpen(false)
    } catch (err) {
      setCancelError(err?.response?.data?.detail || err.message || 'Unable to cancel subscription')
    } finally {
      setCancelling(false)
    }
  }

  if (loading) {
    return <PageContainer><LoadingState label="Loading subscription" rows={6} /></PageContainer>
  }

  if (error || !subscription) {
    return (
      <PageContainer>
        <Button type="button" variant="ghost" onClick={handleBack}>
          <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
          Back to subscriptions
        </Button>
        <ErrorState title="Unable to load subscription" description={error} onRetry={load} />
      </PageContainer>
    )
  }

  const canCancel = user?.role === 'admin' && !['cancelled', 'expired'].includes(subscription.status)

  return (
    <PageContainer>
      <Button type="button" variant="ghost" onClick={handleBack}>
        <ArrowLeftIcon className="h-4 w-4" aria-hidden="true" />
        Back to subscriptions
      </Button>

      <PageHeader
        title={subscription.plan_name || `Subscription #${subscription.id}`}
        description={subscription.org_name || `Organization #${subscription.org_id}`}
        metadata={<StatusBadge status={subscription.status} />}
        actions={canCancel ? (
          <Button type="button" variant="outline" onClick={() => setCancelOpen(true)}>
            Cancel subscription
          </Button>
        ) : null}
      />

      {cancelError && <ErrorState title="Cancellation failed" description={cancelError} />}

      <Card>
        <CardContent className="p-5 sm:p-6">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted">
              <CreditCardIcon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-foreground">Subscription details</h2>
              <p className="text-sm text-muted-foreground">Contract and billing dates from CustomerHub.</p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-5 gap-y-5 sm:grid-cols-3 lg:grid-cols-4">
            <InfoItem label="Billing cycle" value={subscription.billing_cycle} />
            <InfoItem label="Amount" value={formatMoney(subscription.unit_price)} />
            <InfoItem label="Start date" value={formatDate(subscription.start_date)} />
            <InfoItem label="End date" value={formatDate(subscription.end_date)} />
            <InfoItem label="Current period" value={`${formatDate(subscription.current_period_start)} – ${formatDate(subscription.current_period_end)}`} />
            <InfoItem label="Next billing" value={formatDate(subscription.next_billing_date)} />
            <InfoItem label="Payment due" value={`${subscription.due_days} days`} />
            <InfoItem label="Tax rate" value={`${subscription.tax_rate}%`} />
          </dl>
        </CardContent>
      </Card>

      <section className="space-y-3" aria-labelledby="subscription-invoices-title">
        <div className="flex items-center gap-2">
          <CalendarDaysIcon className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
          <h2 id="subscription-invoices-title" className="text-base font-semibold text-foreground">Invoice history</h2>
        </div>
        {invoiceLoading ? (
          <LoadingState label="Loading invoices" rows={3} />
        ) : invoiceError ? (
          <ErrorState title="Unable to load invoices" description={invoiceError} />
        ) : (
          <InvoiceList invoices={invoices} />
        )}
      </section>

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => !cancelling && setCancelOpen(false)}
        onConfirm={handleCancel}
        title="Cancel subscription?"
        description="The linked service will be marked cancelled. Existing invoices and history are retained."
        confirmLabel="Cancel subscription"
        destructive
        isLoading={cancelling}
      />
    </PageContainer>
  )
}
