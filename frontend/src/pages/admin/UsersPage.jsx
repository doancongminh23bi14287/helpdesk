import { useState, useEffect, useMemo } from 'react'
import { PlusIcon, UserGroupIcon, KeyIcon, ClockIcon, CheckCircleIcon, XCircleIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import { listUsers, createUser, updateUser, resetUserPassword, getUserLoginHistory, deleteUser } from '@/api/users'
import { listOrganizations } from '@/api/organizations'
import { formatDateTime } from '@/lib/utils'
import { useNotificationStore } from '@/hooks/useNotificationStore'
import { SEARCH_DEBOUNCE_MS, PAGE_SIZE } from '@/lib/constants'

const PER_PAGE = PAGE_SIZE

const ROLE_COLORS = {
  admin:    'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  staff:    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  customer: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
}

const EMPTY_FORM = { email: '', password: '', full_name: '', role: 'customer', org_id: '', phone: '' }

function genTempPassword() {
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
  return Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

function TempPasswordModal({ password, onClose }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(password)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <Modal open={!!password} onClose={onClose} title="Temporary Password">
      <div className="space-y-4">
        <p className="text-sm text-foreground">
          The user must change this password on their next login.
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 px-3 py-2 bg-muted rounded-lg font-mono text-sm text-foreground border border-border">
            {password}
          </code>
          <button
            onClick={copy}
            className="px-3 py-2 text-sm border border-input rounded-lg hover:bg-muted transition-colors"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <button
          onClick={onClose}
          className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90"
        >
          Done
        </button>
      </div>
    </Modal>
  )
}

function LoginHistoryModal({ history, onClose }) {
  const STATUS_BADGE = {
    success: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    failed:  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    blocked: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  }
  return (
    <Modal open={!!history} onClose={onClose} title="Login History">
      <div className="max-h-96 overflow-y-auto">
        {!history || history.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">No login history</p>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-2 font-medium text-muted-foreground">Time</th>
                <th className="text-left py-2 px-2 font-medium text-muted-foreground">Status</th>
                <th className="text-left py-2 px-2 font-medium text-muted-foreground">IP</th>
                <th className="text-left py-2 px-2 font-medium text-muted-foreground">Browser</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {history.map((h) => (
                <tr key={h.id}>
                  <td className="py-2 px-2 text-muted-foreground tabular-nums whitespace-nowrap">
                    {formatDateTime(h.created_at)}
                  </td>
                  <td className="py-2 px-2">
                    <span className={`inline-flex px-1.5 py-0.5 rounded-full text-[10px] font-medium capitalize ${STATUS_BADGE[h.status] ?? ''}`}>
                      {h.status}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-muted-foreground font-mono">{h.ip_address ?? '—'}</td>
                  <td className="py-2 px-2 text-muted-foreground truncate max-w-[200px]">
                    {h.user_agent ? h.user_agent.slice(0, 60) + (h.user_agent.length > 60 ? '…' : '') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </Modal>
  )
}

function UserForm({ orgs, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.email.trim()) { setError('Email is required'); return }
    if (!form.password.trim()) { setError('Password is required'); return }
    if (!form.full_name.trim()) { setError('Full name is required'); return }
    if (!form.org_id) { setError('Organization is required'); return }
    try {
      await onSubmit({ ...form, org_id: Number(form.org_id) }, form.password)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'An error occurred')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Email <span className="text-red-500">*</span>
          </label>
          <input
            type="email"
            value={form.email}
            onChange={set('email')}
            placeholder="user@example.com"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Full Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.full_name}
            onChange={set('full_name')}
            placeholder="John Doe"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Password <span className="text-red-500">*</span>
          </label>
          <input
            type="password"
            value={form.password}
            onChange={set('password')}
            placeholder="••••••••"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Phone</label>
          <input
            type="text"
            value={form.phone}
            onChange={set('phone')}
            placeholder="+84 000 000 000"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Role</label>
          <select
            value={form.role}
            onChange={set('role')}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="customer">Customer</option>
            <option value="staff">Staff</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">
            Organization <span className="text-red-500">*</span>
          </label>
          <select
            value={form.org_id}
            onChange={set('org_id')}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Select organization…</option>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading}
          className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {loading && <Spinner className="w-3.5 h-3.5" />}
          Create User
        </button>
      </div>
    </form>
  )
}

export default function UsersPage() {
  const addToast = useNotificationStore((s) => s.addToast)
  const [users, setUsers] = useState([])
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [filterRole, setFilterRole] = useState('all')
  const [filterOrg, setFilterOrg] = useState('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [error, setError] = useState('')

  // Temp password modal state
  const [tempPassword, setTempPassword] = useState('')

  // Login history modal state
  const [loginHistory, setLoginHistory] = useState(null)

  // Delete modal state
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const orgMap = useMemo(() => Object.fromEntries(orgs.map((o) => [o.id, o.name])), [orgs])

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [search])

  // Reset page when search or filters change
  useEffect(() => { setPage(1) }, [debouncedSearch, filterRole, filterOrg])

  const load = async () => {
    try {
      setLoading(true)
      const params = { page, per_page: PER_PAGE }
      if (debouncedSearch) params.search = debouncedSearch
      if (filterRole !== 'all') params.role = filterRole
      if (filterOrg !== 'all') params.org_id = Number(filterOrg)
      const [usersData, orgsData] = await Promise.all([
        listUsers(params),
        listOrganizations({ per_page: 200 }),
      ])
      setUsers(Array.isArray(usersData?.items) ? usersData.items : [])
      setTotal(usersData?.total ?? 0)
      setPages(usersData?.pages ?? 1)
      setOrgs(Array.isArray(orgsData?.items) ? orgsData.items : [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [debouncedSearch, filterRole, filterOrg, page])

  const handleCreate = async (form, password) => {
    setSaving(true)
    try {
      await createUser(form)
      setCreateOpen(false)
      setError('')
      setTempPassword(password)
      load()
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async (u) => {
    if (u.is_active) {
      const confirmed = window.confirm('Deactivating will immediately log out this user. Continue?')
      if (!confirmed) return
    }
    try {
      await updateUser(u.id, { is_active: !u.is_active })
      setError('')
      load()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to update user status')
    }
  }

  const handleResetPassword = async (u) => {
    const tempPw = genTempPassword()
    try {
      await resetUserPassword(u.id, tempPw)
      setError('')
      setTempPassword(tempPw)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to reset password')
    }
  }

  const handleLoginHistory = async (u) => {
    try {
      const history = await getUserLoginHistory(u.id)
      setError('')
      setLoginHistory(history)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to fetch login history')
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteUser(deleteTarget.id)
      setDeleteTarget(null)
      addToast({ type: 'success', message: `User ${deleteTarget.email} deleted` })
      load()
    } catch (err) {
      const detail = err?.response?.data?.detail ?? err?.message ?? 'Delete failed'
      addToast({ type: 'error', message: detail })
      setDeleteTarget(null)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-foreground">Users</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total} total user{total !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
        >
          <PlusIcon className="w-4 h-4" />
          Create User
        </button>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or email…"
          className="flex-1 max-w-xs px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All roles</option>
          <option value="admin">Admin</option>
          <option value="staff">Staff</option>
          <option value="customer">Customer</option>
        </select>
        <select
          value={filterOrg}
          onChange={(e) => setFilterOrg(e.target.value)}
          className="px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All organizations</option>
          {orgs.map((o) => (
            <option key={o.id} value={String(o.id)}>{o.name}</option>
          ))}
        </select>
        {(search || filterRole !== 'all' || filterOrg !== 'all') && (
          <button
            onClick={() => { setSearch(''); setFilterRole('all'); setFilterOrg('all') }}
            className="px-3 py-2 border border-input rounded-lg bg-background text-muted-foreground text-sm hover:text-foreground hover:bg-muted transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
        <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Name</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Email</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Role</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Organization</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Linked Contact</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>
          {loading ? (
            <tbody>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-border">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 bg-muted rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : users.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={7}>
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <UserGroupIcon className="w-10 h-10 text-muted-foreground mb-3" />
                    <p className="font-medium text-foreground">No users found</p>
                    <p className="text-sm text-muted-foreground mt-1">Try adjusting your filters</p>
                  </div>
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody className="divide-y divide-border">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium text-foreground">{u.full_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${ROLE_COLORS[u.role] ?? 'bg-muted text-muted-foreground'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {orgMap[u.org_id] ?? `Org #${u.org_id}`}
                  </td>
                  <td className="px-4 py-3">
                    {u.linked_contact_name ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                        {u.linked_contact_name}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      {/* Activate / Deactivate toggle */}
                      <button
                        onClick={() => handleToggleActive(u)}
                        title={u.is_active ? 'Deactivate user' : 'Activate user'}
                        className={`p-1.5 rounded-md transition-colors ${u.is_active ? 'text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20' : 'text-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-900/20'}`}
                      >
                        {u.is_active
                          ? <XCircleIcon className="w-4 h-4" />
                          : <CheckCircleIcon className="w-4 h-4" />
                        }
                      </button>

                      {/* Reset Password */}
                      <button
                        onClick={() => handleResetPassword(u)}
                        title="Reset password"
                        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      >
                        <KeyIcon className="w-4 h-4" />
                      </button>

                      {/* Login History */}
                      <button
                        onClick={() => handleLoginHistory(u)}
                        title="Login history"
                        className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      >
                        <ClockIcon className="w-4 h-4" />
                      </button>

                      {/* Delete User */}
                      <button
                        type="button"
                        title="Delete user"
                        onClick={() => setDeleteTarget(u)}
                        className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                      >
                        <TrashIcon className="w-4 h-4" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
        </div>
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
      </div>

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create User">
        <UserForm
          orgs={orgs}
          onSubmit={handleCreate}
          onCancel={() => setCreateOpen(false)}
          loading={saving}
        />
      </Modal>

      {/* Temp Password Modal */}
      <TempPasswordModal
        password={tempPassword}
        onClose={() => setTempPassword('')}
      />

      {/* Login History Modal */}
      <LoginHistoryModal
        history={loginHistory}
        onClose={() => setLoginHistory(null)}
      />

      {/* Delete Confirm Modal */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
            <h2 className="text-base font-semibold text-gray-900">Delete user?</h2>
            <p className="text-sm text-gray-600">
              This will permanently delete <strong>{deleteTarget.email}</strong> and cannot be undone.
              If they have open tickets, deletion will be blocked.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setDeleteTarget(null)}
                className="btn-secondary"
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-red-600 hover:bg-red-700 text-white transition-colors disabled:opacity-50"
              >
                {deleting ? 'Deleting…' : 'Delete permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
