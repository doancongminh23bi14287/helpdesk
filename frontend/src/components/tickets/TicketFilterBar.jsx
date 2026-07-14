import { useState } from 'react'
import {
  AdjustmentsHorizontalIcon,
  ArchiveBoxIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { Button, FilterBar, Input, Select } from '@/components/ui'

export const TICKET_PRIORITIES = ['All', 'Urgent', 'High', 'Medium', 'Low']

export function TicketFilterBar({
  search,
  onSearchChange,
  priority,
  onPriorityChange,
  organizations = [],
  organizationId = '',
  onOrganizationChange,
  showOrganization = false,
  showArchived = false,
  onToggleArchived,
  showArchiveToggle = false,
  hasFilters = false,
  onClear,
  loading = false,
  shown = 0,
  total = 0,
}) {
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)
  const activeFilterCount = Number(priority !== 'All')
    + Number(showOrganization && organizationId)
    + Number(showArchived)

  return (
    <FilterBar className="border-x-0 border-t-0 px-4 py-3 sm:px-6">
      <div className="relative w-full sm:w-72">
        <MagnifyingGlassIcon
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search tickets"
          aria-label="Search tickets"
          className="min-h-11 pl-9 pr-9 sm:min-h-0"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:text-foreground"
            aria-label="Clear ticket search"
          >
            <XMarkIcon className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="flex w-full items-center gap-2 sm:hidden">
        <Button
          type="button"
          variant={activeFilterCount ? 'secondary' : 'outline'}
          onClick={() => setMobileFiltersOpen((open) => !open)}
          aria-expanded={mobileFiltersOpen}
          aria-controls="mobile-ticket-filters"
          className="min-h-10 flex-1 justify-center"
        >
          <AdjustmentsHorizontalIcon className="h-4 w-4" aria-hidden="true" />
          Filters
          {activeFilterCount > 0 && (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-info px-1 text-[11px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </Button>
        {!loading && (
          <span className="whitespace-nowrap text-xs text-muted-foreground" aria-live="polite">
            {total === 0 ? 'No results' : shown + ' of ' + total}
          </span>
        )}
      </div>

      <div
        id="mobile-ticket-filters"
        className={(mobileFiltersOpen ? 'grid' : 'hidden') + ' w-full grid-cols-1 gap-2 rounded-md border border-border bg-surface-muted p-3 sm:contents'}
      >
        <Select
          value={priority}
          onChange={(event) => onPriorityChange(event.target.value)}
          aria-label="Filter tickets by priority"
          className="min-h-10 w-full sm:min-h-0 sm:w-44"
        >
          {TICKET_PRIORITIES.map((item) => (
            <option key={item} value={item}>{item === 'All' ? 'All priorities' : item}</option>
          ))}
        </Select>

        {showOrganization && (
          <Select
            value={organizationId}
            onChange={(event) => onOrganizationChange(event.target.value)}
            aria-label="Filter tickets by organization"
            className="min-h-10 w-full sm:min-h-0 sm:w-56"
          >
            <option value="">All organizations</option>
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}{organization.code ? ' (' + organization.code + ')' : ''}
              </option>
            ))}
          </Select>
        )}

        {showArchiveToggle && (
          <Button
            type="button"
            variant={showArchived ? 'secondary' : 'outline'}
            onClick={onToggleArchived}
            aria-pressed={showArchived}
          >
            <ArchiveBoxIcon className="h-4 w-4" aria-hidden="true" />
            {showArchived ? 'Archived tickets' : 'Archive'}
          </Button>
        )}

        {hasFilters && (
          <Button type="button" variant="ghost" onClick={onClear}>
            Clear filters
          </Button>
        )}
      </div>

      {!loading && (
        <span className="ml-auto hidden text-xs text-muted-foreground sm:inline" aria-live="polite">
          {total === 0 ? 'No tickets found' : 'Showing ' + shown + ' of ' + total}
        </span>
      )}
    </FilterBar>
  )
}
