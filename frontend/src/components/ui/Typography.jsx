import { cn } from '@/lib/utils'

export function PageTitle({ className, ...props }) {
  return <h1 className={cn('page-title', className)} {...props} />
}

export function PageDescription({ className, ...props }) {
  return <p className={cn('page-description', className)} {...props} />
}

export function SectionTitle({ className, ...props }) {
  return <h2 className={cn('section-title', className)} {...props} />
}

export function CardTitleText({ className, ...props }) {
  return <h3 className={cn('card-title', className)} {...props} />
}

export function Body({ className, ...props }) {
  return <p className={cn('body-text', className)} {...props} />
}

export function SecondaryText({ className, ...props }) {
  return <p className={cn('secondary-text', className)} {...props} />
}

export function Metadata({ className, ...props }) {
  return <p className={cn('metadata-text', className)} {...props} />
}

export function TableHeaderText({ className, ...props }) {
  return <span className={cn('table-header', className)} {...props} />
}
