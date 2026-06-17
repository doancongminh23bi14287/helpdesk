import {
  ServerStackIcon,
  SparklesIcon,
  GlobeAltIcon,
  WrenchScrewdriverIcon,
  CubeIcon,
} from '@heroicons/react/24/outline'

const CONFIG = {
  saas:    { label: 'SaaS',    icon: SparklesIcon,          cls: 'bg-amber-100 text-amber-700' },
  hosting: { label: 'Hosting', icon: ServerStackIcon,       cls: 'bg-cyan-100 text-cyan-700' },
  domain:  { label: 'Domain',  icon: GlobeAltIcon,          cls: 'bg-purple-100 text-purple-700' },
  support: { label: 'Support', icon: WrenchScrewdriverIcon, cls: 'bg-orange-100 text-orange-700' },
  other:   { label: 'Other',   icon: CubeIcon,              cls: 'bg-slate-100 text-slate-600' },
}

export function TypeBadge({ type, className = '' }) {
  const cfg = CONFIG[type] ?? CONFIG.other
  const Icon = cfg.icon
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls} ${className}`}>
      <Icon className="w-3 h-3 flex-shrink-0" />
      {cfg.label}
    </span>
  )
}

export default TypeBadge
