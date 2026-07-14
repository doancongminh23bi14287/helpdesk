import { Bars3Icon } from '@heroicons/react/24/outline'
import { Breadcrumbs } from './Breadcrumbs'
import { NotificationMenu } from './NotificationMenu'
import { UserMenu } from './UserMenu'
import { IconButton } from '@/components/ui'

export function Topbar({ onMenuClick }) {
  return (
    <header className="relative z-30 flex h-topbar shrink-0 items-center justify-between gap-3 border-b border-border bg-surface px-3 sm:px-5">
      <div className="flex min-w-0 items-center gap-2">
        <IconButton label="Open navigation menu" onClick={onMenuClick} className="md:hidden">
          <Bars3Icon className="h-5 w-5" aria-hidden="true" />
        </IconButton>
        <Breadcrumbs />
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <NotificationMenu />
        <UserMenu />
      </div>
    </header>
  )
}
