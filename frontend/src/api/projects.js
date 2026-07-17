import client from '@/api/client'

export const listProjects = (params = {}) =>
  client.get('/projects', { params }).then(r => r.data)

export const getProject = (id) =>
  client.get(`/projects/${id}`).then(r => r.data)

export const createProject = (payload) =>
  client.post('/projects', payload).then(r => r.data)

export const updateProject = (id, payload) =>
  client.patch(`/projects/${id}`, payload).then(r => r.data)

export const cancelProject = (id) =>
  client.delete(`/projects/${id}`).then(r => r.data)

export const deleteProjectPermanently = (id) =>
  client.delete(`/projects/${id}/permanent`).then(r => r.data)

export const listProjectTasks = (projectId, params = {}) =>
  client.get(`/projects/${projectId}/tasks`, { params }).then(r => r.data)

export const createProjectTask = (projectId, payload) =>
  client.post(`/projects/${projectId}/tasks`, payload).then(r => r.data)

export const getProjectTask = (taskId) =>
  client.get(`/project-tasks/${taskId}`).then(r => r.data)

export const updateProjectTask = (taskId, payload) =>
  client.patch(`/project-tasks/${taskId}`, payload).then(r => r.data)

export const updateProjectTaskStatus = (taskId, status) =>
  client.patch(`/project-tasks/${taskId}/status`, { status }).then(r => r.data)

export const cancelProjectTask = (taskId) =>
  client.delete(`/project-tasks/${taskId}`).then(r => r.data)

export const listProjectDocuments = (projectId) =>
  client.get(`/projects/${projectId}/documents`).then(r => r.data)

export const uploadProjectDocument = (projectId, file, isClientVisible = false) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('is_client_visible', String(isClientVisible))
  return client.post(`/projects/${projectId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const downloadProjectDocument = async (projectId, projectDocument) => {
  const res = await client.get(`/projects/${projectId}/documents/${projectDocument.id}/download`, {
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = projectDocument.file_name ?? `project-document-${projectDocument.id}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export const getProjectTickets = (projectId) =>
  client.get(`/projects/${projectId}/tickets`).then(r => r.data)

export const getProjectTasks = (projectId, params = {}) =>
  client.get(`/projects/${projectId}/tasks`, { params }).then(r => r.data)

export const createTaskComment = (taskId, payload) =>
  client.post(`/project-tasks/${taskId}/comments`, payload).then(r => r.data)

export const listTaskComments = (taskId) =>
  client.get(`/project-tasks/${taskId}/comments`).then(r => r.data)

export const getTaskActivities = (taskId) =>
  client.get(`/project-tasks/${taskId}/activities`).then(r => r.data)

export const getProjectDiscussion = (projectId, page = 1, perPage = 50) =>
  client.get(`/projects/${projectId}/discussion`, { params: { page, per_page: perPage } }).then(r => r.data)

export const postProjectDiscussion = (projectId, payload) =>
  client.post(`/projects/${projectId}/discussion`, payload).then(r => r.data)

export const submitTaskApproval = (taskId, payload) =>
  client.post(`/project-tasks/${taskId}/approval`, payload).then(r => r.data)

export const getTaskApprovals = (taskId) =>
  client.get(`/project-tasks/${taskId}/approvals`).then(r => r.data)

export const addProjectMember = (projectId, payload) =>
  client.post(`/projects/${projectId}/members`, payload).then(r => r.data)

export const listProjectMembers = (projectId) =>
  client.get(`/projects/${projectId}/members`).then(r => r.data)

export const removeProjectMember = (projectId, userId) =>
  client.delete(`/projects/${projectId}/members/${userId}`)
