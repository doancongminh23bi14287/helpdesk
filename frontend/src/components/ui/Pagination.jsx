// Simple pagination component used by admin list pages
import { ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'

export default function Pagination({ page, pages, total, perPage, onPage }) {
  if (pages <= 1) return null
  const start = (page - 1) * perPage + 1
  const end = Math.min(page * perPage, total)

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-border">
      <p className="text-sm text-muted-foreground">
        Showing {start}–{end} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeftIcon className="w-4 h-4" />
        </button>
        {/* Page number buttons — show up to 5 pages around current */}
        {getPageRange(page, pages).map((p) =>
          p === '...' ? (
            <span key={`ellipsis-${Math.random()}`} className="px-2 text-muted-foreground text-sm">…</span>
          ) : (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={`w-8 h-8 rounded-md text-sm font-medium transition-colors ${
                p === page
                  ? 'bg-primary text-primary-foreground'
                  : 'text-foreground hover:bg-muted'
              }`}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= pages}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function getPageRange(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  if (current <= 4) return [1, 2, 3, 4, 5, '...', total]
  if (current >= total - 3) return [1, '...', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '...', current - 1, current, current + 1, '...', total]
}
