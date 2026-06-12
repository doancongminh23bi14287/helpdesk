import { erpDelete, erpGet, erpMethod, erpPost, erpPut } from './client'

const READ_ONLY = ['status', 'cancelation_date', 'current_invoice_start', 'current_invoice_end']

const SUBSCRIPTION_FIELDS = JSON.stringify([
  'name', 'status', 'party', 'party_type', 'company',
  'start_date', 'end_date',
  'current_invoice_start', 'current_invoice_end',
  'cancel_at_period_end', 'submit_invoice', 'generate_invoice_at',
  'plans',
])

const INVOICE_FIELDS = JSON.stringify([
  'name', 'status', 'grand_total', 'due_date', 'subscription',
])

/** Strips ERPNext read-only fields before create/update payloads. */
function stripReadOnly(data) {
  const clean = { ...data }
  for (const field of READ_ONLY) delete clean[field]
  return clean
}

/**
 * Calls a controller method on a Subscription document.
 * Uses frappe.client.run_doc_method — the standard way to invoke doc methods
 * via the /api/resource/ layer (doc-level methods aren't routed through /resource/).
 */
function runDocMethod(name, method) {
  return erpMethod('/frappe.client.run_doc_method', {
    dt: 'Subscription',
    dn: name,
    method,
    args: '{}',
  })
}

export const subscriptionService = {
  /**
   * List Subscription documents.
   * Accepts filters: { status, party, party_type, company }
   */
  async list(filters = {}) {
    const erpFilters = Object.entries(filters).map(([k, v]) => [k, '=', v])
    return erpGet('/Subscription', {
      fields: SUBSCRIPTION_FIELDS,
      filters: JSON.stringify(erpFilters),
      limit: 100,
      order_by: 'creation desc',
    })
  },

  /** Fetch a single Subscription by document name. */
  async get(name) {
    return erpGet(`/Subscription/${encodeURIComponent(name)}`)
  },

  /**
   * Create a new Subscription.
   * Required: party_type, party, generate_invoice_at, plans (min 1 row).
   * Read-only fields are stripped automatically.
   */
  async create(data) {
    if (!data.party_type) throw new Error('party_type is required')
    if (!data.party) throw new Error('party is required')
    if (!data.generate_invoice_at) throw new Error('generate_invoice_at is required')
    if (!data.plans?.length) throw new Error('At least one plan row is required')

    return erpPost('/Subscription', stripReadOnly(data))
  },

  /**
   * Update mutable fields on an existing Subscription.
   * Only cancel_at_period_end, submit_invoice, and plans are accepted.
   * party_type, party, start_date, end_date cannot change after creation.
   */
  async update(name, data) {
    const allowed = ['cancel_at_period_end', 'submit_invoice', 'plans']
    const safe = Object.fromEntries(
      Object.entries(data).filter(([k]) => allowed.includes(k))
    )
    return erpPut(`/Subscription/${encodeURIComponent(name)}`, safe)
  },

  /** Cancel the subscription via ERPNext controller method. */
  async cancel(name) {
    return runDocMethod(name, 'cancel_subscription')
  },

  /** Restart a previously cancelled subscription. */
  async restart(name) {
    return runDocMethod(name, 'restart_subscription')
  },

  /**
   * DESTRUCTIVE — permanently deletes the document.
   * Must pass confirm=true or the call throws before reaching ERP.
   */
  async delete(name, confirm) {
    if (confirm !== true) {
      throw new Error('delete requires confirm=true — this action is irreversible')
    }
    return erpDelete(`/Subscription/${encodeURIComponent(name)}`)
  },

  /**
   * HIGH RISK — triggers invoice generation and billing cycle advancement.
   * Must pass confirm=true explicitly.
   */
  async process(name, confirm) {
    if (confirm !== true) {
      throw new Error('process requires confirm=true — this triggers billing cycle processing')
    }
    return runDocMethod(name, 'process')
  },

  /** Returns all Sales Invoices linked to the given Subscription name. */
  async getInvoices(subscriptionName) {
    return erpGet('/Sales%20Invoice', {
      fields: INVOICE_FIELDS,
      filters: JSON.stringify([['subscription', '=', subscriptionName]]),
    })
  },
}
