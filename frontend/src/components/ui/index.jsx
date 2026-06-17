export { ToastContainer } from './Toast'
export { StatusBadge } from '@/components/StatusBadge'
export { default as Pagination } from './Pagination'
export { default as AttachmentList } from './AttachmentList'
export { UserAvatar } from './UserAvatar'
// Re-export shadcn components + shared helpers
export { Button }     from '@/components/ui-shadcn/button'
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui-shadcn/card'
export { Badge }      from '@/components/ui-shadcn/badge'
export { Input }      from '@/components/ui-shadcn/input'
export { Textarea }   from '@/components/ui-shadcn/textarea'
export { Select }     from '@/components/ui-shadcn/select'
export { Separator }  from '@/components/ui-shadcn/separator'
export { Avatar, AvatarFallback } from '@/components/ui-shadcn/avatar'

import { cn } from '@/lib/utils'

// ─── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ className }) {
  return (
    <svg className={cn('animate-spin h-4 w-4 text-primary', className)} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

// ─── Empty State ───────────────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {Icon && (
        <div className="p-4 bg-muted rounded-2xl mb-4">
          <Icon className="w-8 h-8 text-muted-foreground" />
        </div>
      )}
      <p className="font-display font-semibold text-foreground text-base">{title}</p>
      {description && <p className="text-sm text-muted-foreground mt-1 max-w-xs">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

// ─── Page shell + header ──────────────────────────────────────────────────────
// Standard wrapper for "padded" pages. Provides horizontal padding so content
// never sits flush against the sidebar, and constrains max width for legibility.
export function PageShell({ children, className }) {
  return (
    <div className={cn('p-6 lg:p-8 max-w-6xl mx-auto space-y-6 animate-fade-in', className)}>
      {children}
    </div>
  )
}

// Consistent page heading: title, optional subtitle, and right-aligned actions.
// Keeps typography uniform across pages.
export function PageHeader({ title, subtitle, actions, className }) {
  return (
    <div className={cn('flex flex-col gap-3 md:flex-row md:items-end md:justify-between', className)}>
      <div>
        <h1 className="text-2xl font-bold text-foreground tracking-tight">{title}</h1>
        {subtitle && (
          <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}
