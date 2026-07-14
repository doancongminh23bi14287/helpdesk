import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { listServices } from '@/api/services'
import { useAuthStore } from '@/hooks/useAuth'
import { EmptyState, LoadingState, PageShell, PageHeader } from '@/components/ui'
import { motion } from 'framer-motion'
import { formatDate, daysUntil } from '@/lib/utils'
import {
  ServerStackIcon, SparklesIcon, ExclamationTriangleIcon,
  ArrowPathIcon, CubeIcon, DocumentTextIcon, GlobeAltIcon, WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import { StatusBadge } from '@/components/StatusBadge'
import { TypeBadge } from '@/components/TypeBadge'

const TYPE_CONFIG = {
  saas:    { label: 'SaaS',    icon: SparklesIcon,           color: 'bg-amber-100 text-amber-700' },
  hosting: { label: 'Hosting', icon: ServerStackIcon,        color: 'bg-cyan-100 text-cyan-700' },
  domain:  { label: 'Domain',  icon: GlobeAltIcon,           color: 'bg-purple-100 text-purple-700' },
  support: { label: 'Support', icon: WrenchScrewdriverIcon,  color: 'bg-orange-100 text-orange-700' },
  other:   { label: 'Other',   icon: CubeIcon,               color: 'bg-slate-100 text-slate-600' },
}

function ExpiryChip({ dateStr }) {
  const days = daysUntil(dateStr)
  if (days === null) return null
  if (days < 0)   return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><ExclamationTriangleIcon className="w-3 h-3" /> Expired</span>
  if (days <= 7)  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><ExclamationTriangleIcon className="w-3 h-3" /> {days}d left</span>
  if (days <= 30) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">{days}d left</span>
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">Expires {formatDate(dateStr)}</span>
}

function DiskBar({ usage }) {
  if (!usage) return null
  const match = usage.match(/([\d.]+)\s*\w+\s*\/\s*([\d.]+)/)
  if (!match) return <p className="text-sm font-semibold">{usage}</p>
  const pct = Math.min(100, Math.round((parseFloat(match[1]) / parseFloat(match[2])) * 100))
  const color = pct >= 90 ? 'bg-red-500' : pct >= 70 ? 'bg-amber-500' : 'bg-cyan-500'
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-muted-foreground">Disk Usage</span>
        <span className="text-xs font-semibold">{usage}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function ServiceCard({ service, onRenewal }) {
  const cfg = TYPE_CONFIG[service.type] ?? TYPE_CONFIG.other
  const Icon = cfg.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-border bg-card shadow-sm hover:shadow-md transition-shadow overflow-hidden"
    >
      <div className="p-5">
        <div className="flex items-start gap-4">
          <div className={cn('p-2.5 rounded-xl flex-shrink-0', cfg.color.split(' ')[0])}>
            <Icon className={cn('w-5 h-5', cfg.color.split(' ')[1])} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <p className="font-semibold text-foreground truncate">{service.name}</p>
              <StatusBadge status={service.status} className="flex-shrink-0" />
            </div>
            <TypeBadge type={service.type} className="mt-1" />
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-border space-y-3">
          {service.domain && (
            <div>
              <p className="text-xs text-muted-foreground">Domain</p>
              <p className="text-sm font-semibold truncate mt-0.5">{service.domain}</p>
            </div>
          )}
          {service.monthly_cost != null && service.monthly_cost > 0 && (
            <div>
              <p className="text-xs text-muted-foreground">Monthly Cost</p>
              <p className="text-sm font-semibold mt-0.5">
                {new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(service.monthly_cost)}
              </p>
            </div>
          )}
          {service.disk_usage && <DiskBar usage={service.disk_usage} />}
          {service.expiry_date && <ExpiryChip dateStr={service.expiry_date} />}

          <button
            type="button"
            onClick={() => onRenewal(service)}
            className="mt-2 w-full flex items-center justify-center gap-2 py-2 text-sm font-semibold bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors"
          >
            <ArrowPathIcon className="w-3.5 h-3.5" />
            Request Renewal
          </button>
          <Link
            to="/invoices"
            className="mt-2 w-full flex items-center justify-center gap-2 py-2 text-sm font-medium border border-border rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            <DocumentTextIcon className="w-3.5 h-3.5" />
            View Invoices
          </Link>
        </div>
      </div>
    </motion.div>
  )
}

export default function ServicesPage() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listServices()
      .then((data) => setServices(Array.isArray(data) ? data : []))
      .catch(() => setServices([]))
      .finally(() => setLoading(false))
  }, [])

  const handleRenewal = (service) => {
    navigate('/tickets/new', {
      state: {
        subject: `Renewal Request: ${service.name}`,
        ticket_type: 'Renewal',
        org_id: service.org_id,
        service_id: service.id,
      },
    })
  }

  if (loading) return (
    <PageShell>
      <LoadingState label="Loading services" rows={6} />
    </PageShell>
  )

  return (
    <PageShell>
      <PageHeader
        title="Services"
        subtitle={`${services.length} service${services.length !== 1 ? 's' : ''} in your account`}
      />

      {services.length === 0 ? (
        <EmptyState
          icon={ServerStackIcon}
          title="No services found"
          description="Contact support if you believe this is an error."
        />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map((s) => (
            <ServiceCard key={s.id} service={s} onRenewal={handleRenewal} />
          ))}
        </div>
      )}
    </PageShell>
  )
}
