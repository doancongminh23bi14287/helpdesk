export { ToastContainer } from './Toast'
export { StatusBadge, PriorityBadge } from '@/components/StatusBadge'
export { default as Pagination } from './Pagination'
export { default as AttachmentList } from './AttachmentList'
export { UserAvatar } from './UserAvatar'
export { Modal, ModalFooter } from './Modal'
export { ConfirmDialog } from './ConfirmDialog'
export { PageHeader, SectionHeader } from './PageHeader'
export { PageContainer } from './PageContainer'
export { FormField, FormActions } from './FormField'
export { FilterBar } from './FilterBar'
export { ResponsiveTableViewport, MobileCardList, MobileDataCard, MobileDataRow } from './ResponsiveTable'
export {
  DataTable,
  DataTableScroll,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableCell,
} from './DataTable'
export {
  LoadingState,
  EmptyState,
  ErrorState,
  NoSearchResults,
  PermissionDeniedState,
} from './FeedbackState'
export {
  PageTitle,
  PageDescription,
  SectionTitle,
  CardTitleText,
  Body,
  SecondaryText,
  Metadata,
  TableHeaderText,
} from './Typography'
export { Button, IconButton } from '@/components/ui-shadcn/button'
export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui-shadcn/card'
export { Badge } from '@/components/ui-shadcn/badge'
export { Input } from '@/components/ui-shadcn/input'
export { Textarea } from '@/components/ui-shadcn/textarea'
export { Select } from '@/components/ui-shadcn/select'
export { Separator } from '@/components/ui-shadcn/separator'
export { Avatar, AvatarFallback } from '@/components/ui-shadcn/avatar'

import { cn } from '@/lib/utils'
import { PageContainer } from './PageContainer'

export function Spinner({ className, label = 'Loading' }) {
  return (
    <svg
      className={cn('h-4 w-4 animate-spin text-primary', className)}
      fill="none"
      viewBox="0 0 24 24"
      role="status"
      aria-label={label}
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

export function PageShell({ children, className }) {
  return <PageContainer className={cn('animate-fade-in', className)}>{children}</PageContainer>
}
