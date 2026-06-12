/**
 * ERP bridge layer — single import point for the entire application.
 *
 * Auth is handled via the existing Frappe session cookie — no API keys required.
 *
 * @example
 * import { erpClient } from '@/erp'
 *
 * // List active subscriptions
 * const res = await erpClient.subscription.list({ status: 'Active' })
 * const subs = res.data
 *
 * // Get plan rate
 * const rate = await erpClient.plan.getRate({
 *   plan: 'Basic Plan', quantity: 1, customer: 'Aloha Vietnam',
 *   start_date: '2026-05-01', end_date: '2026-05-31',
 * })
 *
 * // Cancel via doc method
 * await erpClient.subscription.cancel('ACC-SUB-2026-00010')
 *
 * // Dangerous actions require explicit confirmation
 * await erpClient.subscription.delete('ACC-SUB-2026-00010', true)
 */

export { subscriptionService } from './subscription.service'
export { planService } from './plan.service'
export { erpGet, erpPost, erpPut, erpDelete, erpMethod, erpGetMethod } from './client'

import { subscriptionService } from './subscription.service'
import { planService } from './plan.service'

export const erpClient = {
  subscription: subscriptionService,
  plan: planService,
}
