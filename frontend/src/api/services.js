import client from './client'

// getOrgServices re-export for convenience
export { getOrgServices } from './organizations'

/**
 * List services scoped to current user's role.
 * @returns {Promise<Array>}
 */
export async function listServices() {
  const res = await client.get('/services')
  return res.data
}

/**
 * Stub — old pages may call this.
 * @returns {Promise<{ hosting: Array, subscriptions: Array }>}
 */
export async function getCustomerServices() {
  return { hosting: [], subscriptions: [] }
}

/**
 * Stub — subscription management not available in new backend.
 * @returns {Promise<null>}
 */
export async function renewSubscription() {
  return null
}

/**
 * Stub — subscription management not available in new backend.
 * @returns {Promise<null>}
 */
export async function cancelSubscription() {
  return null
}
