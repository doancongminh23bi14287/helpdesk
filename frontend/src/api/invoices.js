import client from '@/api/client'

export const listMyInvoices = () =>
  client.get('/invoices/my').then(r => r.data)

export const listInvoices = (params = {}) =>
  client.get('/invoices', { params }).then(r => r.data)

export const getInvoice = (id) =>
  client.get(`/invoices/${id}`).then(r => r.data)

export const sendInvoice = (id) =>
  client.put(`/invoices/${id}/send`).then(r => r.data)

export const markInvoicePaid = (id) =>
  client.put(`/invoices/${id}/mark-paid`).then(r => r.data)

export const listInvoicePayments = (id) =>
  client.get(`/invoices/${id}/payments`).then(r => r.data)

export const addInvoicePayment = (id, payload) =>
  client.post(`/invoices/${id}/payments`, payload).then(r => r.data)

export const downloadInvoicePdf = async (invoice) => {
  const res = await client.get(`/invoices/${invoice.id}/pdf`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `invoice-${invoice.invoice_number ?? invoice.id}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export const cancelInvoice = (id) =>
  client.put(`/invoices/${id}/cancel`).then(r => r.data)

export const deleteInvoice = (id) =>
  client.delete(`/invoices/${id}`)

export const generateFromSubscriptions = () =>
  client.post('/admin/invoices/generate-from-subscriptions').then(r => r.data)
