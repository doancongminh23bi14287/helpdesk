import {
  BellIcon,
  BuildingOffice2Icon,
  ClipboardDocumentListIcon,
  CreditCardIcon,
  CubeIcon,
  DocumentTextIcon,
  HomeIcon,
  MagnifyingGlassCircleIcon,
  PresentationChartBarIcon,
  ServerStackIcon,
  ShieldCheckIcon,
  TicketIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline'
import {
  BellIcon as BellSolid,
  BuildingOffice2Icon as BuildingSolid,
  ClipboardDocumentListIcon as ClipboardSolid,
  CreditCardIcon as CreditCardSolid,
  CubeIcon as CubeSolid,
  DocumentTextIcon as DocumentTextSolid,
  HomeIcon as HomeSolid,
  MagnifyingGlassCircleIcon as MagnifyingGlassCircleSolid,
  PresentationChartBarIcon as PresentationChartBarSolid,
  ServerStackIcon as ServerSolid,
  ShieldCheckIcon as ShieldSolid,
  TicketIcon as TicketSolid,
  UserGroupIcon as UserGroupSolid,
} from '@heroicons/react/24/solid'

const NAV_ITEMS = {
  dashboard: { labelKey: 'nav.dashboard', href: '/', icon: HomeIcon, iconActive: HomeSolid },
  organizations: { labelKey: 'nav.organizations', href: '/admin/organizations', icon: BuildingOffice2Icon, iconActive: BuildingSolid },
  users: { labelKey: 'nav.users', href: '/admin/users', icon: UserGroupIcon, iconActive: UserGroupSolid },
  staffAssignments: { labelKey: 'nav.staffAssignments', href: '/admin/staff-assignments', icon: UserGroupIcon, iconActive: UserGroupSolid },
  services: { labelKey: 'nav.services', href: '/services', icon: ServerStackIcon, iconActive: ServerSolid },
  seoProjects: { labelKey: 'nav.seoProjects', href: '/projects', icon: ClipboardDocumentListIcon, iconActive: ClipboardSolid },
  myTickets: { labelKey: 'nav.myTickets', href: '/tickets', icon: TicketIcon, iconActive: TicketSolid },
  allTickets: { labelKey: 'nav.allTickets', href: '/tickets', icon: TicketIcon, iconActive: TicketSolid },
  notifications: { labelKey: 'nav.notifications', href: '/notifications', icon: BellIcon, iconActive: BellSolid },
  slaPolicies: { labelKey: 'nav.slaPolicies', href: '/admin/sla', icon: ShieldCheckIcon, iconActive: ShieldSolid },
  items: { labelKey: 'nav.items', href: '/admin/items', icon: CubeIcon, iconActive: CubeSolid },
  subscriptions: { labelKey: 'nav.subscriptions', href: '/admin/subscriptions', icon: CreditCardIcon, iconActive: CreditCardSolid },
  invoicesAdmin: { labelKey: 'nav.invoices', href: '/admin/invoices', icon: DocumentTextIcon, iconActive: DocumentTextSolid },
  invoicesMine: { labelKey: 'nav.invoices', href: '/invoices', icon: DocumentTextIcon, iconActive: DocumentTextSolid },
  emailOutbox: { labelKey: 'nav.emailOutbox', href: '/admin/email-outbox', icon: DocumentTextIcon, iconActive: DocumentTextSolid },
  analytics: { labelKey: 'nav.analytics', href: '/admin/analytics', icon: PresentationChartBarIcon, iconActive: PresentationChartBarSolid },
  systemStatus: { labelKey: 'nav.systemStatus', href: '/admin/system', icon: ServerStackIcon, iconActive: ServerSolid },
  accountSecurity: { labelKey: 'nav.accountSecurity', href: '/account/security', icon: ShieldCheckIcon, iconActive: ShieldSolid },
  seoDashboard: { labelKey: 'nav.seoDashboard', href: '/seo', icon: MagnifyingGlassCircleIcon, iconActive: MagnifyingGlassCircleSolid },
}

export function navSectionsForRole(role) {
  if (role === 'customer') {
    return [
      { titleKey: 'sidebar.section.main', items: [NAV_ITEMS.dashboard] },
      { titleKey: 'sidebar.section.myServices', items: [NAV_ITEMS.services, NAV_ITEMS.seoProjects] },
      { titleKey: 'sidebar.section.support', items: [NAV_ITEMS.myTickets, NAV_ITEMS.notifications, NAV_ITEMS.invoicesMine] },
      { titleKey: 'sidebar.section.account', items: [NAV_ITEMS.accountSecurity] },
    ]
  }

  if (role === 'staff') {
    return [
      { titleKey: 'sidebar.section.main', items: [NAV_ITEMS.dashboard, NAV_ITEMS.seoDashboard] },
      { titleKey: 'sidebar.section.delivery', items: [NAV_ITEMS.seoProjects, NAV_ITEMS.services] },
      { titleKey: 'sidebar.section.support', items: [NAV_ITEMS.allTickets, NAV_ITEMS.notifications] },
      { titleKey: 'sidebar.section.reporting', items: [NAV_ITEMS.analytics] },
      { titleKey: 'sidebar.section.account', items: [NAV_ITEMS.accountSecurity] },
    ]
  }

  return [
    { titleKey: 'sidebar.section.main', items: [NAV_ITEMS.dashboard, NAV_ITEMS.seoDashboard] },
    { titleKey: 'sidebar.section.clientManagement', items: [NAV_ITEMS.organizations, NAV_ITEMS.users, NAV_ITEMS.staffAssignments, NAV_ITEMS.services] },
    { titleKey: 'sidebar.section.delivery', items: [NAV_ITEMS.seoProjects] },
    { titleKey: 'sidebar.section.support', items: [NAV_ITEMS.allTickets, NAV_ITEMS.notifications, NAV_ITEMS.slaPolicies] },
    { titleKey: 'sidebar.section.billing', items: [NAV_ITEMS.items, NAV_ITEMS.subscriptions, NAV_ITEMS.invoicesAdmin, NAV_ITEMS.emailOutbox] },
    { titleKey: 'sidebar.section.reporting', items: [NAV_ITEMS.analytics, NAV_ITEMS.systemStatus] },
    { titleKey: 'sidebar.section.account', items: [NAV_ITEMS.accountSecurity] },
  ]
}
