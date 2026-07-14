import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

function useIsMobileTable() {
  const getMatches = () => (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(max-width: 767px)').matches
  )
  const [isMobile, setIsMobile] = useState(getMatches)

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const media = window.matchMedia('(max-width: 767px)')
    const update = (event) => setIsMobile(event.matches)
    setIsMobile(media.matches)
    media.addEventListener?.('change', update)
    return () => media.removeEventListener?.('change', update)
  }, [])

  return isMobile
}

export function ResponsiveTableViewport({ children, mobile, className, tableClassName }) {
  const isMobile = useIsMobileTable()

  return (
    <div className={cn('min-w-0', className)}>
      {isMobile ? (
        <div>{mobile}</div>
      ) : (
        <div
          className={cn(
            'max-w-full overflow-x-auto overscroll-x-contain scroll-smooth [scrollbar-gutter:stable]',
            '[&_thead]:sticky [&_thead]:top-0 [&_thead]:z-10',
            tableClassName,
          )}
        >
          {children}
        </div>
      )}
    </div>
  )
}

export function MobileCardList({ children, className, ariaLabel }) {
  return (
    <div className={cn('space-y-3 p-3', className)} aria-label={ariaLabel}>
      {children}
    </div>
  )
}

export function MobileDataCard({ children, actions, onClick, className, ariaLabel }) {
  const interactive = typeof onClick === 'function'
  return (
    <article
      tabIndex={interactive ? 0 : undefined}
      role={interactive ? 'link' : undefined}
      aria-label={ariaLabel}
      onClick={onClick}
      onKeyDown={interactive ? (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onClick(event)
        }
      } : undefined}
      className={cn(
        'rounded-lg border border-border bg-surface p-4 shadow-sm',
        interactive && 'cursor-pointer transition-colors active:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
    >
      {children}
      {actions && <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">{actions}</div>}
    </article>
  )
}

export function MobileDataRow({ label, children, className }) {
  if (children === null || children === undefined || children === '') return null
  return (
    <div className={cn('grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 py-1.5 text-sm', className)}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-right text-sm font-medium text-secondary-foreground">{children}</dd>
    </div>
  )
}
