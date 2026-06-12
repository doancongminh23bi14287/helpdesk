import axios from 'axios'
import { describe, expect, it, vi } from 'vitest'

import client from './client'

describe('api client interceptor', () => {
  it('does not infinitely retry refresh after a 401', async () => {
    localStorage.setItem('access_token', 'old-access')
    localStorage.setItem('refresh_token', 'old-refresh')
    vi.spyOn(axios, 'post').mockRejectedValue({
      response: { status: 401, data: { detail: 'refresh failed' } },
      config: {},
    })
    client.defaults.adapter = vi.fn(async (config) => Promise.reject({
      config,
      response: { status: 401, data: { detail: 'expired' } },
    }))

    await expect(client.get('/protected')).rejects.toThrow('refresh failed')

    expect(axios.post).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})
