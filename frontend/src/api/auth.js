import axios from 'axios'
import client, { setTokens, clearTokens } from './client'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8001/api'

/**
 * Login with email + password.
 * Stores access_token and refresh_token in localStorage via setTokens.
 * @returns {{ access_token: string, refresh_token: string, token_type: string }}
 */
export async function login(email, password) {
  const res = await client.post('/auth/login', { email, password }, { headers: { Authorization: undefined } })
  const { access_token, refresh_token } = res.data
  setTokens(access_token, refresh_token)
  return res.data
}

/**
 * Logout — invalidates the token server-side.
 * Always clears local tokens regardless of server response.
 */
export async function logout() {
  try {
    await client.post('/auth/logout')
  } finally {
    clearTokens()
  }
}

/**
 * Exchange a refresh token for a new access token.
 * @param {string} refreshTok
 * @returns {{ access_token: string }}
 */
export async function refreshToken(refreshTok) {
  const res = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refreshTok })
  return res.data
}

/**
 * Fetch the currently authenticated user's profile.
 * @returns {{ id, email, full_name, role, org_id, phone, is_active, created_at }}
 */
export async function getMe() {
  const res = await client.get('/auth/me')
  return res.data
}

/**
 * Compat shim — RegisterPage.jsx imports this but the new backend has no
 * self-registration endpoint. Throws to surface the issue clearly at runtime.
 */
export async function registerUser() {
  throw new Error('User registration is not supported. Contact your administrator.')
}

/**
 * Compat shim — useAuth.js calls getSession() and expects { user: email }.
 * Delegates to getMe() and maps the shape so existing hooks keep working
 * without modification.
 * @returns {{ user: string|null }}
 */
export async function getSession() {
  try {
    const me = await getMe()
    return { user: me?.email ?? null }
  } catch {
    return { user: null }
  }
}

/**
 * Change the current user's password.
 */
export async function changePassword(currentPassword, newPassword) {
  const res = await client.post('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return res.data
}

export const listSessions = () =>
  client.get('/auth/sessions').then(r => r.data)

export const revokeSession = (id) =>
  client.delete(`/auth/sessions/${id}`).then(r => r.data)

export const logoutAllSessions = () =>
  client.post('/auth/logout-all').then(r => r.data)

/**
 * Update the current user's profile. Only fields on the backend's
 * UpdateMeRequest schema (full_name, phone, avatar_color) are accepted.
 */
export const updateMe = (payload) =>
  client.patch('/auth/me', payload).then(r => r.data)

/**
 * Upload a new avatar image. Browser sets the multipart boundary itself —
 * do NOT set Content-Type manually here.
 */
export async function uploadAvatar(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post('/auth/me/avatar', form)
  return res.data
}

export const deleteAvatar = () =>
  client.delete('/auth/me/avatar').then(r => r.data)
