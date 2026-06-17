import client from '@/api/client'

// Subscription Plans
export const listSubscriptionPlans = (params = {}) =>
  client.get('/subscription-plans', { params }).then(r => r.data)

export const getSubscriptionPlan = (id) =>
  client.get(`/subscription-plans/${id}`).then(r => r.data)

export const createSubscriptionPlan = (data) =>
  client.post('/subscription-plans', data).then(r => r.data)

export const updateSubscriptionPlan = (id, data) =>
  client.put(`/subscription-plans/${id}`, data).then(r => r.data)

// Subscriptions
export const listSubscriptions = (params = {}) =>
  client.get('/subscriptions', { params }).then(r => r.data)

export const getMySubscriptions = () =>
  client.get('/subscriptions/my').then(r => r.data)

export const createSubscription = (data) =>
  client.post('/subscriptions', data).then(r => r.data)

export const getSubscription = (id) =>
  client.get(`/subscriptions/${id}`).then(r => r.data)

export const cancelSubscription = (id) =>
  client.put(`/subscriptions/${id}/cancel`).then(r => r.data)

export const deleteSubscription = (id) =>
  client.delete(`/subscriptions/${id}`)

export const deleteSubscriptionPermanent = (id) =>
  client.delete(`/subscriptions/${id}/permanent`).then(r => r.data)
