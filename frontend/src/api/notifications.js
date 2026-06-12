import client from './client'

/**
 * Fetch all notifications for the current user.
 * @returns {Promise<Array<{ id, user_id, title, content, type, ref_ticket_id, is_read, created_at }>>}
 */
export async function getNotifications() {
  const res = await client.get('/notifications')
  return res.data
}

/**
 * Mark a single notification as read.
 * @param {string|number} id
 * @returns {Promise<Object>} updated notification
 */
export async function markRead(id) {
  const res = await client.put(`/notifications/${id}/read`)
  return res.data
}

/**
 * Mark all notifications as read.
 * @returns {Promise<{ updated: number }>}
 */
export async function markAllRead() {
  const res = await client.put('/notifications/read-all')
  return res.data
}
