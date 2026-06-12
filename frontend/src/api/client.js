/**
 * Shared Axios instance — JWT Bearer token auth against FastAPI backend.
 * All domain API modules import from here; never create a second instance.
 */
import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001/api'

const client = axios.create({
  baseURL: BASE_URL,
})

// ---------------------------------------------------------------------------
// Token helpers
// ---------------------------------------------------------------------------

export function setTokens(access, refresh) {
  localStorage.setItem('access_token', access)
  localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

// ---------------------------------------------------------------------------
// Request interceptor — attach Bearer token if present
// ---------------------------------------------------------------------------

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// ---------------------------------------------------------------------------
// Response interceptor — refresh on 401, normalise FastAPI error messages
// ---------------------------------------------------------------------------

// Track whether a refresh is in flight to prevent concurrent refresh attempts.
let _isRefreshing = false
let _refreshSubscribers = []

function onRefreshed(newToken) {
  _refreshSubscribers.forEach(({ resolve }) => resolve(newToken))
  _refreshSubscribers = []
}

function onRefreshFailed(err) {
  _refreshSubscribers.forEach(({ reject }) => reject(err))
  _refreshSubscribers = []
}

client.interceptors.response.use(
  (res) => res,
  async (err) => {
    const originalRequest = err.config

    // Only attempt refresh once per request (guard against infinite loop).
    if (err.response?.status === 401 && !originalRequest._retried) {
      const { pathname } = window.location
      if (pathname === '/login') {
        return Promise.reject(normalise(err))
      }

      originalRequest._retried = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(normalise(err))
      }

      if (_isRefreshing) {
        // Queue request until the in-flight refresh resolves.
        return new Promise((resolve, reject) => {
          _refreshSubscribers.push({
            resolve: (newToken) => {
              originalRequest.headers['Authorization'] = `Bearer ${newToken}`
              resolve(client(originalRequest))
            },
            reject,
          })
        })
      }

      _isRefreshing = true
      try {
        const res = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
        const newAccessToken = res.data.access_token
        localStorage.setItem('access_token', newAccessToken)
        if (res.data.refresh_token) {
          localStorage.setItem('refresh_token', res.data.refresh_token)
        }
        onRefreshed(newAccessToken)
        originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`
        return client(originalRequest)
      } catch (refreshErr) {
        onRefreshFailed(normalise(refreshErr))
        clearTokens()
        window.location.href = '/login'
        return Promise.reject(normalise(refreshErr))
      } finally {
        _isRefreshing = false
      }
    }

    return Promise.reject(normalise(err))
  },
)

/**
 * Normalise FastAPI error format: {"detail": "..."} → err.message
 */
function normalise(err) {
  if (!err.normalised) {
    const detail = err.response?.data?.detail
    if (detail && typeof detail === 'string') {
      err.message = detail
      err.normalised = true
    } else if (detail && Array.isArray(detail)) {
      // FastAPI validation errors are arrays of {loc, msg, type}
      err.message = detail.map((d) => d.msg).filter(Boolean).join('; ')
      err.normalised = true
    }
  }
  return err
}

export default client
