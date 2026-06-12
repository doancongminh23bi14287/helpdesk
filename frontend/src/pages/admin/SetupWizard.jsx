import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Spinner } from '@/components/ui'
import { createItem, createContact } from '@/api/items'
import { createOrganization } from '@/api/organizations'
import { createUser } from '@/api/users'
import {
  CheckCircleIcon,
  BuildingOfficeIcon,
  UserIcon,
  CubeIcon,
  UserPlusIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'

// ─── Default data ──────────────────────────────────────────────────────────────

const DEFAULT_ITEMS = [
  { id: 1, code: 'SaaS-BASIC', name: 'Basic SaaS', category: 'saas', unit_price: 500000, billing_cycle: 'month' },
  { id: 2, code: 'SaaS-PRO', name: 'Pro SaaS', category: 'saas', unit_price: 1000000, billing_cycle: 'month' },
  { id: 3, code: 'HOSTING-01', name: 'Web Hosting', category: 'hosting', unit_price: 200000, billing_cycle: 'month' },
  { id: 4, code: 'SUPPORT-01', name: 'Support Package', category: 'support', unit_price: 300000, billing_cycle: 'month' },
]

// ─── Progress Bar ──────────────────────────────────────────────────────────────

function ProgressBar({ step, totalSteps = 6 }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-foreground">Step {step} of {totalSteps}</span>
        <span className="text-xs text-muted-foreground">{Math.round((step / totalSteps) * 100)}% complete</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-300"
          style={{ width: `${(step / totalSteps) * 100}%` }}
        />
      </div>
    </div>
  )
}

// ─── Step Header ──────────────────────────────────────────────────────────────

function StepHeader({ icon: Icon, title, description }) {
  return (
    <div className="flex items-start gap-4 mb-6">
      <div className="p-2.5 bg-primary/10 rounded-xl shrink-0">
        <Icon className="w-5 h-5 text-primary" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {description && <p className="text-sm text-muted-foreground mt-0.5">{description}</p>}
      </div>
    </div>
  )
}

// ─── Navigation Buttons ───────────────────────────────────────────────────────

