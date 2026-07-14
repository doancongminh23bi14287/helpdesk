import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import TrendSparkline from './TrendSparkline'

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  AreaChart: ({ children, data }) => (
    <svg data-testid="trend-chart" data-points={JSON.stringify(data)}>{children}</svg>
  ),
  Area: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}))

describe('TrendSparkline', () => {
  it('shows a loading state without rendering a chart', () => {
    render(<TrendSparkline data={[]} color="#F59E0B" isLoading />)

    expect(screen.getByText('Đang tải dữ liệu...')).toBeInTheDocument()
    expect(screen.queryByTestId('trend-chart')).not.toBeInTheDocument()
  })

  it('shows an API error state without rendering a chart', () => {
    render(<TrendSparkline data={[]} color="#0EA5E9" error="API failed" />)

    expect(screen.getByText('Không thể tải dữ liệu trong khoảng thời gian này')).toBeInTheDocument()
    expect(screen.queryByTestId('trend-chart')).not.toBeInTheDocument()
  })

  it('shows an empty state instead of a zero-value fallback point', () => {
    render(<TrendSparkline data={[]} color="#F59E0B" />)

    expect(screen.getByText('Chưa có dữ liệu trong khoảng thời gian này')).toBeInTheDocument()
    expect(screen.queryByTestId('single-trend-point')).not.toBeInTheDocument()
  })

  it('centers a real single point and explains that trend data is insufficient', () => {
    render(
      <TrendSparkline
        data={[{ date: '2026-07-01', value: 4 }]}
        color="#0EA5E9"
      />,
    )

    expect(screen.getByTestId('single-trend-point')).toHaveStyle({ backgroundColor: '#0EA5E9' })
    expect(screen.getByText('Chưa đủ dữ liệu để xác định xu hướng')).toBeInTheDocument()
    expect(screen.queryByTestId('trend-chart')).not.toBeInTheDocument()
  })

  it('renders sorted daily values, including an all-zero series', () => {
    render(
      <TrendSparkline
        data={[
          { date: '2026-07-02', value: 0 },
          { date: '2026-07-01', value: 0 },
        ]}
        color="#F59E0B"
      />,
    )

    expect(JSON.parse(screen.getByTestId('trend-chart').dataset.points)).toEqual([
      { date: '2026-07-01', value: 0 },
      { date: '2026-07-02', value: 0 },
    ])
  })
})
