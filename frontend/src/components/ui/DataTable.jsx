import { cn } from '@/lib/utils'

export function DataTable({ children, className, ariaLabel }) {
  return (
    <section
      className={cn('min-w-0 overflow-hidden rounded-lg border border-border bg-surface shadow-sm', className)}
      aria-label={ariaLabel}
    >
      {children}
    </section>
  )
}

export function DataTableScroll({ children, className }) {
  return <div className={cn('max-w-full overflow-x-auto overscroll-x-contain scroll-smooth scrollbar-thin [scrollbar-gutter:stable] [&_thead]:sticky [&_thead]:top-0 [&_thead]:z-10', className)}>{children}</div>
}

export function Table({ children, className, ...props }) {
  return <table className={cn('w-full min-w-[640px] text-sm', className)} {...props}>{children}</table>
}

export function TableHead({ children, sticky = false, className }) {
  return (
    <thead className={cn('bg-surface-muted', sticky && 'sticky top-0 z-10', className)}>
      {children}
    </thead>
  )
}

export function TableRow({ children, clickable = false, className, ...props }) {
  return (
    <tr
      className={cn(
        'border-b border-border transition-colors last:border-b-0',
        clickable && 'cursor-pointer hover:bg-surface-muted focus-within:bg-surface-muted',
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  )
}

export function TableHeaderCell({ children, align = 'left', className, ...props }) {
  return (
    <th
      scope="col"
      className={cn(
        'px-4 py-3 table-header',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        className,
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export function TableCell({ children, align = 'left', className, ...props }) {
  return (
    <td
      className={cn(
        'px-4 py-3 text-foreground',
        align === 'right' && 'text-right tabular-nums',
        align === 'center' && 'text-center',
        className,
      )}
      {...props}
    >
      {children}
    </td>
  )
}
