import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { applyTheme, getStoredTheme, watchSystemTheme } from '@/lib/theme'

// Apply the saved theme BEFORE the first render so users who picked dark
// don't see a flash of the light palette on every reload.
applyTheme(getStoredTheme())
// Keep "system" honest: if the OS flips dark/light, follow along.
watchSystemTheme()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
