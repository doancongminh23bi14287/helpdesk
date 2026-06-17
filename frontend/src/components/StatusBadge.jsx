const CONFIG = {
  // Ticket statuses (capitalized from backend)
  'Open':          'bg-blue-50 text-blue-700 border border-blue-200',
  'In Progress':   'bg-amber-50 text-amber-700 border border-amber-200',
  'Waiting':       'bg-purple-50 text-purple-700 border border-purple-200',
  'Resolved':      'bg-green-50 text-green-700 border border-green-200',
  'Closed':        'bg-gray-100 text-gray-600 border border-gray-200',
  // Project statuses (lowercase)
  'open':          'bg-slate-100 text-slate-600',
  'working':       'bg-cyan-100 text-cyan-700',
  'on_hold':       'bg-amber-100 text-amber-700',
  'completed':     'bg-green-100 text-green-700',
  'cancelled':     'bg-slate-100 text-slate-400',
  // Task statuses
  'review':        'bg-cyan-100 text-cyan-700',
  'approved':      'bg-green-100 text-green-700',
  // Subscription / service statuses
  'active':        'bg-green-100 text-green-700',
  'trial':         'bg-blue-100 text-blue-700',
  'past_due':      'bg-amber-100 text-amber-700',
  'expired':       'bg-red-100 text-red-700',
  'inactive':      'bg-slate-100 text-slate-500',
}

const LABEL_MAP = {
  'on_hold':    'On Hold',
  'working':    'Working',
  'open':       'Open',
  'completed':  'Completed',
  'cancelled':  'Cancelled',
  'review':     'Review',
  'approved':   'Approved',
  // Subscription / service statuses
  'active':     'Active',
  'trial':      'Trial',
  'past_due':   'Past Due',
  'expired':    'Expired',
  'inactive':   'Inactive',
}

export function StatusBadge({ status, className = '' }) {
  const cls = CONFIG[status] ?? 'bg-gray-100 text-gray-600'
  const label = LABEL_MAP[status] ?? status ?? ''
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls} ${className}`}>
      {label}
    </span>
  )
}

export default StatusBadge
