import { useEffect } from 'react'
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import { IconButton } from '@/components/ui-shadcn/button'
import { cn } from '@/lib/utils'

export default function Pagination({ page, pages, total, perPage, onPage, className = '' }) {
  useEffect(() => {
    if (pages <= 1) return undefined
    const handler = (event) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName)) return
      if (event.key === 'ArrowLeft' && page > 1) onPage(page - 1)
      if (event.key === 'ArrowRight' && page < pages) onPage(page + 1)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [page, pages, onPage])

  if (pages <= 1) return null

  const start = (page - 1) * perPage + 1
  const end = Math.min(page * perPage, total)

  return (
    <nav className={cn('flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between', className)} aria-label="Pagination">
      <p className="metadata-text">Showing {start}–{end} of {total}</p>
      <div className="flex items-center gap-1">
        <IconButton label="Previous page" onClick={() => onPage(page - 1)} disabled={page <= 1}>
          <ChevronLeftIcon className="h-4 w-4" aria-hidden="true" />
        </IconButton>
        {getPageRange(page, pages).map((item, index) =>
          item === '...' ? (
            <span key={`ellipsis-${index}`} className="px-2 text-sm text-muted-foreground">…</span>
          ) : (
            <button
              key={item}
              type="button"
              onClick={() => onPage(item)}
              aria-current={item === page ? 'page' : undefined}
              className={cn(
                'h-8 min-w-8 rounded-md px-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-ring',
                item === page ? 'bg-sidebar-active text-white' : 'text-secondary-foreground hover:bg-surface-muted hover:text-foreground',
              )}
            >
              {item}
            </button>
          ),
        )}
        <IconButton label="Next page" onClick={() => onPage(page + 1)} disabled={page >= pages}>
          <ChevronRightIcon className="h-4 w-4" aria-hidden="true" />
        </IconButton>
      </div>
    </nav>
  )
}

function getPageRange(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)
  if (current <= 4) return [1, 2, 3, 4, 5, '...', total]
  if (current >= total - 3) return [1, '...', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '...', current - 1, current, current + 1, '...', total]
}
