import client from './client'

// getOrgServices re-export for convenience
export { getOrgServices } from './organizations'

/**
 * List services scoped to current user's role.
 * @param {{ lifecycle?: 'active' | 'archived' | 'all' }} params
 * @returns {Promise<Array>}
 */
export async function listServices(params = {}) {
  const res = await client.get('/services', { params })
  return res.data
}

/**
 * Update a service (admin only).
 * @param {string|number} id
 * @param {Object} data
 * @returns {Promise<Object>}
 */
export async function updateService(id, data) {
  const res = await client.put(`/services/${id}`, data)
  return res.data
}

/**
 * Archive a service (admin only).
 * @param {string|number} id
 * @returns {Promise<Object>}
 */
export async function archiveService(id) {
  const res = await client.put(`/services/${id}/archive`)
  return res.data
}

/**
 * Restore an archived service (admin only).
 * @param {string|number} id
 * @returns {Promise<Object>}
 */
export async function restoreService(id) {
  const res = await client.put(`/services/${id}/restore`)
  return res.data
}

/**
 * Permanently delete a service when there are no dependencies.
 * @param {string|number} id
 * @returns {Promise<Object>}
 */
export async function deleteServicePermanently(id) {
  const res = await client.delete(`/services/${id}/permanent`)
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
