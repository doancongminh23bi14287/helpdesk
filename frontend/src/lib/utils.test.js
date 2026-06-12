import { describe, expect, it } from 'vitest'
import { formatVND } from './utils'

describe('formatVND', () => {
  it('formats an integer with vi-VN thousands separators', () => {
    expect(formatVND(150_000)).toBe('150.000 ₫')
  })

  it('renders millions in compact form', () => {
    expect(formatVND(2_500_000)).toBe('2.5M ₫')
  })

  it('returns "0 ₫" for undefined', () => {
    expect(formatVND(undefined)).toBe('0 ₫')
  })

  it('returns "0 ₫" for null', () => {
    expect(formatVND(null)).toBe('0 ₫')
  })

  it('returns "0 ₫" for NaN', () => {
    expect(formatVND(NaN)).toBe('0 ₫')
  })

  it('returns "0 ₫" for a non-numeric string', () => {
    expect(formatVND('not a number')).toBe('0 ₫')
  })

  it('coerces numeric strings', () => {
    expect(formatVND('150000')).toBe('150.000 ₫')
  })

  it('never includes the substring "NaN"', () => {
    for (const v of [undefined, null, NaN, Infinity, -Infinity, 'oops', {}, []]) {
      expect(formatVND(v)).not.toMatch(/NaN/)
    }
  })
})
