import client from './client'

export async function listSlaPolicies() {
  const res = await client.get('/admin/sla/policies')
  return res.data
}

export async function updateSlaPolicy(id, data) {
  const res = await client.put(`/admin/sla/policies/${id}`, data)
  return res.data
}
