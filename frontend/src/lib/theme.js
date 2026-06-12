// Shared theme logic for light / dark / system. Kept tiny on purpose so the
// boot module can run it before React mounts (avoids a flash of light theme
// when the user picked dark previously).

const STORAGE_KEY = 'app.theme'

export function getStoredTheme() {
  return localStorage.getItem(STORAGE_KEY) ?? 'system'
}

export function systemPrefersDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

// Add or remove the `dark` class on <html>. Tailwind picks this up via
// darkMode: ['class'].
export function applyTheme(value) {
  const wantsDark = value === 'dark' || (value === 'system' && systemPrefersDark())
  document.documentElement.classList.toggle('dark', wantsDark)
}

export function setTheme(value) {
  localStorage.setItem(STORAGE_KEY, value)
  applyTheme(value)
}

// React to system colour-scheme changes when the user picked "system".
// Returns an unsubscribe function for callers that need to clean up.
export function watchSystemTheme(onChange) {
  const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
  if (!mq) return () => {}
  const handler = () => {
    if (getStoredTheme() === 'system') {
      applyTheme('system')
      onChange?.()
    }
  }
  mq.addEventListener?.('change', handler)
  return () => mq.removeEventListener?.('change', handler)
}
