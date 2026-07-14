import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getTrendDomain, getTrendState, normalizeTrendData } from '@/lib/seoTrend'

const STATE_MESSAGES = {
  loading: 'Đang tải dữ liệu...',
  error: 'Không thể tải dữ liệu trong khoảng thời gian này',
  empty: 'Chưa có dữ liệu trong khoảng thời gian này',
}

function formatDate(date, includeYear = false) {
  const [year, month, day] = date.split('-')
  return includeYear ? `${day}/${month}/${year}` : `${day}/${month}`
}

function TrendTooltip({ active, payload, label, valueLabel, color }) {
  if (!active || !payload?.length) return null

  return (
    <div className="rounded-md border border-border bg-card px-2.5 py-2 shadow-md">
      <p className="text-[11px] text-muted-foreground">{formatDate(label, true)}</p>
      <p className="mt-0.5 text-xs font-semibold text-foreground">
        <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
        {valueLabel}: {payload[0].value.toLocaleString()}
      </p>
    </div>
  )
}

export default function TrendSparkline({
  data,
  color,
  valueLabel,
  isLoading = false,
  error = null,
}) {
  const points = normalizeTrendData(data)
  const state = getTrendState(points, { isLoading, error })
  const gradientId = `trend-${color.replace('#', '')}`
  const timeTicks = state === 'ready'
    ? [points[0].date, points[Math.floor((points.length - 1) / 2)].date, points.at(-1).date]
    : []

  if (state === 'single') {
    return (
      <div className="h-[90px] min-h-[90px] w-full flex flex-col items-center justify-center gap-2 text-center">
        <span
          data-testid="single-trend-point"
          className="block h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: color }}
        />
        <p className="text-[11px] leading-4 text-muted-foreground">
          Chưa đủ dữ liệu để xác định xu hướng
        </p>
      </div>
    )
  }

  if (state !== 'ready') {
    return (
      <div
        role="status"
        className="h-[90px] min-h-[90px] w-full flex items-center justify-center px-4 text-center text-[11px] leading-4 text-muted-foreground"
      >
        {STATE_MESSAGES[state]}
      </div>
    )
  }

  return (
    <div className="h-[90px] min-h-[90px] w-full" aria-label="Biểu đồ xu hướng theo ngày">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 6, right: 4, left: 4, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            ticks={timeTicks}
            tickFormatter={(date) => formatDate(date)}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: 'currentColor' }}
            className="text-muted-foreground"
            height={20}
            interval={0}
          />
          <YAxis hide domain={getTrendDomain(points)} />
          <Tooltip
            cursor={{ stroke: color, strokeOpacity: 0.25, strokeDasharray: '3 3' }}
            content={(
              <TrendTooltip valueLabel={valueLabel} color={color} />
            )}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.75}
            fill={`url(#${gradientId})`}
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
