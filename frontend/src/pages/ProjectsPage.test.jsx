import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProjectsPage from './ProjectsPage'

let mockRole = { isCustomer: true, isStaff: false, isAdmin: false, role: 'customer' }
const listProjectsMock = vi.fn()
const listProjectTasksMock = vi.fn()

vi.mock('@/hooks/useRole', () => ({
  useRole: () => mockRole,
}))

vi.mock('@/api/projects', () => ({
  listProjects: (...args) => listProjectsMock(...args),
  listProjectTasks: (...args) => listProjectTasksMock(...args),
  createProject: vi.fn(),
}))

vi.mock('@/api/organizations', () => ({
  listOrganizations: vi.fn().mockResolvedValue({ items: [] }),
}))

const RouterWrapper = ({ children }) => (
  <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
    {children}
  </MemoryRouter>
)

describe('ProjectsPage', () => {
  beforeEach(() => {
    mockRole = { isCustomer: true, isStaff: false, isAdmin: false, role: 'customer' }
    listProjectsMock.mockResolvedValue({ items: [], total: 0, page: 1, per_page: 20, pages: 1 })
    listProjectTasksMock.mockResolvedValue([])
  })

  it('renders empty state after loading projects', async () => {
    render(<ProjectsPage />, { wrapper: RouterWrapper })

    expect(await screen.findByText(/no projects found/i)).toBeInTheDocument()
  })

  it('uses the "SEO Projects" page heading', async () => {
    render(<ProjectsPage />, { wrapper: RouterWrapper })
    expect(screen.getByRole('heading', { level: 1, name: /SEO Projects/ })).toBeInTheDocument()
  })

  it('displays project progress and status', async () => {
    listProjectsMock.mockResolvedValue({
      items: [
        { id: 1, name: 'SEO Growth', project_type: 'seo', status: 'working', progress_percent: 50, start_date: '2026-06-01', due_date: '2026-06-30' },
      ],
      total: 1,
    })
    listProjectTasksMock.mockResolvedValue([
      { id: 1, status: 'completed' },
      { id: 2, status: 'working' },
    ])

    render(<ProjectsPage />, { wrapper: RouterWrapper })

    expect(await screen.findByText('SEO Growth')).toBeInTheDocument()
    expect(screen.getByText('Deadline')).toBeInTheDocument()
    expect(screen.getByText(/Start date:/)).toBeInTheDocument()
    expect(screen.getByText('working')).toBeInTheDocument()
    expect(screen.getByText('1/2')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('50%')).toBeInTheDocument())
  })
})
