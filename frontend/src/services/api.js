/**
 * src/services/api.js — backward-compatibility shim.
 *
 * All API logic lives in src/api/. This file re-exports everything so existing
 * imports keep working without changes. New code should import from '@/api' directly.
 */
export { default } from '@/api/client'
export * from '@/api/client'
export * from '@/api/auth'
export * from '@/api/organizations'
export * from '@/api/tickets'
export * from '@/api/services'
export * from '@/api/users'
export * from '@/api/notifications'
export * from '@/api/analytics'
