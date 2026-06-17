import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProjectDetailPage from './ProjectDetailPage'

let mockRole = { isCustomer: true, isStaff: false, isAdmin: false, role: 'customer' }
const getProjectMock = vi.fn()
const listProjectTasksMock = vi.fn()
const createProjectTaskMock = vi.fn()
const updateProjectTaskStatusMock = vi.fn()
const listProjectDocumentsMock = vi.fn()
const uploadProjectDocumentMock = vi.fn()
const downloadProjectDocumentMock = vi.fn()
const listUsersMock = vi.fn()
const getProjectTicketsMock = vi.fn()

vi.mock('@/hooks/useRole', () => ({
  useRole: () => mockRole,
}))

vi.mock('@/api/projects', () => ({
  getProject: (...args) => getProjectMock(...args),
  listProjectTasks: (...args) => listProjectTasksMock(...args),
  createProjectTask: (...args) => createProjectTaskMock(...args),
  updateProjectTaskStatus: (...args) => updateProjectTaskStatusMock(...args),
  listProjectDocuments: (...args) => listProjectDocumentsMock(...args),
  uploadProjectDocument: (...args) => uploadProjectDocumentMock(...args),
  downloadProjectDocument: (...args) => downloadProjectDocumentMock(...args),
  getProjectTickets: (...args) => getProjectTicketsMock(...args),
  cancelProject: vi.fn(),
  updateProjectTask: vi.fn(),
  cancelProjectTask: vi.fn(),
}))

vi.mock('@/api/users', () => ({
  listUsers: (...args) => listUsersMock(...args),
}))

function renderDetail() {
  return render(
    <MemoryRouter
      initialEntries={['/projects/1']}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/projects/:id" element={<ProjectDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    mockRole = { isCustomer: true, isStaff: false, isAdmin: false, role: 'customer' }
    getProjectMock.mockResolvedValue({
      id: 1,
      name: 'SEO Growth',
      description: 'Public progress',
      project_type: 'seo',
      status: 'working',
      visibility: 'customer_visible',
      progress_percent: 50,
      start_date: '2026-06-01',
      due_date: '2026-06-30',
    })
    listProjectTasksMock.mockResolvedValue([
      { id: 10, project_id: 1, title: 'Monthly Report', task_type: 'report', status: 'open', priority: 'medium' },
    ])
    createProjectTaskMock.mockResolvedValue({})
    updateProjectTaskStatusMock.mockResolvedValue({})
    listProjectDocumentsMock.mockResolvedValue([
      { id: 99, project_id: 1, file_name: 'seo-brief.pdf', file_size: 2048, mime_type: 'application/pdf', is_client_visible: true, created_at: '2026-06-01T00:00:00' },
    ])
    uploadProjectDocumentMock.mockResolvedValue({})
    downloadProjectDocumentMock.mockResolvedValue({})
    listUsersMock.mockResolvedValue({ items: [{ id: 2, full_name: 'Staff One', email: 'staff@example.com' }] })
    getProjectTicketsMock.mockResolvedValue([])
  })

  it('customer detail is read-only and does not show internal notes', async () => {
    renderDetail()

    expect(await screen.findByRole('heading', { level: 1, name: 'SEO Growth' })).toBeInTheDocument()
    expect(screen.getByText('Start date')).toBeInTheDocument()
    expect(screen.getAllByText('Deadline').length).toBeGreaterThan(0)
    expect(screen.queryByText(/add task/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/internal:/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/upload/i)).not.toBeInTheDocument()
    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(screen.getByText('seo-brief.pdf')).toBeInTheDocument()
  })

  it('admin detail shows add task controls', async () => {
    mockRole = { isCustomer: false, isStaff: false, isAdmin: true, role: 'admin' }
    listProjectTasksMock.mockResolvedValue([
      {
        id: 10,
        project_id: 1,
        title: 'Technical Audit',
        task_type: 'technical_audit',
        status: 'open',
        priority: 'high',
        is_client_visible: false,
        internal_note: 'Check crawl budget',
      },
    ])

    renderDetail()

    expect((await screen.findAllByText('Add Task')).length).toBeGreaterThan(0)
    expect(screen.getByText(/internal: check crawl budget/i)).toBeInTheDocument()
    expect(screen.getAllByDisplayValue('open').length).toBeGreaterThan(0)
    expect(screen.getByText('Team Members')).toBeInTheDocument()
    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(screen.getByText('Upload')).toBeInTheDocument()
  })

  it('staff status update calls API and refreshes tasks', async () => {
    mockRole = { isCustomer: false, isStaff: true, isAdmin: false, role: 'staff' }

    renderDetail()

    const selects = await screen.findAllByDisplayValue('open')
    const select = selects[selects.length - 1]
    fireEvent.change(select, { target: { value: 'working' } })

    await waitFor(() => {
      expect(updateProjectTaskStatusMock).toHaveBeenCalledWith(10, 'working')
    })
    expect(listProjectTasksMock).toHaveBeenCalledTimes(2)
  })
})
