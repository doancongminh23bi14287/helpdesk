import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

const API_BASE = import.meta.env?.VITE_API_URL ?? 'http://localhost:8001/api'

// Turn the server-relative avatar_url into something the <img> tag can fetch.
// In dev the Vite proxy forwards /api/* to the backend, so same-origin paths
// already work. The branch below covers split-origin deploys where the
// frontend and backend live on different hosts: we re-anchor the path on the
// API origin.
function resolveAvatarUrl(url) {
  if (!url) return null
  if (/^https?:\/\//i.test(url)) return url
  try {
    const apiUrl = new URL(API_BASE)
    if (apiUrl.origin === window.location.origin) return url
    // VITE_API_URL points at api.example.com/api; we want the origin only.
    return apiUrl.origin + url
  } catch {
    return url
  }
}

// Palette aligned with the DashCode theme — no purple, no emerald.
const COLOR_CLASSES = {
  amber:  'bg-amber-100 text-amber-700',
  orange: 'bg-orange-100 text-orange-700',
  blue:   'bg-blue-100 text-blue-700',
  sky:    'bg-sky-100 text-sky-700',
  rose:   'bg-rose-100 text-rose-700',
  slate:  'bg-slate-200 text-slate-700',
}

const COLOR_KEYS = ['amber', 'blue', 'sky', 'orange', 'rose', 'slate']

function colorFromId(id) {
  return COLOR_KEYS[Math.abs(id ?? 0) % COLOR_KEYS.length]
}

const SIZE_CLASSES = {
  sm: 'h-7 w-7 text-[10px]',
  md: 'h-9 w-9 text-xs',
  lg: 'h-12 w-12 text-sm',
  xl: 'h-24 w-24 text-2xl',
}

function getInitials(user) {
  const source = user?.full_name || user?.email || ''
  const trimmed = source.trim()
  if (!trimmed) return '??'
  const parts = trimmed.split(/[\s@._-]+/).filter(Boolean)
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase()
  }
  return trimmed.slice(0, 2).toUpperCase()
}

/**
 * Round user avatar with image + initials fallback.
 *
 * - If user.avatar_url is set and the image loads, the picture is shown.
 * - If the image fails (network/404) or no URL exists, fall back to initials
 *   on a colored circle. The color is driven by user.avatar_color, defaulting
 *   to blue, so the badge looks intentional rather than blank.
 */
export function UserAvatar({ user, size = 'md', className, title }) {
  const [imageBroken, setImageBroken] = useState(false)
  const initials = getInitials(user)
  // avatar_color wins; fall back to deterministic hash of user.id; then amber.
  const color = COLOR_CLASSES[user?.avatar_color] ?? COLOR_CLASSES[colorFromId(user?.id)] ?? COLOR_CLASSES.amber
  const sizeCls = SIZE_CLASSES[size] ?? SIZE_CLASSES.md
  const resolvedUrl = resolveAvatarUrl(user?.avatar_url)
  const showImage = Boolean(resolvedUrl) && !imageBroken

  // Reset the broken flag when the URL actually changes (uploads bust cache
  // via the ?v= query string, so a previous failure shouldn't stick).
  useEffect(() => {
    setImageBroken(false)
  }, [resolvedUrl])

  return (
    <div
      className={cn(
        'relative inline-flex items-center justify-center rounded-full overflow-hidden font-semibold flex-shrink-0',
        sizeCls,
        showImage ? 'bg-muted' : color,
        className,
      )}
      aria-hidden={false}
      title={title}
    >
      {showImage ? (
        <img
          src={resolvedUrl}
          alt={user?.full_name || user?.email || 'Avatar'}
          className="h-full w-full object-cover"
          onError={() => setImageBroken(true)}
        />
      ) : (
        <span aria-hidden="true">{initials}</span>
      )}
    </div>
  )
}

export default UserAvatar
