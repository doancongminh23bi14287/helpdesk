export const TICKET_STATUSES = ['All', 'Open', 'In Progress', 'Waiting', 'Resolved', 'Closed']

export function TicketStatusTabs({ value, onChange }) {
  return (
    <div
      className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0"
      role="tablist"
      aria-label="Filter tickets by status"
    >
      <div className="flex min-w-max snap-x gap-2 border-b-0 pb-1 sm:gap-1 sm:border-b sm:border-border sm:pb-0">
        {TICKET_STATUSES.map((status) => {
          const selected = value === status
          return (
            <button
              key={status}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(status)}
              className={
                'relative min-h-9 snap-start rounded-full border px-3.5 py-2 text-sm font-medium transition-colors focus-visible:z-10 ' +
                'sm:min-h-0 sm:rounded-none sm:border-0 sm:px-3 sm:py-2.5 ' +
                (selected
                  ? 'border-info/20 bg-info-muted text-info sm:bg-transparent sm:text-foreground sm:after:absolute sm:after:inset-x-2 sm:after:bottom-0 sm:after:h-0.5 sm:after:bg-info'
                  : 'border-border bg-surface text-muted-foreground hover:text-foreground sm:bg-transparent')
              }
            >
              {status}
            </button>
          )
        })}
      </div>
    </div>
  )
}
