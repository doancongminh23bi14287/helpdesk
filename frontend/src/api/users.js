import client from './client'

/**
 * List all users (admin only).
 * @param {Object} params - Optional query params: search, page, per_page, sort, order
 * @returns {Promise<Object>} paginated response: { items, total, page, per_page, pages }
 */
export async function listUsers(params = {}) {
  const res = await client.get('/users', { params })
  return res.data
}

/**
 * Create a new user (admin only).
 * @param {{ email: string, password: string, full_name: string, role: string, org_id: string|number, phone?: string }} data
 * @returns {Promise<Object>} created user
 */
export async function createUser(data) {
  const res = await client.post('/users', data)
  return res.data
}

/**
 * Update an existing user (admin only).
 * @param {string|number} id
 * @param {{ full_name?: string, phone?: string, role?: string, is_active?: boolean }} data
 * @returns {Promise<Object>} updated user
 */
export async function updateUser(id, data) {
  const res = await client.put(`/users/${id}`, data)
  return res.data
}

export async function resetUserPassword(id, newPassword) {
  const res = await client.post(`/users/${id}/reset-password`, { new_password: newPassword })
  return res.data
}

export async function getUserLoginHistory(id) {
  const res = await client.get(`/users/${id}/login-history`)
  return res.data
}
