import { useState, useEffect } from 'react'
import { PlusIcon, TrashIcon, UserGroupIcon } from '@heroicons/react/24/outline'
import { Spinner, PageShell, PageHeader } from '@/components/ui'
import { Modal } from '@/components/ui/Modal'
import api from '@/api/client'

async function listAssignments() {
  const { data } = await api.get('/staff-assignments')
  return data
}

async function listStaff() {
  const { data } = await api.get('/users?role=staff&per_page=100')
  return data.users || data
}

async function listOrgs() {
  const { data } = await api.get('/organizations?per_page=100')
  return data.organizations || data
}

async function createAssignment(user_id, org_id) {
  await api.post('/staff-assignments', { user_id, org_id })
}

async function deleteAssignment(user_id, org_id) {
  await api.delete(`/staff-assignments?user_id=${user_id}&org_id=${org_id}`)
}

export default function StaffAssignmentsPage() {
  const [assignments, setAssignments] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [staffList, setStaffList] = useState([])
  const [orgList, setOrgList] = useState([])
  const [form, setForm] = useState({ user_id: '', org_id: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [a, s, o] = await Promise.all([listAssignments(), listStaff(), listOrgs()])
      setAssignments(a)
      setStaffList(Array.isArray(s) ? s : s.users || [])
      setOrgList(Array.isArray(o) ? o : o.organizations || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleAdd = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await createAssignment(Number(form.user_id), Number(form.org_id))
      setShowModal(false)
      setForm({ user_id: '', org_id: '' })
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create assignment')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (user_id, org_id) => {
    if (!confirm('Remove this assignment?')) return
    await deleteAssignment(user_id, org_id)
    await load()
  }

  // Group by staff user
  const grouped = assignments.reduce((acc, a) => {
    const key = a.user_id
    if (!acc[key]) acc[key] = { user_id: a.user_id, user_name: a.user_name, user_email: a.user_email, orgs: [] }
    acc[key].orgs.push({ org_id: a.org_id, org_name: a.org_name, org_code: a.org_code })
    return acc
  }, {})

  return (
    <PageShell>
      <PageHeader
        title="Staff Assignments"
        subtitle="Control which staff members can see tickets from each organization."
        actions={(
          <button
            onClick={() => { setShowModal(true); setError('') }}
            className="flex items-center gap-1.5 px-3 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition"
          >
            <PlusIcon className="w-4 h-4" aria-hidden="true" />
            Add assignment
          </button>
        )}
      />

      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="w-6 h-6" /></div>
      ) : Object.keys(grouped).length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <UserGroupIcon className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No assignments yet. Add one to give staff access to customer tickets.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.values(grouped).map((staff) => (
            <div key={staff.user_id} className="rounded-xl border border-border bg-card p-4">
              <div className="mb-3">
                <p className="font-semibold text-foreground text-sm">{staff.user_name}</p>
                <p className="text-xs text-muted-foreground">{staff.user_email}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {staff.orgs.map((org) => (
                  <div key={org.org_id} className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs font-medium">
                    <span>{org.org_name}</span>
                    <button
                      onClick={() => handleDelete(staff.user_id, org.org_id)}
                      className="ml-1 text-blue-500 hover:text-red-500 transition"
                      title="Remove"
                    >
                      <TrashIcon className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={showModal} onClose={() => setShowModal(false)} title="Add Staff Assignment">
        <form onSubmit={handleAdd} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Staff member</label>
            <select
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm"
              value={form.user_id}
              onChange={(e) => setForm({ ...form, user_id: e.target.value })}
              required
            >
              <option value="">Select staff…</option>
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>{s.full_name} ({s.email})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1">Organization</label>
            <select
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm"
              value={form.org_id}
              onChange={(e) => setForm({ ...form, org_id: e.target.value })}
              required
            >
              <option value="">Select organization…</option>
              {orgList.map((o) => (
                <option key={o.id} value={o.id}>{o.name} ({o.code})</option>
              ))}
            </select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 text-sm border border-input rounded-lg hover:bg-muted">Cancel</button>
            <button type="submit" disabled={saving} className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50">
              {saving ? <Spinner className="w-4 h-4" /> : 'Add'}
            </button>
          </div>
        </form>
      </Modal>
    </PageShell>
  )
}