function StepActions({ onBack, onSkip, onNext, nextLabel = 'Next', loading, hideBack }) {
  return (
    <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
      <div>
        {!hideBack && onBack && (
          <button
            type="button"
            onClick={onBack}
            className="px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
          >
            Back
          </button>
        )}
      </div>
      <div className="flex gap-3">
        {onSkip && (
          <button
            type="button"
            onClick={onSkip}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip
          </button>
        )}
        {onNext && (
          <button
            type="button"
            onClick={onNext}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {loading && <Spinner className="w-3.5 h-3.5" />}
            {nextLabel}
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Error Banner ─────────────────────────────────────────────────────────────

function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-400">
      {message}
    </div>
  )
}

// ─── Step 1: Service Items ────────────────────────────────────────────────────

function Step1Items({ onBack, onNext, onSkip }) {
  const [items, setItems] = useState(DEFAULT_ITEMS.map(i => ({ ...i })))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const updateItem = (id, key, value) =>
    setItems(prev => prev.map(i => i.id === id ? { ...i, [key]: value } : i))

  const removeItem = (id) => setItems(prev => prev.filter(i => i.id !== id))

  const addRow = () =>
    setItems(prev => [
      ...prev,
      { id: Date.now(), code: '', name: '', category: 'saas', unit_price: 0, billing_cycle: 'month' },
    ])

  const handleCreate = async () => {
    const valid = items.filter(i => i.code.trim() && i.name.trim())
    if (valid.length === 0) {
      setError('Add at least one item with a code and name, or click Skip.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const created = []
      for (const item of valid) {
        const result = await createItem({
          code: item.code.trim(),
          name: item.name.trim(),
          category: item.category,
          unit_price: Number(item.unit_price),
          billing_cycle: item.billing_cycle,
        })
        created.push(result)
      }
      onNext({ items: created })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to create items.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <StepHeader
        icon={CubeIcon}
        title="Create Service Items"
        description="Define your service catalog. You can edit, remove, or add new rows."
      />
      <ErrorBanner message={error} />

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Code</th>
              <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Name</th>
              <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Category</th>
              <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Price (VND)</th>
              <th className="text-left px-3 py-2.5 font-medium text-muted-foreground">Cycle</th>
              <th className="px-3 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map(item => (
              <tr key={item.id}>
                <td className="px-2 py-2">
                  <input
                    type="text"
                    value={item.code}
                    onChange={e => updateItem(item.id, 'code', e.target.value)}
                    className="w-24 px-2 py-1.5 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </td>
                <td className="px-2 py-2">
                  <input
                    type="text"
                    value={item.name}
                    onChange={e => updateItem(item.id, 'name', e.target.value)}
                    className="w-full min-w-[120px] px-2 py-1.5 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </td>
                <td className="px-2 py-2">
                  <select
                    value={item.category}
                    onChange={e => updateItem(item.id, 'category', e.target.value)}
                    className="px-2 py-1.5 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="saas">saas</option>
                    <option value="hosting">hosting</option>
                    <option value="support">support</option>
                    <option value="license">license</option>
                    <option value="other">other</option>
                  </select>
                </td>
                <td className="px-2 py-2">
                  <input
                    type="number"
                    value={item.unit_price}
                    onChange={e => updateItem(item.id, 'unit_price', e.target.value)}
                    min={0}
                    className="w-28 px-2 py-1.5 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </td>
                <td className="px-2 py-2">
                  <select
                    value={item.billing_cycle}
                    onChange={e => updateItem(item.id, 'billing_cycle', e.target.value)}
                    className="px-2 py-1.5 border border-input rounded-md bg-background text-foreground text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                  >
                    <option value="month">month</option>
                    <option value="year">year</option>
                    <option value="one_time">one_time</option>
                  </select>
                </td>
                <td className="px-2 py-2">
                  <button
                    type="button"
                    onClick={() => removeItem(item.id)}
                    className="p-1 text-muted-foreground hover:text-red-500 transition-colors"
                    title="Remove row"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={addRow}
        className="mt-3 text-sm text-primary hover:underline"
      >
        + Add row
      </button>

      <StepActions
        onBack={onBack}
        onSkip={() => onNext({ items: [] })}
        onNext={handleCreate}
        nextLabel="Create Items"
        loading={loading}
      />
    </div>
  )
}

// ─── Step 2: Organization ─────────────────────────────────────────────────────

function Step2Organization({ onBack, onNext, onSkip }) {
  const [form, setForm] = useState({ name: '', code: '', contact_email: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleCreate = async () => {
    if (!form.name.trim()) { setError('Organization name is required.'); return }
    if (!form.code.trim()) { setError('Organization code is required.'); return }
    setError('')
    setLoading(true)
    try {
      const payload = { name: form.name.trim(), code: form.code.trim() }
      if (form.contact_email.trim()) payload.contact_email = form.contact_email.trim()
      const org = await createOrganization(payload)
      onNext({ organization: org })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to create organization.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <StepHeader
        icon={BuildingOfficeIcon}
        title="Create Your First Organization"
        description="Organizations represent your customers. At minimum, provide a name and unique code."
      />
      <ErrorBanner message={error} />

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={set('name')}
              placeholder="Acme Corp"
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Code <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.code}
              onChange={set('code')}
              placeholder="ACME"
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-foreground mb-1.5">Contact Email</label>
          <input
            type="email"
            value={form.contact_email}
            onChange={set('contact_email')}
            placeholder="contact@acme.com"
            className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <StepActions
        onBack={onBack}
        onSkip={() => onNext({ organization: null })}
        onNext={handleCreate}
        nextLabel="Create Organization"
        loading={loading}
      />
    </div>
  )
}

// ─── Step 3: Contact ──────────────────────────────────────────────────────────

function Step3Contact({ onBack, onNext, onSkip, organization }) {
  const [form, setForm] = useState({ name: '', email: '', phone: '', role: 'primary' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleCreate = async () => {
    if (!form.name.trim()) { setError('Contact name is required.'); return }
    setError('')
    setLoading(true)
    try {
      const payload = {
        name: form.name.trim(),
        role: form.role,
      }
      if (form.email.trim()) payload.email = form.email.trim()
      if (form.phone.trim()) payload.phone = form.phone.trim()
      const contact = await createContact(organization.id, payload)
      onNext({ contact })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to create contact.')
    } finally {
      setLoading(false)
    }
  }

  if (!organization) {
    return (
      <div>
        <StepHeader
          icon={UserIcon}
          title="Add First Contact"
          description="No organization was created in the previous step."
        />
        <div className="text-sm text-muted-foreground py-6 text-center">
          This step requires an organization. You can go back and create one, or skip to continue.
        </div>
        <StepActions
          onBack={onBack}
          onSkip={() => onNext({ contact: null })}
        />
      </div>
    )
  }

  return (
    <div>
      <StepHeader
        icon={UserIcon}
        title="Add First Contact"
        description={`Create a contact person for ${organization.name}.`}
      />
      <ErrorBanner message={error} />

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={set('name')}
              placeholder="Jane Smith"
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={set('email')}
              placeholder="jane@acme.com"
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
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
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Role</label>
            <select
              value={form.role}
              onChange={set('role')}
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="primary">Primary</option>
              <option value="billing">Billing</option>
              <option value="technical">Technical</option>
            </select>
          </div>
        </div>
      </div>

      <StepActions
        onBack={onBack}
        onSkip={() => onNext({ contact: null })}
        onNext={handleCreate}
        nextLabel="Add Contact"
        loading={loading}
      />
    </div>
  )
}

// ─── Step 4: Customer User ────────────────────────────────────────────────────

function Step4User({ onBack, onNext, onSkip, organization }) {
  const [form, setForm] = useState({
    email: '',
    password: '',
    full_name: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const handleCreate = async () => {
    if (!form.email.trim()) { setError('Email is required.'); return }
    if (!form.password.trim()) { setError('Password is required.'); return }
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (!form.full_name.trim()) { setError('Full name is required.'); return }
    setError('')
    setLoading(true)
    try {
      const payload = {
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim(),
        role: 'customer',
      }
      if (organization?.id) payload.org_id = organization.id
      const user = await createUser(payload)
      onNext({ user })
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to create user.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <StepHeader
        icon={UserPlusIcon}
        title="Create Customer User"
        description="Set up the first customer account for login access."
      />
      <ErrorBanner message={error} />

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              value={form.email}
              onChange={set('email')}
              placeholder="user@acme.com"
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
              placeholder="Jane Smith"
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
            <label className="block text-sm font-medium text-foreground mb-1.5">
              Organization {organization && <span className="text-muted-foreground text-xs">(pre-filled)</span>}
            </label>
            <input
              type="text"
              value={organization?.name ?? ''}
              disabled={!!organization}
              placeholder="No organization linked"
              className="w-full px-3 py-2 border border-input rounded-lg bg-muted text-muted-foreground text-sm cursor-not-allowed"
            />
          </div>
        </div>
      </div>

      <StepActions
        onBack={onBack}
        onSkip={() => onNext({ user: null })}
        onNext={handleCreate}
        nextLabel="Create User"
        loading={loading}
      />
    </div>
  )
}

// ─── Step 5: Done ─────────────────────────────────────────────────────────────

function SummaryRow({ label, value, skipped }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {skipped ? (
        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">Skipped</span>
      ) : (
        <span className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400 font-medium">
          <CheckCircleIcon className="w-4 h-4" />
          {value}
        </span>
      )}
    </div>
  )
}

function Step5Done({ createdData, onViewOrg, onDashboard }) {
  const { items, organization, contact, user } = createdData

  return (
    <div>
      <StepHeader
        icon={SparklesIcon}
        title="Setup Complete!"
        description="Here's a summary of what was created during the wizard."
      />

      <div className="bg-card border border-border rounded-xl p-4 mb-6">
        <SummaryRow
          label="Service Items"
          value={`${items?.length ?? 0} created`}
          skipped={!items || items.length === 0}
        />
        <SummaryRow
          label="Organization"
          value={organization?.name}
          skipped={!organization}
        />
        <SummaryRow
          label="Contact"
          value={contact?.name}
          skipped={!contact}
        />
        <SummaryRow
          label="Customer User"
          value={user?.email}
          skipped={!user}
        />
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        {organization && (
          <button
            type="button"
            onClick={onViewOrg}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            View Your First Organization →
          </button>
        )}
        <button
          type="button"
          onClick={onDashboard}
          className={`flex-1 flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            organization
              ? 'border border-input text-foreground hover:bg-muted'
              : 'bg-primary text-primary-foreground hover:opacity-90'
          }`}
        >
          Go to Dashboard →
        </button>
      </div>
    </div>
  )
}

// ─── Main Wizard ──────────────────────────────────────────────────────────────

export default function SetupWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [createdData, setCreatedData] = useState({
    items: null,
    organization: null,
    contact: null,
    user: null,
  })

  const advance = (data) => {
    setCreatedData(prev => ({ ...prev, ...data }))
    setStep(s => s + 1)
  }

  const goBack = () => setStep(s => s - 1)

  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Page Title */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-foreground">First-Time Setup Wizard</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Complete these steps to get your helpdesk system ready.
        </p>
      </div>

      {/* Card */}
      <div className="bg-card border border-border rounded-xl p-6">
        {/* Progress Bar (not shown on done step) */}
        {step < 5 && <ProgressBar step={step} totalSteps={5} />}

        {step === 1 && (
          <Step1Items
            onNext={(data) => advance(data)}
          />
        )}

        {step === 2 && (
          <Step2Organization
            onBack={goBack}
            onNext={(data) => advance(data)}
          />
        )}

        {step === 3 && (
          <Step3Contact
            onBack={goBack}
            onNext={(data) => advance(data)}
            organization={createdData.organization}
          />
        )}

        {step === 4 && (
          <Step4User
            onBack={goBack}
            onNext={(data) => advance(data)}
            organization={createdData.organization}
          />
        )}

        {step === 5 && (
          <Step5Done
            createdData={createdData}
            onViewOrg={() => navigate('/admin/organizations')}
            onDashboard={() => navigate('/')}
          />
        )}
      </div>
    </div>
  )
}
