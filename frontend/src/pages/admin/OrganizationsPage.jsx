import { useState, useEffect } from 'react'
import { PlusIcon, PencilIcon, BuildingOffice2Icon, TrashIcon, UserCircleIcon, MapPinIcon } from '@heroicons/react/24/outline'
import {
  Button,
  DataTable,
  DataTableScroll,
  EmptyState,
  ErrorState,
  FilterBar,
  FormField,
  IconButton,
  Input,
  Modal,
  ModalFooter,
  LoadingState,
  MobileCardList,
  MobileDataCard,
  MobileDataRow,
  PageHeader,
  ResponsiveTableViewport,
  PageShell,
  Select,
  Spinner,
  StatusBadge,
  Textarea,
} from '@/components/ui'
import Pagination from '@/components/ui/Pagination'
import { listOrganizations, createOrganization, updateOrganization } from '@/api/organizations'
import {
  listContacts, createContact, updateContact, deleteContact,
  listAddresses, createAddress, updateAddress, deleteAddress,
  linkContactToUser,
} from '@/api/items'
import { createUser } from '@/api/users'
import { SEARCH_DEBOUNCE_MS, PAGE_SIZE } from '@/lib/constants'

const ROLE_COLORS = {
  primary:   'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  billing:   'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  technical: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  other:     'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
}

const EMPTY_ORG_FORM = { name: '', code: '', contact_email: '', phone: '', status: 'active', notes: '' }

function OrgForm({ initial = EMPTY_ORG_FORM, onSubmit, onCancel, loading, isEdit }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const set = (key) => (event) => setForm((value) => ({ ...value, [key]: event.target.value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    if (!form.name.trim()) { setError('Name is required'); return }
    if (!form.code.trim()) { setError('Code is required'); return }
    try {
      await onSubmit(form)
    } catch (requestError) {
      setError(requestError?.response?.data?.detail ?? 'An error occurred')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <ErrorState title="Unable to save organization" description={error} />}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField label="Name" required>
          <Input type="text" value={form.name} onChange={set('name')} placeholder="Company name" />
        </FormField>
        <FormField label="Code" required helperText={isEdit ? 'Organization codes cannot be changed.' : undefined}>
          <Input type="text" value={form.code} onChange={set('code')} placeholder="ORG-001" disabled={isEdit} />
        </FormField>
        <FormField label="Contact Email">
          <Input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="contact@company.com" />
        </FormField>
        <FormField label="Phone">
          <Input type="text" value={form.phone} onChange={set('phone')} placeholder="+84 000 000 000" />
        </FormField>
      </div>
      <FormField label="Status">
        <Select value={form.status} onChange={set('status')}>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </Select>
      </FormField>
      <FormField label="Notes" helperText="Optional">
        <Textarea value={form.notes} onChange={set('notes')} rows={3} placeholder="Notes about this organization" />
      </FormField>
      <ModalFooter>
        <Button type="button" variant="outline" onClick={onCancel} disabled={loading}>Cancel</Button>
        <Button type="submit" isLoading={loading} loadingText={isEdit ? 'Saving…' : 'Creating…'}>
          {isEdit ? 'Save Changes' : 'Create Organization'}
        </Button>
      </ModalFooter>
    </form>
  )
}

/* ── Contact form ── */
const EMPTY_CONTACT = { name: '', email: '', phone: '', role: 'primary' }
function ContactForm({ initial = EMPTY_CONTACT, onSubmit, onCancel, loading, isEdit }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const handle = async (e) => {
    e.preventDefault(); setError('')
    if (!form.name.trim()) { setError('Name required'); return }
    try { await onSubmit(form) } catch (err) { setError(err?.response?.data?.detail ?? 'Error') }
  }
  return (
    <form onSubmit={handle} className="space-y-4">
      {error && <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Name <span className="text-red-500">*</span></label>
          <input type="text" value={form.name} onChange={set('name')} placeholder="Full name"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Role</label>
          <select value={form.role} onChange={set('role')}
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring">
            <option value="primary">Primary</option>
            <option value="billing">Billing</option>
            <option value="technical">Technical</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Email</label>
          <input type="email" value={form.email} onChange={set('email')} placeholder="name@company.com"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Phone</label>
          <input type="text" value={form.phone} onChange={set('phone')} placeholder="0900 000 000"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onCancel} className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors">Cancel</button>
        <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
          {loading && <Spinner className="w-3.5 h-3.5" />}{isEdit ? 'Save' : 'Add Contact'}
        </button>
      </div>
    </form>
  )
}

/* ── Address form ── */
const EMPTY_ADDR = { label: '', street: '', city: '', province: '', country: 'Vietnam', postal_code: '', is_default: false }
function AddressForm({ initial = EMPTY_ADDR, onSubmit, onCancel, loading }) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setCheck = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))
  const handle = async (e) => {
    e.preventDefault(); setError('')
    if (!form.label.trim()) { setError('Label required'); return }
    try { await onSubmit(form) } catch (err) { setError(err?.response?.data?.detail ?? 'Error') }
  }
  return (
    <form onSubmit={handle} className="space-y-4">
      {error && <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Label <span className="text-red-500">*</span></label>
          <input type="text" value={form.label} onChange={set('label')} placeholder="HQ"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Country</label>
          <input type="text" value={form.country} onChange={set('country')} placeholder="Vietnam"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Street</label>
        <input type="text" value={form.street} onChange={set('street')} placeholder="123 Nguyen Hue"
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">City</label>
          <input type="text" value={form.city} onChange={set('city')} placeholder="Ho Chi Minh City"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Province</label>
          <input type="text" value={form.province} onChange={set('province')} placeholder="Ho Chi Minh"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <input type="checkbox" id="addr_default" checked={form.is_default} onChange={setCheck('is_default')} className="w-4 h-4 rounded border-input accent-primary" />
        <label htmlFor="addr_default" className="text-sm font-medium text-foreground cursor-pointer">Default address</label>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onCancel} className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors">Cancel</button>
        <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
          {loading && <Spinner className="w-3.5 h-3.5" />}Save Address
        </button>
      </div>
    </form>
  )
}

