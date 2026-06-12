import apiClient from './client'

export const getTicketAnalytics = (params, signal) => apiClient.get('/analytics/tickets', { params, signal })
export const getSLAAnalytics = (params, signal) => apiClient.get('/analytics/sla', { params, signal })
export const getAgentAnalytics = (params, signal) => apiClient.get('/analytics/agents', { params, signal })
export const getRevenueAnalytics = (params, signal) => apiClient.get('/analytics/revenue', { params, signal })
