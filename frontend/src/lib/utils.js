import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export function daysUntil(dateStr) {
  if (!dateStr) return null
  const diff = new Date(dateStr) - new Date()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
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
