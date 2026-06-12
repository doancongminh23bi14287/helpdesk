import client from './client'

/**
 * List organizations.
 * @param {Object} params - Optional query params: search, page, per_page, sort, order
 * @returns {Promise<Object>} paginated response: { items, total, page, per_page, pages }
 */
export async function listOrganizations(params = {}) {
  const res = await client.get('/organizations', { params })
  return res.data
}

/**
 * Create a new organization (admin only).
 * @param {{ code: string, name: string, address?: string, phone?: string, email?: string }} data
 * @returns {Promise<Object>} created organization
 */
export async function createOrganization(data) {
  const res = await client.post('/organizations', data)
  return res.data
}

/**
 * Fetch a single organization by ID.
 * @param {string|number} id
 * @returns {Promise<Object>}
 */
export async function getOrganization(id) {
  const res = await client.get(`/organizations/${id}`)
  return res.data
}

/**
 * Update an organization (admin only).
 * @param {string|number} id
 * @param {Object} data
 * @returns {Promise<Object>} updated organization
 */
export async function updateOrganization(id, data) {
  const res = await client.put(`/organizations/${id}`, data)
  return res.data
}

/**
 * List services belonging to an organization.
 * @param {string|number} id
 * @returns {Promise<Array>}
 */
export async function getOrgServices(id) {
  const res = await client.get(`/organizations/${id}/services`)
  return res.data
}
