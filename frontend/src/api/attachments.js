import client from './client'

export const uploadAttachment = (ticketId, file, replyId = null) => {
  const fd = new FormData()
  fd.append('file', file)
  const url = replyId
    ? `/tickets/${ticketId}/attachments?reply_id=${replyId}`
    : `/tickets/${ticketId}/attachments`
  // Let the browser set Content-Type (including multipart boundary).
  // Axios default headers must not override this.
  return client.post(url, fd, {
    headers: { 'Content-Type': null },
  }).then(r => r.data)
}

export const getAttachments = (ticketId) =>
  client.get(`/tickets/${ticketId}/attachments`).then(r => r.data)

/** Fetch as blob and return an object URL. Caller must revoke when done. */
export const fetchAttachmentBlobUrl = (attachmentId) =>
  client.get(`/attachments/${attachmentId}/download`, { responseType: 'blob' })
    .then(r => window.URL.createObjectURL(r.data))

/**
 * Open viewable files in a new tab (image / pdf / text); download everything else.
 * Uses <a>.click() so it's not blocked by popup blockers.
 */
export const openOrDownloadAttachment = (attachment) => {
  const { id, mime_type, file_name } = attachment
  const viewable =
    mime_type?.startsWith('image/') ||
    mime_type === 'application/pdf' ||
    mime_type?.startsWith('text/')

  client.get(`/attachments/${id}/download`, { responseType: 'blob' })
    .then(r => {
      const blobUrl = window.URL.createObjectURL(r.data)
      const a = document.createElement('a')
      a.href = blobUrl
      if (viewable) {
        a.target = '_blank'
        a.rel = 'noopener noreferrer'
      } else {
        a.download = r.headers['content-disposition']
          ?.match(/filename="?([^"]+)"?/)?.[1] ?? file_name ?? 'download'
      }
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      // keep URL alive long enough for the new tab to read it
      setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60_000)
    })
    .catch(console.error)
}

export const downloadAttachment = (attachmentId) => {
  client.get(`/attachments/${attachmentId}/download`, { responseType: 'blob' })
    .then(response => {
      const blobUrl = window.URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = response.headers['content-disposition']
        ?.match(/filename="?([^"]+)"?/)?.[1] ?? 'download'
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(blobUrl)
      document.body.removeChild(a)
    })
    .catch(console.error)
}
