import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

// Backend returns UTC timestamps without 'Z'. Safe with string | Date | number | null.
export function parseUTC(value) {
  if (value == null) return null
  if (value instanceof Date) return value
  if (typeof value === 'number') return new Date(value)
  if (typeof value !== 'string') return new Date(value)
  const s = value.trim()
  if (!s) return null
  // ISO string without timezone → treat as UTC
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(s)
  const iso = hasTz ? s : s.replace(' ', 'T') + 'Z'
  const d = new Date(iso)
  return isNaN(d.getTime()) ? null : d
}

export function formatDate(dateStr) {
  if (!dateStr && dateStr !== 0) return '—'
  const d = parseUTC(dateStr)
  if (!d) return '—'
  return d.toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    timeZone: 'Asia/Ho_Chi_Minh',
  })
}

export function formatDateTime(dateStr) {
  if (!dateStr && dateStr !== 0) return '—'
  const d = parseUTC(dateStr)
  if (!d) return '—'
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Ho_Chi_Minh',
  })
}

export function daysUntil(dateStr) {
  if (!dateStr && dateStr !== 0) return null
  const d = parseUTC(dateStr)
  if (!d) return null
  return Math.ceil((d - new Date()) / (1000 * 60 * 60 * 24))
}

// Canonical VND money formatter — money displays go through here.
// Coerces non-finite input to 0 so it never renders "NaN ₫".
export function formatCurrencyVND(value) {
  const n = Number(value)
  const safe = Number.isFinite(n) ? n : 0
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(safe)
}

// Compact VND formatter for dashboard stat cards: abbreviates millions
// ("1.5M ₫"). Anything that can't be coerced to a finite number renders
// as "0 ₫" rather than "NaN ₫" / "undefined ₫" / "null ₫".
export function formatVND(value) {
  const n = Number(value)
  const safe = Number.isFinite(n) ? n : 0
  if (safe >= 1_000_000) {
    return `${(safe / 1_000_000).toFixed(1)}M ₫`
  }
  return new Intl.NumberFormat('vi-VN').format(safe) + ' ₫'
}
