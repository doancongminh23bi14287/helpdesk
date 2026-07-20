// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const sockets = []

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => {
    const handlers = new Map()
    const socket = {
      connected: true,
      on: vi.fn((event, handler) => {
        handlers.set(event, handler)
        return socket
      }),
      off: vi.fn(),
      emit: vi.fn(),
      removeAllListeners: vi.fn(),
      disconnect: vi.fn(),
      handlers,
    }
    sockets.push(socket)
    return socket
  }),
}))

describe('useSocket presence heartbeat', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    localStorage.setItem('access_token', 'test-token')
    const { useAuthStore } = await import('./useAuth')
    useAuthStore.setState({
      user: { id: 2, role: 'staff' },
      isAuthenticated: true,
    })
  })

  afterEach(async () => {
    const { useAuthStore } = await import('./useAuth')
    useAuthStore.setState({ user: null, isAuthenticated: false })
    localStorage.clear()
    sockets.length = 0
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('keeps one timer across reconnects and cleans it on unmount', async () => {
    const { useSocket } = await import('./useSocket')
    const { unmount } = renderHook(() => useSocket())
    const socket = sockets.at(-1)
    const baselineTimers = vi.getTimerCount()

    act(() => socket.handlers.get('connect')())
    expect(socket.emit).toHaveBeenCalledWith('presence_heartbeat')
    expect(vi.getTimerCount()).toBe(baselineTimers + 1)

    act(() => socket.handlers.get('connect')())
    expect(vi.getTimerCount()).toBe(baselineTimers + 1)

    const callsBeforeTick = socket.emit.mock.calls.length
    act(() => vi.advanceTimersByTime(30_000))
    expect(socket.emit.mock.calls.length).toBe(callsBeforeTick + 1)

    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('stops heartbeat while disconnected', async () => {
    const { useSocket } = await import('./useSocket')
    const { unmount } = renderHook(() => useSocket())
    const socket = sockets.at(-1)
    const baselineTimers = vi.getTimerCount()

    act(() => socket.handlers.get('connect')())
    expect(vi.getTimerCount()).toBe(baselineTimers + 1)

    act(() => socket.handlers.get('disconnect')())
    expect(vi.getTimerCount()).toBe(baselineTimers)
    unmount()
  })
})
