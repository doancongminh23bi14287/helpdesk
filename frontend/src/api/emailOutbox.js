import client from '@/api/client'

export const listEmailOutbox = (params = {}) =>
  client.get('/admin/email-outbox', { params }).then(r => r.data)

export const retryEmailOutbox = (id) =>
  client.post(`/admin/email-outbox/${id}/retry`).then(r => r.data)

export const getEmailOAuthStatus = () =>
  client.get('/admin/email-oauth/status').then(r => r.data)

export const getEmailOAuthConnectUrl = () =>
  client.get('/admin/email-oauth/connect').then(r => r.data)
