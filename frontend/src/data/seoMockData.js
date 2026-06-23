// ── Tracked keywords ──────────────────────────────────────────────────────────
export const keywords = [
  { keyword: 'seo agency vietnam',        position: 3,  prevPosition: 6,  change: 3,   volume: 1900, url: '/services/seo-agency' },
  { keyword: 'digital marketing hanoi',   position: 7,  prevPosition: 5,  change: -2,  volume: 2400, url: '/services/digital-marketing' },
  { keyword: 'content marketing service', position: 11, prevPosition: 15, change: 4,   volume: 880,  url: '/blog/content-marketing' },
  { keyword: 'link building packages',    position: 5,  prevPosition: 5,  change: 0,   volume: 1300, url: '/services/link-building' },
  { keyword: 'technical seo audit',       position: 2,  prevPosition: 4,  change: 2,   volume: 720,  url: '/services/seo-audit' },
  { keyword: 'local seo services',        position: 14, prevPosition: 19, change: 5,   volume: 3100, url: '/services/local-seo' },
  { keyword: 'ecommerce seo vietnam',     position: 8,  prevPosition: 7,  change: -1,  volume: 590,  url: '/services/ecommerce-seo' },
  { keyword: 'google ads management',     position: 22, prevPosition: 28, change: 6,   volume: 4200, url: '/services/google-ads' },
  { keyword: 'social media marketing',    position: 17, prevPosition: 17, change: 0,   volume: 5500, url: '/services/social-media' },
  { keyword: 'website seo optimization',  position: 4,  prevPosition: 9,  change: 5,   volume: 1600, url: '/services/on-page-seo' },
]

// ── Rank history — 30 days, 4 keywords ────────────────────────────────────────
function buildHistory() {
  const seeds = {
    'seo agency vietnam':      [6, 6, 5, 5, 5, 4, 4, 5, 4, 4, 4, 3, 3, 4, 3, 3, 3, 3, 3, 3, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3],
    'technical seo audit':     [7, 6, 6, 6, 5, 5, 5, 5, 5, 4, 4, 4, 4, 5, 4, 4, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 3, 2, 2],
    'local seo services':      [22, 21, 20, 21, 20, 19, 18, 18, 19, 17, 17, 17, 16, 16, 15, 15, 16, 15, 15, 15, 15, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    'website seo optimization':[12, 11, 11, 10, 10, 10, 9, 9, 9, 9, 8, 8, 7, 7, 8, 7, 6, 6, 6, 5, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4],
  }
  const today = new Date()
  return Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today)
    d.setDate(today.getDate() - (29 - i))
    const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    const entry = { date: label }
    for (const [kw, vals] of Object.entries(seeds)) {
      entry[kw] = vals[i]
    }
    return entry
  })
}

export const rankHistory = buildHistory()

// Short display labels for the chart legend
export const rankKeywords = [
  { key: 'seo agency vietnam',      color: '#F59E0B' },
  { key: 'technical seo audit',     color: '#0EA5E9' },
  { key: 'local seo services',      color: '#10B981' },
  { key: 'website seo optimization',color: '#6366F1' },
]

// ── Google Search Console summary ────────────────────────────────────────────
const gscSparkBase = [420,380,450,510,490,530,560,540,580,610,590,640,620,670,700,680,720,750,730,760,800,780,820,850,830,870,910,890,930,960]
export const gscSummary = {
  clicks:       28400,
  impressions:  512000,
  ctr:          5.55,
  avgPosition:  8.2,
  sparkline:    gscSparkBase,
}

// ── Google Analytics 4 summary ────────────────────────────────────────────────
const ga4SparkBase = [310,290,340,390,370,410,430,420,450,470,460,490,480,510,530,520,540,560,555,575,600,590,615,635,625,650,670,660,680,700]
export const ga4Summary = {
  sessions:        48200,
  users:           31700,
  engagementRate:  62.4,
  sparkline:       ga4SparkBase,
}
