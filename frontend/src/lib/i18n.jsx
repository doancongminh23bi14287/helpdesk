/**
 * Minimal in-app i18n. No extra npm dependency — a Context + hook backed
 * by a static dictionary is enough for the visible surfaces (sidebar,
 * profile dropdown, ProfilePage, Dashboard).
 *
 * Usage:
 *   const { t, lang, setLang } = useTranslation()
 *   <span>{t('nav.dashboard')}</span>
 *
 * Falls back to English when a key is missing in the active language so
 * partially-translated pages never display the raw key.
 */
import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const STORAGE_KEY = 'app.language'
export const SUPPORTED_LANGS = ['en', 'vi']

export const TRANSLATIONS = {
  en: {
    // ── Sidebar ─────────────────────────────────────────────────────────
    'sidebar.brand.subtitle': 'Client Support Platform',
    'sidebar.section.main': 'Main',
    'sidebar.section.clientManagement': 'Client Management',
    'sidebar.section.delivery': 'Delivery',
    'sidebar.section.support': 'Support',
    'sidebar.section.billing': 'Billing',
    'sidebar.section.reporting': 'Reporting',
    'sidebar.section.account': 'Account',
    'sidebar.section.myServices': 'My Services',
    'nav.dashboard': 'Dashboard',
    'nav.organizations': 'Organizations',
    'nav.users': 'Users',
    'nav.staffAssignments': 'Staff Assignments',
    'nav.services': 'Services',
    'nav.seoProjects': 'SEO Projects',
    'nav.allTickets': 'All Tickets',
    'nav.myTickets': 'My Tickets',
    'nav.notifications': 'Notifications',
    'nav.slaPolicies': 'SLA Policies',
    'nav.items': 'Items',
    'nav.subscriptions': 'Subscriptions',
    'nav.invoices': 'Invoices',
    'nav.emailOutbox': 'Email Outbox',
    'nav.analytics': 'Analytics',
    'nav.systemStatus': 'System Status',
    'nav.accountSecurity': 'Account Security',
    'nav.seoDashboard': 'SEO (Preview)',
    'nav.newTicket': 'New Ticket',
    'nav.search': 'Search...',
    // ── Topbar / notifications ──────────────────────────────────────────
    'topbar.home': 'Home',
    'topbar.notifications': 'Notifications',
    'topbar.markAllRead': 'Mark all read',
    'topbar.allCaughtUp': 'All caught up!',
    // ── Profile dropdown ────────────────────────────────────────────────
    'profile.menu.openMenu': 'Open profile menu',
    'profile.menu.myProfile': 'My Profile',
    'profile.menu.preferences': 'Preferences',
    'profile.menu.accountSecurity': 'Account Security',
    'profile.menu.signOut': 'Sign Out',
    // ── Profile page ────────────────────────────────────────────────────
    'profile.title': 'My Profile',
    'profile.subtitle': 'Manage your account details, avatar, and preferences.',
    'profile.section.photo': 'Profile photo',
    'profile.section.color': 'Avatar color',
    'profile.section.personalInfo': 'Personal information',
    'profile.section.preferences': 'Preferences',
    'profile.action.upload': 'Upload avatar',
    'profile.action.remove': 'Remove avatar',
    'profile.action.uploadFileLabel': 'Upload avatar file',
    'profile.formatHint': 'JPG, PNG, or WebP. Max 2 MB.',
    'profile.colorHint': 'Used as the background for your initials when no photo is set.',
    'profile.field.fullName': 'Full name',
    'profile.field.phone': 'Phone',
    'profile.field.email': 'Email',
    'profile.field.role': 'Role',
    'profile.field.organization': 'Organization',
    'profile.save': 'Save profile',
    'profile.savedOK': 'Profile updated',
    'profile.savedFail': 'Could not update profile',
    'profile.removeFail': 'Could not remove avatar',
    'profile.uploadFail': 'Upload failed',
    'profile.invalidType': 'Unsupported file type. Use JPG, PNG, or WebP.',
    'profile.tooLarge': 'File is larger than 2 MB.',
    'profile.theme': 'Theme',
    'profile.theme.light': 'Light',
    'profile.theme.dark': 'Dark',
    'profile.theme.system': 'System',
    'profile.language': 'Language',
    'profile.preferencesNote': 'Theme and language preferences are saved locally on this device.',
    // ── Dashboard ───────────────────────────────────────────────────────
    'dashboard.title': 'Dashboard',
    'dashboard.overview': 'Overview of your account',
    'dashboard.metric.users': 'Users',
    'dashboard.metric.organizations': 'Organizations',
    'dashboard.metric.openTickets': 'Open Tickets',
    'dashboard.metric.outstanding': 'Outstanding',
    'dashboard.metric.activeSeoProjects': 'Active SEO Projects',
    'dashboard.metric.activeServices': 'Active Services',
    'dashboard.metric.expiringSoon': 'Expiring Soon',
    'dashboard.metric.projectsDueSoon': 'Projects Due Soon',
    'dashboard.metric.resolvedTickets': 'Resolved Tickets',
    'dashboard.metric.myOpenTickets': 'My Open Tickets',
    'dashboard.metric.myActiveServices': 'My Active Services',
    'dashboard.metric.inactiveSuffix': 'inactive',
    'dashboard.metric.registered': 'registered',
    'dashboard.metric.awaiting': 'awaiting response',
    'dashboard.metric.outstandingHint': 'sent + overdue invoices',
    'dashboard.recentTickets': 'Recent Tickets',
    'dashboard.recentSeoProjects': 'Recent SEO Projects',
    'dashboard.viewAll': 'View all',
    'dashboard.noTickets': 'No tickets yet',
    'dashboard.noProjects': 'No SEO projects yet',
    'dashboard.yourServices': 'Your Services',
    'dashboard.systemHealth': 'System Health',
    'dashboard.allClear': 'All systems operational',
    'dashboard.subjectCol': 'Subject',
    'dashboard.statusCol': 'Status',
    'dashboard.priorityCol': 'Priority',
    'dashboard.updatedCol': 'Updated',
  },
  vi: {
    // ── Sidebar ─────────────────────────────────────────────────────────
    'sidebar.brand.subtitle': 'Nền tảng hỗ trợ khách hàng',
    'sidebar.section.main': 'Tổng quan',
    'sidebar.section.clientManagement': 'Quản lý khách hàng',
    'sidebar.section.delivery': 'Triển khai',
    'sidebar.section.support': 'Hỗ trợ',
    'sidebar.section.billing': 'Hoá đơn',
    'sidebar.section.reporting': 'Báo cáo',
    'sidebar.section.account': 'Tài khoản',
    'sidebar.section.myServices': 'Dịch vụ của tôi',
    'nav.dashboard': 'Bảng điều khiển',
    'nav.organizations': 'Tổ chức',
    'nav.users': 'Người dùng',
    'nav.staffAssignments': 'Phân công nhân viên',
    'nav.services': 'Dịch vụ',
    'nav.seoProjects': 'Dự án SEO',
    'nav.allTickets': 'Tất cả ticket',
    'nav.myTickets': 'Ticket của tôi',
    'nav.notifications': 'Thông báo',
    'nav.slaPolicies': 'Chính sách SLA',
    'nav.items': 'Mặt hàng',
    'nav.subscriptions': 'Gói thuê bao',
    'nav.invoices': 'Hoá đơn',
    'nav.emailOutbox': 'Email gửi đi',
    'nav.analytics': 'Phân tích',
    'nav.systemStatus': 'Trạng thái hệ thống',
    'nav.accountSecurity': 'Bảo mật tài khoản',
    'nav.seoDashboard': 'SEO (Xem thử)',
    'nav.newTicket': 'Ticket mới',
    'nav.search': 'Tìm kiếm...',
    // ── Topbar / notifications ──────────────────────────────────────────
    'topbar.home': 'Trang chủ',
    'topbar.notifications': 'Thông báo',
    'topbar.markAllRead': 'Đánh dấu đã đọc',
    'topbar.allCaughtUp': 'Bạn đã xem hết!',
    // ── Profile dropdown ────────────────────────────────────────────────
    'profile.menu.openMenu': 'Mở menu hồ sơ',
    'profile.menu.myProfile': 'Hồ sơ của tôi',
    'profile.menu.preferences': 'Tuỳ chọn',
    'profile.menu.accountSecurity': 'Bảo mật tài khoản',
    'profile.menu.signOut': 'Đăng xuất',
    // ── Profile page ────────────────────────────────────────────────────
    'profile.title': 'Hồ sơ của tôi',
    'profile.subtitle': 'Quản lý thông tin tài khoản, ảnh đại diện và tuỳ chọn.',
    'profile.section.photo': 'Ảnh đại diện',
    'profile.section.color': 'Màu ảnh đại diện',
    'profile.section.personalInfo': 'Thông tin cá nhân',
    'profile.section.preferences': 'Tuỳ chọn',
    'profile.action.upload': 'Tải ảnh lên',
    'profile.action.remove': 'Xoá ảnh',
    'profile.action.uploadFileLabel': 'Tải tệp ảnh đại diện',
    'profile.formatHint': 'JPG, PNG hoặc WebP. Tối đa 2 MB.',
    'profile.colorHint': 'Dùng làm nền cho chữ cái viết tắt khi chưa có ảnh.',
    'profile.field.fullName': 'Họ và tên',
    'profile.field.phone': 'Số điện thoại',
    'profile.field.email': 'Email',
    'profile.field.role': 'Vai trò',
    'profile.field.organization': 'Tổ chức',
    'profile.save': 'Lưu hồ sơ',
    'profile.savedOK': 'Đã cập nhật hồ sơ',
    'profile.savedFail': 'Không thể cập nhật hồ sơ',
    'profile.removeFail': 'Không thể xoá ảnh đại diện',
    'profile.uploadFail': 'Tải ảnh thất bại',
    'profile.invalidType': 'Định dạng không hỗ trợ. Dùng JPG, PNG hoặc WebP.',
    'profile.tooLarge': 'Tệp lớn hơn 2 MB.',
    'profile.theme': 'Giao diện',
    'profile.theme.light': 'Sáng',
    'profile.theme.dark': 'Tối',
    'profile.theme.system': 'Theo hệ thống',
    'profile.language': 'Ngôn ngữ',
    'profile.preferencesNote': 'Giao diện và ngôn ngữ được lưu cục bộ trên thiết bị này.',
    // ── Dashboard ───────────────────────────────────────────────────────
    'dashboard.title': 'Bảng điều khiển',
    'dashboard.overview': 'Tổng quan tài khoản của bạn',
    'dashboard.metric.users': 'Người dùng',
    'dashboard.metric.organizations': 'Tổ chức',
    'dashboard.metric.openTickets': 'Ticket đang mở',
    'dashboard.metric.outstanding': 'Công nợ',
    'dashboard.metric.activeSeoProjects': 'Dự án SEO đang chạy',
    'dashboard.metric.activeServices': 'Dịch vụ đang hoạt động',
    'dashboard.metric.expiringSoon': 'Sắp hết hạn',
    'dashboard.metric.projectsDueSoon': 'Dự án sắp đến hạn',
    'dashboard.metric.resolvedTickets': 'Ticket đã giải quyết',
    'dashboard.metric.myOpenTickets': 'Ticket đang mở của tôi',
    'dashboard.metric.myActiveServices': 'Dịch vụ của tôi đang hoạt động',
    'dashboard.metric.inactiveSuffix': 'không hoạt động',
    'dashboard.metric.registered': 'đã đăng ký',
    'dashboard.metric.awaiting': 'đang chờ phản hồi',
    'dashboard.metric.outstandingHint': 'hoá đơn đã gửi + quá hạn',
    'dashboard.recentTickets': 'Ticket gần đây',
    'dashboard.recentSeoProjects': 'Dự án SEO gần đây',
    'dashboard.viewAll': 'Xem tất cả',
    'dashboard.noTickets': 'Chưa có ticket nào',
    'dashboard.noProjects': 'Chưa có dự án SEO nào',
    'dashboard.yourServices': 'Dịch vụ của bạn',
    'dashboard.systemHealth': 'Sức khoẻ hệ thống',
    'dashboard.allClear': 'Hệ thống hoạt động bình thường',
    'dashboard.subjectCol': 'Tiêu đề',
    'dashboard.statusCol': 'Trạng thái',
    'dashboard.priorityCol': 'Ưu tiên',
    'dashboard.updatedCol': 'Cập nhật',
  },
}

export function getStoredLang() {
  const saved = localStorage.getItem(STORAGE_KEY)
  return SUPPORTED_LANGS.includes(saved) ? saved : 'en'
}

// Default context falls back to the English dictionary so components
// rendered outside a LanguageProvider (e.g. unit tests) still display
// real strings instead of raw translation keys.
const LanguageContext = createContext({
  lang: 'en',
  setLang: () => {},
  t: (k) => TRANSLATIONS.en[k] ?? k,
})

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(getStoredLang)

  useEffect(() => {
    // Keep the <html lang="…"> attribute honest for screen readers and
    // browser features (e.g. spellcheck).
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((value) => {
    if (!SUPPORTED_LANGS.includes(value)) return
    localStorage.setItem(STORAGE_KEY, value)
    setLangState(value)
  }, [])

  const t = useCallback(
    (key) => TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en[key] ?? key,
    [lang],
  )

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useTranslation() {
  return useContext(LanguageContext)
}
