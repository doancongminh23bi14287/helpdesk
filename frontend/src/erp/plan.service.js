import { erpGet, erpGetMethod } from './client'

const PLAN_FIELDS = JSON.stringify([
  'name', 'plan_name', 'cost', 'currency',
  'billing_interval', 'billing_interval_count',
  'price_determination', 'item',
])

export const planService = {
  /** List all Subscription Plan documents. */
  async list() {
    return erpGet('/Subscription%20Plan', { fields: PLAN_FIELDS })
  },

  /** Fetch a single Subscription Plan by name. */
  async get(name) {
    return erpGet(`/Subscription%20Plan/${encodeURIComponent(name)}`)
  },

  /**
   * Get the effective rate for a plan given customer, quantity, and date range.
   * Accounts for Fixed Rate / Price List / Monthly Rate price_determination.
   *
   * @param {{ plan, quantity, customer, start_date, end_date }} params
   * @returns {Promise<number>} Calculated rate in the plan's currency.
   */
  async getRate({ plan, quantity, customer, start_date, end_date }) {
    const res = await erpGetMethod(
      '/erpnext.accounts.doctype.subscription_plan.subscription_plan.get_plan_rate',
      { plan, quantity, customer, start_date, end_date },
    )
    // Frappe method responses wrap the return value in res.message
    return res.message
  },
}
