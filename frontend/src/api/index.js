/**
 * Public API barrel — import from '@/api' to get all domain functions.
 * The default export is the raw Axios client for edge cases.
 */
export { default } from './client'
export * from './client'

export * from './auth'
export * from './organizations'
export * from './tickets'
export * from './services'
export * from './users'
export * from './notifications'
export * from './analytics'
