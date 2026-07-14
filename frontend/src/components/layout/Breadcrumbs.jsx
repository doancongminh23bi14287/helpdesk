import { Link, useLocation } from 'react-router-dom'
import { ChevronRightIcon } from '@heroicons/react/24/outline'
import { useTranslation } from '@/lib/i18n'

const labels = {
  tickets: 'Tickets',
  projects: 'SEO Projects',
  new: 'New Ticket',
  services: 'Services',
  notifications: 'Notifications',
  admin: 'Admin',
  organizations: 'Organizations',
  users: 'Users',
  items: 'Items',
  subscriptions: 'Subscriptions',
  invoices: 'Invoices',
  sla: 'SLA Policies',
  analytics: 'Analytics',
  account: 'Account',
  security: 'Security',
  system: 'System Status',
  'email-outbox': 'Email Outbox',
  seo: 'SEO Dashboard',
}

export function Breadcrumbs() {
  const { pathname } = useLocation()
  const { t } = useTranslation()
  const parts = pathname.split('/').filter(Boolean)
  const crumbs = parts.map((part, index) => ({
    label: labels[part] ?? `#${part}`,
    href: `/${parts.slice(0, index + 1).join('/')}`,
    isLast: index === parts.length - 1,
  }))

  return (
    <nav className="min-w-0 overflow-hidden" aria-label="Breadcrumb">
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        <li>
          <Link to="/" className="whitespace-nowrap font-medium text-muted-foreground transition-colors hover:text-foreground">
            {t('topbar.home')}
          </Link>
        </li>
        {crumbs.map(({ label, href, isLast }) => (
          <li key={href} className="flex min-w-0 items-center gap-1">
            <ChevronRightIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" aria-hidden="true" />
            {isLast ? (
              <span className="truncate font-medium text-foreground" aria-current="page">{label}</span>
            ) : (
              <Link to={href} className="whitespace-nowrap font-medium text-muted-foreground transition-colors hover:text-foreground">
                {label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
