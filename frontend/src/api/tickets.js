import client from './client'

/**
 * List tickets, optionally filtered.
 * @param {{ status?: string, priority?: string, org_id?: string|number, service_id?: string|number }} params
 * @returns {Promise<Array>}
 */
export async function getTickets(params = {}) {
  const res = await client.get('/tickets', { params })
  if (Array.isArray(res.data)) {
    return { items: res.data, total: res.data.length, page: 1, pages: 1 }
  }
  return {
    items: res.data.items ?? [],
    total: res.data.total ?? 0,
    page: res.data.page ?? 1,
    pages: res.data.pages ?? 1,
  }
}

/**
 * Create a new ticket.
 * @param {{ org_id, service_id, subject, description?, priority?, ticket_type? }} data
 * @returns {Promise<Object>} created ticket
 */
export async function createTicket(data) {
  const res = await client.post('/tickets', data)
  return res.data
}

/**
 * Fetch a single ticket with replies and activities.
 * @param {string|number} id
 * @returns {Promise<Object>}
 */
export async function getTicket(id, { signal } = {}) {
  const res = await client.get(`/tickets/${id}`, { signal })
  return res.data
}

/**
 * Update a ticket's status, priority, or assignee.
 * @param {string|number} id
 * @param {{ status?, priority?, assignee_id? }} data
 * @returns {Promise<Object>} updated ticket
 */
export async function updateTicket(id, data) {
  const res = await client.put(`/tickets/${id}`, data)
  return res.data
}

/**
 * Delete a ticket (admin only).
 * @param {string|number} id
 */
export async function deleteTicket(id) {
  const res = await client.delete(`/tickets/${id}`)
  return res.data
}

/**
 * Add a reply to a ticket.
 * @param {string|number} id
 * @param {{ content: string, is_internal?: boolean }} data
 * @returns {Promise<Object>} created reply
 */
export async function addReply(id, data) {
  const res = await client.post(`/tickets/${id}/replies`, data)
  return res.data
}

/**
 * Get all replies for a ticket.
 * @param {string|number} id
 * @returns {Promise<Array>}
 */
export async function getReplies(id, { signal } = {}) {
  const res = await client.get(`/tickets/${id}/replies`, { signal })
  return res.data
}

/**
 * Get SLA status for a ticket.
 * @param {string|number} id
 * @returns {Promise<{ state, percent_remaining, hours_remaining, resolution_by, response_by }>}
 */
export async function getSla(id, { signal } = {}) {
  const res = await client.get(`/tickets/${id}/sla`, { signal })
  return res.data
}

/**
 * Assign a ticket to an agent.
 * @param {string|number} id
 * @param {string|number} assigneeId
 * @returns {Promise<Object>}
 */
export async function assignTicket(id, assigneeId) {
  const res = await client.post(`/tickets/${id}/assign`, { assignee_id: assigneeId })
  return res.data
}

// ---------------------------------------------------------------------------
// Backward-compat shims — hooks/pages use old function names; cannot be
// modified until Phase 4B. These map old signatures to new ones.
// ---------------------------------------------------------------------------

/**
 * Compat shim for useTickets.js — old name was getTicketDetail.
 * New backend returns ticket.replies; map to { ticket, messages } shape.
 * @param {string|number} ticketId
 * @returns {Promise<{ ticket: Object, messages: Array }>}
 */
export async function getTicketDetail(ticketId) {
  const data = await getTicket(ticketId)
  const messages = data?.replies ?? []
  // Include activities on the ticket object so useTicket can access them
  return { ticket: data, messages }
}

/**
 * Compat shim for useTickets.js — old name was replyToTicket(id, content).
 * Maps to addReply(id, { content }).
 */
export async function replyToTicket(ticketId, content, isInternal = false) {
  return addReply(ticketId, { content, is_internal: isInternal })
}

/**
 * Return available ticket type categories.
 * No backend endpoint — returns a hardcoded list.
 * @returns {Promise<Array<{ name: string }>>}
 */
export async function getServiceCategories() {
  return [
    { name: 'Incident' },
    { name: 'Bug' },
    { name: 'Question' },
    { name: 'Service Request' },
    { name: 'Unspecified' },
  ]
}

/**
 * Stub — some pages call this but the new backend has no equivalent.
 * @returns {Promise<null>}
 */
export async function getPortalSummary() {
  return null
}

export const getTransferRequest = (ticketId) =>
  client.get(`/tickets/${ticketId}/transfer-request`).then(r => r.data)

export const createTransferRequest = (ticketId, toStaffId) =>
  client.post(`/tickets/${ticketId}/transfer-request`, { to_staff_id: toStaffId }).then(r => r.data)

export const acceptTransfer = (ticketId, reqId) =>
  client.put(`/tickets/${ticketId}/transfer-request/${reqId}/accept`).then(r => r.data)

export const declineTransfer = (ticketId, reqId) =>
  client.put(`/tickets/${ticketId}/transfer-request/${reqId}/decline`).then(r => r.data)
