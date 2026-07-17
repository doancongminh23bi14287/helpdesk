import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProjectDetailPage from './ProjectDetailPage'

let mockRole = { isCustomer: true, isStaff: false, isAdmin: false, role: 'customer' }
const getProjectMock = vi.fn()
const listProjectTasksMock = vi.fn()
const createProjectTaskMock = vi.fn()
const updateProjectTaskStatusMock = vi.fn()
const updateProjectMock = vi.fn()
const cancelProjectMock = vi.fn()
const listProjectDocumentsMock = vi.fn()
const uploadProjectDocumentMock = vi.fn()
const downloadProjectDocumentMock = vi.fn()
const listProjectMembersMock = vi.fn()
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
  listProjectMembers: (...args) => listProjectMembersMock(...args),
  cancelProject: (...args) => cancelProjectMock(...args),
  updateProject: (...args) => updateProjectMock(...args),
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
    updateProjectMock.mockResolvedValue({
      id: 1, name: 'SEO Growth', description: 'Public progress', project_type: 'seo',
      status: 'working', visibility: 'customer_visible', progress_percent: 50,
      start_date: '2026-06-01', due_date: '2026-06-30',
    })
    cancelProjectMock.mockResolvedValue({
      id: 1, name: 'SEO Growth', description: 'Public progress', project_type: 'seo',
      status: 'cancelled', visibility: 'customer_visible', progress_percent: 50,
      start_date: '2026-06-01', due_date: '2026-06-30',
    })
    listProjectDocumentsMock.mockResolvedValue([
      { id: 99, project_id: 1, file_name: 'seo-brief.pdf', file_size: 2048, mime_type: 'application/pdf', is_client_visible: true, created_at: '2026-06-01T00:00:00' },
    ])
    uploadProjectDocumentMock.mockResolvedValue({})
    downloadProjectDocumentMock.mockResolvedValue({})
    listUsersMock.mockResolvedValue({ items: [{ id: 2, full_name: 'Staff One', email: 'staff@example.com' }] })
    listProjectMembersMock.mockResolvedValue([
      { id: 1, user_id: 2, user_full_name: 'Staff One', user_email: 'staff@example.com' },
    ])
    getProjectTicketsMock.mockResolvedValue([])
  })

  it('customer detail is read-only and does not show internal notes', async () => {
    renderDetail()

    expect(await screen.findByRole('heading', { level: 1, name: 'SEO Growth' })).toBeInTheDocument()

    // Switch to Overview tab — start date and deadline live there
    fireEvent.click(screen.getByRole('button', { name: 'Overview' }))
    expect(await screen.findByText(/start date/i)).toBeInTheDocument()
    expect(screen.getAllByText('Deadline').length).toBeGreaterThan(0)
    expect(screen.queryByText(/add task/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/internal:/i)).not.toBeInTheDocument()

    // Switch to Files tab — customer can see files but not upload
    fireEvent.click(screen.getByRole('button', { name: /^files/i }))
    expect(await screen.findByText('seo-brief.pdf')).toBeInTheDocument()
    expect(screen.queryByText(/upload file/i)).not.toBeInTheDocument()
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

    // Tasks tab (default) — add-task form and internal notes visible for admin
    expect((await screen.findAllByText('Add Task')).length).toBeGreaterThan(0)
    expect(screen.getByText(/internal: check crawl budget/i)).toBeInTheDocument()
    expect(screen.getAllByDisplayValue('open').length).toBeGreaterThan(0)

    // Switch to Overview tab — Team Members card visible when members exist
    fireEvent.click(screen.getByRole('button', { name: 'Overview' }))
    expect(await screen.findByText(/team members/i)).toBeInTheDocument()

    // Switch to Files tab — admin sees the upload button
    fireEvent.click(screen.getByRole('button', { name: /^files/i }))
    expect(await screen.findByText(/upload file/i)).toBeInTheDocument()
  })

  it('staff can update the project status', async () => {
    mockRole = { isCustomer: false, isStaff: true, isAdmin: false, role: 'staff' }
    getProjectMock.mockResolvedValueOnce({
      id: 1,
      name: 'SEO Growth',
      description: 'Public progress',
      project_type: 'seo',
      status: 'open',
      visibility: 'customer_visible',
      progress_percent: 50,
      start_date: '2026-06-01',
      due_date: '2026-06-30',
    })
    renderDetail()

    fireEvent.change(await screen.findByLabelText('Project status'), { target: { value: 'working' } })

    await waitFor(() => {
      expect(updateProjectMock).toHaveBeenCalledWith('1', { status: 'working' })
    })
  })

  it('admin can undo an archive back to the prior status', async () => {
    mockRole = { isCustomer: false, isStaff: false, isAdmin: true, role: 'admin' }
    renderDetail()

    fireEvent.click(await screen.findByRole('button', { name: 'Archive' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Undo archive' }))

    await waitFor(() => {
      expect(updateProjectMock).toHaveBeenCalledWith('1', { status: 'working' })
    })
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
