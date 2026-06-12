import client from './client'

export const listItems = (params = {}) => client.get('/items', { params }).then(r => r.data)
export const createItem = (data) => client.post('/items', data).then(r => r.data)
export const updateItem = (id, data) => client.put(`/items/${id}`, data).then(r => r.data)
export const getItem = (id) => client.get(`/items/${id}`).then(r => r.data)

export const listContacts = (orgId) => client.get(`/organizations/${orgId}/contacts`).then(r => r.data)
export const createContact = (orgId, data) => client.post(`/organizations/${orgId}/contacts`, data).then(r => r.data)
export const updateContact = (orgId, id, data) => client.put(`/organizations/${orgId}/contacts/${id}`, data).then(r => r.data)
export const deleteContact = (orgId, id) => client.delete(`/organizations/${orgId}/contacts/${id}`)
export const linkContactToUser = (orgId, contactId, userId) =>
  client.put(`/organizations/${orgId}/contacts/${contactId}/link-user`, { user_id: userId }).then(r => r.data)

export const listAddresses = (orgId) => client.get(`/organizations/${orgId}/addresses`).then(r => r.data)
export const createAddress = (orgId, data) => client.post(`/organizations/${orgId}/addresses`, data).then(r => r.data)
export const updateAddress = (orgId, id, data) => client.put(`/organizations/${orgId}/addresses/${id}`, data).then(r => r.data)
export const deleteAddress = (orgId, id) => client.delete(`/organizations/${orgId}/addresses/${id}`)
