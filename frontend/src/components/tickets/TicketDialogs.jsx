import { Button, Input, Modal, ModalFooter } from '@/components/ui'

export function LinkProjectDialog({
  open,
  onClose,
  search,
  onSearchChange,
  results,
  loading,
  onSelect,
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Link project"
      description="Search projects in this organization and link one to the ticket."
      footer={(
        <ModalFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        </ModalFooter>
      )}
    >
      <div className="space-y-3">
        <Input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search projects"
          aria-label="Search projects"
          autoFocus
        />
        <div className="max-h-64 space-y-1 overflow-y-auto">
          {results.map((project) => (
            <button
              key={project.id}
              type="button"
              onClick={() => onSelect(project.id)}
              disabled={loading}
              className="flex w-full items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-left hover:bg-surface-muted disabled:opacity-50"
            >
              <span className="truncate text-sm font-medium text-foreground">{project.name}</span>
              <span className="text-xs text-muted-foreground">{project.status}</span>
            </button>
          ))}
          {search.trim() && results.length === 0 && (
            <p className="py-5 text-center text-sm text-muted-foreground">No projects found.</p>
          )}
          {!search.trim() && (
            <p className="py-5 text-center text-sm text-muted-foreground">Type to search projects.</p>
          )}
        </div>
      </div>
    </Modal>
  )
}

export function TransferTicketDialog({
  open,
  onClose,
  staff,
  currentUserId,
  onSelect,
}) {
  const candidates = staff.filter((member) => Number(member.id) !== Number(currentUserId))
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Request transfer"
      description="The selected staff member must accept before the ticket is reassigned."
      footer={(
        <ModalFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
        </ModalFooter>
      )}
    >
      <div className="max-h-72 space-y-1 overflow-y-auto">
        {candidates.map((member) => (
          <button
            key={member.id}
            type="button"
            onClick={() => onSelect(member.id)}
            className="w-full rounded-md border border-border px-3 py-2 text-left hover:bg-surface-muted"
          >
            <p className="text-sm font-medium text-foreground">{member.full_name}</p>
            <p className="text-xs text-muted-foreground">{member.email}</p>
          </button>
        ))}
        {candidates.length === 0 && (
          <p className="rounded-md border border-dashed border-border px-3 py-5 text-center text-sm text-muted-foreground">
            No eligible staff are available from the current API response.
          </p>
        )}
      </div>
    </Modal>
  )
}
