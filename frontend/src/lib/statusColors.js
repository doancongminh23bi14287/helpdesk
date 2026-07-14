/**
 * Shared color-class maps for status/type badges across admin and customer pages.
 * Import the constant(s) you need rather than defining them locally in each page.
 */

/**
 * Invoice and subscription status badge colors.
 * Keys cover the union of all statuses used across InvoicesPage,
 * admin/InvoicesPage, and admin/SubscriptionsPage.
 */
export const STATUS_COLORS = {
  // Invoice statuses
  draft:     'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  sent:      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  paid:      'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  overdue:   'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  cancelled: 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500',
  // Subscription-only statuses
  trial:    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  active:   'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  scheduled:'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  past_due: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  expired:  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

/**
 * Item active/inactive status badge colors.
 * Keyed by the string representation of the boolean is_active field.
 */
export const ITEM_STATUS_COLORS = {
  true:  'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  false: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

/**
 * Item type badge colors (admin/ItemsPage).
 */
export const TYPE_COLORS = {
  saas:    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  hosting: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  domain:  'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  support: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  other:   'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
}
