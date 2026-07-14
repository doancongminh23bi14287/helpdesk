import { cn } from '@/lib/utils'
import { PageDescription, PageTitle, SectionTitle } from './Typography'

export function PageHeader({
  title,
  description,
  subtitle,
  metadata,
  actions,
  children,
  className,
}) {
  return (
    <header className={cn('min-w-0 space-y-4', className)}>
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <PageTitle>{title}</PageTitle>
          {(description || subtitle) && (
            <PageDescription className="mt-1">{description || subtitle}</PageDescription>
          )}
          {metadata && <div className="mt-2 flex flex-wrap items-center gap-2">{metadata}</div>}
        </div>
        {actions && (
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            {actions}
          </div>
        )}
      </div>
      {children}
    </header>
  )
}

export function SectionHeader({ title, description, actions, className }) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between', className)}>
      <div className="min-w-0">
        <SectionTitle>{title}</SectionTitle>
        {description && <PageDescription className="mt-1">{description}</PageDescription>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
