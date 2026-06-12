/**
 * ERP fetch primitives — session-cookie auth only.
 *
 * Uses the shared axios instance (withCredentials: true + CSRF injection).
 * No api_key / api_secret anywhere in this file.
 *
 * Uses /api/resource/* (Frappe v1 REST API) — same path the existing hooks
 * use, confirmed to work with portal user sessions.
 * baseURL is '/api', so paths here start with '/resource/...' or '/method/...'.
 */
import client from '@/api/client'

const ERP_RES = '/resource'
const ERP_METHOD = '/method'

/** GET a document list or a single document. */
export async function erpGet(path, params = {}) {
  const res = await client.get(`${ERP_RES}${path}`, { params })
  return res.data
}

/** POST to a document endpoint (create or doc-method). */
export async function erpPost(path, body = {}) {
  const res = await client.post(`${ERP_RES}${path}`, body)
  return res.data
}

/** PUT to a document endpoint (update). */
export async function erpPut(path, body = {}) {
  const res = await client.put(`${ERP_RES}${path}`, body)
  return res.data
}

/** DELETE a document. */
export async function erpDelete(path) {
  const res = await client.delete(`${ERP_RES}${path}`)
  return res.data
}

/** POST to a whitelisted Frappe/ERPNext server method. */
export async function erpMethod(methodPath, body = {}) {
  const res = await client.post(`${ERP_METHOD}${methodPath}`, body)
  return res.data
}

/** GET a whitelisted Frappe/ERPNext server method (e.g. get_plan_rate). */
export async function erpGetMethod(methodPath, params = {}) {
  const res = await client.get(`${ERP_METHOD}${methodPath}`, { params })
  return res.data
}
