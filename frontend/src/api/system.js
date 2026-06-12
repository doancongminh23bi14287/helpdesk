import axios from 'axios'
import client from '@/api/client'

function apiRoot() {
  const base = client.defaults.baseURL ?? ''
  return base.replace(/\/api\/?$/, '')
}

export const getHealth = () =>
  axios.get(`${apiRoot()}/health`).then(r => r.data)

export const getReady = () =>
  axios.get(`${apiRoot()}/ready`).then(r => r.data)
