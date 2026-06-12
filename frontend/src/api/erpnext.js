// DEPRECATED — do not use in new code
// Use @/erp bridge layer instead
// This file will be deleted after full migration
import client from './client'

/**
 * Generic Frappe REST wrapper — thin layer over /api/resource/* and
 * /api/method/frappe.client.*.
 * Uses the same shared Axios client as every other API module so auth,
 * CSRF injection, and error normalisation are handled automatically.
 */

/** @returns {Promise<Array>} */
export async function getList(doctype, fields = ['name'], filters = [], limit = 20) {
  const params = {
    fields: JSON.stringify(fields),
    limit,
    order_by: 'modified desc',
  }
  if (filters.length) params.filters = JSON.stringify(filters)

  const res = await client.get(`/resource/${encodeURIComponent(doctype)}`, { params })
  return res.data.data ?? []
}

/** @returns {Promise<Object|null>} */
export async function getDoc(doctype, name) {
  const res = await client.get(
    `/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`
  )
  return res.data.data ?? null
}

/** @returns {Promise<number>} */
export async function getCount(doctype, filters = []) {
  const params = { doctype }
  if (filters.length) params.filters = JSON.stringify(filters)

  const res = await client.get('/method/frappe.client.get_count', { params })
  return res.data.message ?? 0
}