function genPassword() {
  const chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
  return Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

function CreatePortalUserModal({ contact, orgId, onClose, onCreated }) {
  const [form, setForm] = useState({
    email: contact.email ?? '',
    full_name: contact.name,
    password: genPassword(),
    role: 'customer',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!form.email.trim()) { setError('Email is required'); return }
    setSaving(true)
    try {
      const newUser = await createUser({ ...form, org_id: orgId })
      await linkContactToUser(orgId, contact.id, newUser.id)
      onCreated()
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'An error occurred')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">{error}</div>}
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Email <span className="text-red-500">*</span></label>
        <input type="email" value={form.email} onChange={set('email')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Full Name</label>
        <input type="text" value={form.full_name} onChange={set('full_name')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Temporary Password</label>
        <input type="text" value={form.password} onChange={set('password')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring" />
        <p className="mt-1 text-xs text-muted-foreground">User must change this on first login.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1.5">Role</label>
        <select value={form.role} onChange={set('role')}
          className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring">
          <option value="customer">Customer</option>
          <option value="staff">Staff</option>
          <option value="admin">Admin</option>
        </select>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onClose}
          className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors">Cancel</button>
        <button type="submit" disabled={saving}
          className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
          {saving && <Spinner className="w-3.5 h-3.5" />}Create & Link
        </button>
      </div>
    </form>
  )
}

/* ── Contacts tab ── */
function ContactsTab({ orgId }) {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editContact, setEditContact] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [portalContact, setPortalContact] = useState(null)

  const load = async () => {
    try { setLoading(true); setContacts(await listContacts(orgId)) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [orgId])

  const handleAdd = async (form) => {
    setSaving(true); try { await createContact(orgId, form); setAddOpen(false); load() } finally { setSaving(false) }
  }
  const handleEdit = async (form) => {
    setSaving(true); try { await updateContact(orgId, editContact.id, form); setEditContact(null); load() } finally { setSaving(false) }
  }
  const handleDelete = async () => {
    setSaving(true); try { await deleteContact(orgId, deleteTarget); setDeleteTarget(null); load() } finally { setSaving(false) }
  }

  if (loading) return <div className="flex justify-center py-10"><Spinner className="w-5 h-5" /></div>

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <p className="text-sm text-muted-foreground">{contacts.length} contact{contacts.length !== 1 ? 's' : ''}</p>
        <button onClick={() => setAddOpen(true)} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:opacity-90 transition-opacity">
          <PlusIcon className="w-3.5 h-3.5" />Add Contact
        </button>
      </div>
      {contacts.length === 0 ? (
        <div className="flex flex-col items-center py-10 text-center">
          <UserCircleIcon className="w-8 h-8 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">No contacts yet</p>
        </div>
      ) : (
        <ResponsiveTableViewport
          mobile={(
            <MobileCardList ariaLabel="Organization contacts" className="p-0">
              {contacts.map((c) => (
                <MobileDataCard
                  key={c.id}
                  actions={(
                    <>
                      {!c.is_portal_user && (
                        <Button type="button" size="sm" variant="outline" onClick={() => setPortalContact(c)}>
                          Create portal user
                        </Button>
                      )}
                      <Button type="button" size="sm" variant="outline" onClick={() => setEditContact(c)}>Edit</Button>
                      <Button type="button" size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleteTarget(c.id)}>Delete</Button>
                    </>
                  )}
                >
                  <h4 className="text-base font-semibold text-foreground">{c.name}</h4>
                  <dl className="mt-2 divide-y divide-border">
                    <MobileDataRow label="Role">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${ROLE_COLORS[c.role] ?? ROLE_COLORS.other}`}>{c.role}</span>
                    </MobileDataRow>
                    <MobileDataRow label="Email">{c.email || 'Not provided'}</MobileDataRow>
                    <MobileDataRow label="Portal user">{c.is_portal_user ? c.user_email : 'Not created'}</MobileDataRow>
                  </dl>
                </MobileDataCard>
              ))}
            </MobileCardList>
          )}
        >
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="border-b border-border bg-muted/40">
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Name</th>
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Role</th>
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Email</th>
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Portal User</th>
            <th className="px-3 py-2" />
          </tr></thead>
          <tbody className="divide-y divide-border">
            {contacts.map((c) => (
              <tr key={c.id} className="hover:bg-muted/20 transition-colors">
                <td className="px-3 py-2 font-medium text-foreground">{c.name}</td>
                <td className="px-3 py-2"><span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${ROLE_COLORS[c.role] ?? ROLE_COLORS.other}`}>{c.role}</span></td>
                <td className="px-3 py-2 text-muted-foreground">{c.email ?? '—'}</td>
                <td className="px-3 py-2">
                  {c.is_portal_user ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                      {c.user_email}
                    </span>
                  ) : (
                    <button onClick={() => setPortalContact(c)}
                      className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border border-dashed border-muted-foreground text-muted-foreground hover:border-primary hover:text-primary transition-colors">
                      <PlusIcon className="w-3 h-3" />Create Portal User
                    </button>
                  )}
                </td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <button onClick={() => setEditContact(c)} className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><PencilIcon className="w-3.5 h-3.5" /></button>
                    <button onClick={() => setDeleteTarget(c.id)} className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"><TrashIcon className="w-3.5 h-3.5" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </ResponsiveTableViewport>
      )}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add Contact">
        <ContactForm onSubmit={handleAdd} onCancel={() => setAddOpen(false)} loading={saving} isEdit={false} />
      </Modal>
      <Modal open={!!editContact} onClose={() => setEditContact(null)} title="Edit Contact">
        {editContact && <ContactForm initial={{ name: editContact.name, email: editContact.email ?? '', phone: editContact.phone ?? '', role: editContact.role }} onSubmit={handleEdit} onCancel={() => setEditContact(null)} loading={saving} isEdit />}
      </Modal>
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Contact">
        <div className="space-y-4">
          <p className="text-sm text-foreground">Delete this contact permanently?</p>
          <div className="flex gap-3"><button onClick={() => setDeleteTarget(null)} className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium hover:bg-muted transition-colors">Cancel</button><button onClick={handleDelete} disabled={saving} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">{saving && <Spinner className="w-3.5 h-3.5" />}Delete</button></div>
        </div>
      </Modal>
      <Modal open={!!portalContact} onClose={() => setPortalContact(null)} title="Create Portal User">
        {portalContact && (
          <CreatePortalUserModal
            contact={portalContact}
            orgId={orgId}
            onClose={() => setPortalContact(null)}
            onCreated={() => { setPortalContact(null); load() }}
          />
        )}
      </Modal>
    </div>
  )
}

/* ── Addresses tab ── */
function AddressesTab({ orgId }) {
  const [addresses, setAddresses] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editAddr, setEditAddr] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const load = async () => {
    try { setLoading(true); setAddresses(await listAddresses(orgId)) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [orgId])

  const handleAdd = async (form) => {
    setSaving(true); try { await createAddress(orgId, form); setAddOpen(false); load() } finally { setSaving(false) }
  }
  const handleEdit = async (form) => {
    setSaving(true); try { await updateAddress(orgId, editAddr.id, form); setEditAddr(null); load() } finally { setSaving(false) }
  }
  const handleDelete = async () => {
    setSaving(true); try { await deleteAddress(orgId, deleteTarget); setDeleteTarget(null); load() } finally { setSaving(false) }
  }

  const fmtAddr = (a) => [a.street, a.city, a.province].filter(Boolean).join(', ')

  if (loading) return <div className="flex justify-center py-10"><Spinner className="w-5 h-5" /></div>

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <p className="text-sm text-muted-foreground">{addresses.length} address{addresses.length !== 1 ? 'es' : ''}</p>
        <button onClick={() => setAddOpen(true)} className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:opacity-90 transition-opacity">
          <PlusIcon className="w-3.5 h-3.5" />Add Address
        </button>
      </div>
      {addresses.length === 0 ? (
        <div className="flex flex-col items-center py-10 text-center">
          <MapPinIcon className="w-8 h-8 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">No addresses yet</p>
        </div>
      ) : (
        <ResponsiveTableViewport
          mobile={(
            <MobileCardList ariaLabel="Organization addresses" className="p-0">
              {addresses.map((a) => (
                <MobileDataCard
                  key={a.id}
                  actions={(
                    <>
                      <Button type="button" size="sm" variant="outline" onClick={() => setEditAddr(a)}>Edit</Button>
                      <Button type="button" size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleteTarget(a.id)}>Delete</Button>
                    </>
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-base font-semibold text-foreground">{a.label}</h4>
                    {a.is_default && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">Default</span>}
                  </div>
                  <dl className="mt-2 divide-y divide-border">
                    <MobileDataRow label="Address">{fmtAddr(a) || 'Not provided'}</MobileDataRow>
                    <MobileDataRow label="Country">{a.country}</MobileDataRow>
                  </dl>
                </MobileDataCard>
              ))}
            </MobileCardList>
          )}
        >
        <table className="w-full min-w-[560px] text-sm">
          <thead><tr className="border-b border-border bg-muted/40">
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Label</th>
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Address</th>
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Country</th>
            <th className="px-3 py-2" />
          </tr></thead>
          <tbody className="divide-y divide-border">
            {addresses.map((a) => (
              <tr key={a.id} className="hover:bg-muted/20 transition-colors">
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground">{a.label}</span>
                    {a.is_default && <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">Default</span>}
                  </div>
                </td>
                <td className="px-3 py-2 text-muted-foreground">{fmtAddr(a) || '—'}</td>
                <td className="px-3 py-2 text-muted-foreground">{a.country}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1">
                    <button onClick={() => setEditAddr(a)} className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"><PencilIcon className="w-3.5 h-3.5" /></button>
                    <button onClick={() => setDeleteTarget(a.id)} className="p-1 rounded text-muted-foreground hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"><TrashIcon className="w-3.5 h-3.5" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </ResponsiveTableViewport>
      )}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add Address">
        <AddressForm onSubmit={handleAdd} onCancel={() => setAddOpen(false)} loading={saving} />
      </Modal>
      <Modal open={!!editAddr} onClose={() => setEditAddr(null)} title="Edit Address">
        {editAddr && <AddressForm initial={{ label: editAddr.label, street: editAddr.street ?? '', city: editAddr.city ?? '', province: editAddr.province ?? '', country: editAddr.country, postal_code: editAddr.postal_code ?? '', is_default: editAddr.is_default }} onSubmit={handleEdit} onCancel={() => setEditAddr(null)} loading={saving} />}
      </Modal>
      <Modal open={!!deleteTarget} onClose={() => setDeleteTarget(null)} title="Delete Address">
        <div className="space-y-4">
          <p className="text-sm text-foreground">Delete this address permanently?</p>
          <div className="flex gap-3"><button onClick={() => setDeleteTarget(null)} className="flex-1 px-4 py-2 border border-input rounded-lg text-sm font-medium hover:bg-muted transition-colors">Cancel</button><button onClick={handleDelete} disabled={saving} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">{saving && <Spinner className="w-3.5 h-3.5" />}Delete</button></div>
        </div>
      </Modal>
    </div>
  )
}

/* ── Org detail modal (tabbed) ── */
const TABS = ['Details', 'Contacts', 'Addresses']

function OrgDetailModal({ org, onClose, onSaved }) {
  const [tab, setTab] = useState('Details')
  const [saving, setSaving] = useState(false)

  const handleEdit = async (form) => {
    setSaving(true)
    try { await updateOrganization(org.id, form); onSaved() } finally { setSaving(false) }
  }

  return (
    <Modal open={true} onClose={onClose} title={org.name} className="max-w-2xl">
      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-border -mt-2">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${tab === t ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === 'Details' && (
        <OrgForm
          initial={{ name: org.name, code: org.code, contact_email: org.contact_email ?? '', phone: org.phone ?? '', status: org.status, notes: org.notes ?? '' }}
          onSubmit={handleEdit} onCancel={onClose} loading={saving} isEdit
        />
      )}
      {tab === 'Contacts' && <ContactsTab orgId={org.id} />}
      {tab === 'Addresses' && <AddressesTab orgId={org.id} />}
    </Modal>
  )
}

const PER_PAGE = PAGE_SIZE

/* ── Main page ── */
export default function OrganizationsPage() {
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [detailOrg, setDetailOrg] = useState(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [search])

  // Reset page when search changes
  useEffect(() => { setPage(1) }, [debouncedSearch])

  const load = async () => {
    try {
      setLoading(true)
      const params = { page, per_page: PER_PAGE }
      if (debouncedSearch) params.search = debouncedSearch
      const orgsData = await listOrganizations(params)
      setOrgs(Array.isArray(orgsData?.items) ? orgsData.items : [])
      setTotal(orgsData?.total ?? 0)
      setPages(orgsData?.pages ?? 1)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [debouncedSearch, page])

  const handleCreate = async (form) => {
    setSaving(true)
    try { await createOrganization(form); setCreateOpen(false); load() } finally { setSaving(false) }
  }

  const handleSaved = () => { setDetailOrg(null); load() }

  return (
    <PageShell>
      <PageHeader
        title="Organizations"
        subtitle="Manage customer organizations"
        actions={(
          <Button type="button" onClick={() => setCreateOpen(true)}>
            <PlusIcon className="h-4 w-4" aria-hidden="true" />
            Create Organization
          </Button>
        )}
      />

      {/* Search */}
      <FilterBar>
        <Input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search by name, code, or email…"
          className="w-full sm:w-80"
          aria-label="Search organizations"
        />
        {search && <Button type="button" variant="outline" onClick={() => setSearch('')}>Clear</Button>}
      </FilterBar>

      <DataTable ariaLabel="Organizations">
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} className="border-t-0 border-b border-border" />
        <ResponsiveTableViewport
          mobile={loading ? (
            <LoadingState rows={3} label="Loading organizations" />
          ) : orgs.length === 0 ? (
            <EmptyState
              icon={BuildingOffice2Icon}
              title={search ? 'No matching organizations' : 'No organizations yet'}
              description={search ? 'Try changing or clearing your search.' : 'Create one to get started.'}
            />
          ) : (
            <MobileCardList ariaLabel="Organizations">
              {orgs.map((org) => (
                <MobileDataCard
                  key={org.id}
                  onClick={() => setDetailOrg(org)}
                  ariaLabel={`View ${org.name}`}
                  actions={(
                    <Button type="button" size="sm" variant="outline" onClick={() => setDetailOrg(org)}>
                      View details
                    </Button>
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-base font-semibold text-foreground" title={org.name}>{org.name}</h3>
                      <p className="mt-0.5 font-mono text-xs text-muted-foreground">{org.code}</p>
                    </div>
                    <StatusBadge status={org.status} />
                  </div>
                  <dl className="mt-3 divide-y divide-border">
                    <MobileDataRow label="Email">{org.contact_email || 'Not provided'}</MobileDataRow>
                    <MobileDataRow label="Contacts">{org.contacts_count ?? 0}</MobileDataRow>
                    <MobileDataRow label="Addresses">{org.addresses_count ?? 0}</MobileDataRow>
                  </dl>
                </MobileDataCard>
              ))}
            </MobileCardList>
          )}
        >
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Code</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Name</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Contact Email</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Contacts</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          {loading ? (
            <tbody>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-border">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-4 skeleton-shimmer rounded" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          ) : orgs.length === 0 ? (
            <tbody>
              <tr>
                <td colSpan={6}>
                  <EmptyState
                    icon={BuildingOffice2Icon}
                    title={search ? 'No matching organizations' : 'No organizations yet'}
                    description={search ? 'Try changing or clearing your search.' : 'Create one to get started.'}
                  />
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody className="divide-y divide-border">
              {orgs.map((org) => (
                <tr key={org.id} className="hover:bg-muted/30 transition-colors cursor-pointer" onClick={() => setDetailOrg(org)}>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{org.code}</td>
                  <td className="px-4 py-3 font-medium text-foreground">{org.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{org.contact_email ?? '—'}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {org.contacts_count ?? 0} / {org.addresses_count ?? 0}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={org.status} />
                  </td>
                  <td className="px-4 py-3">
                    <IconButton label={`Edit ${org.name}`} onClick={(event) => { event.stopPropagation(); setDetailOrg(org) }}>
                      <PencilIcon className="h-4 w-4" aria-hidden="true" />
                    </IconButton>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
        </ResponsiveTableViewport>
        <Pagination page={page} pages={pages} total={total} perPage={PER_PAGE} onPage={setPage} />
      </DataTable>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create Organization"
        description="Add a customer organization to CustomerHub."
      >
        <OrgForm onSubmit={handleCreate} onCancel={() => setCreateOpen(false)} loading={saving} isEdit={false} />
      </Modal>

      {detailOrg && (
        <OrgDetailModal org={detailOrg} onClose={() => setDetailOrg(null)} onSaved={handleSaved} />
      )}
    </PageShell>
  )
}
