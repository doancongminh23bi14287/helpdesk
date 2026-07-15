import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { useTicket } from '@/hooks/useTickets'
import { useAuthStore } from '@/hooks/useAuth'
import { useRole } from '@/hooks/useRole'
import { subscribeSocketEvent } from '@/hooks/useSocket'
import {
  acceptTransfer,
  assignTicket,
  createProjectFromTicket,
  createTransferRequest,
  declineTransfer,
  getTransferRequest,
  linkProject,
  unlinkProject,
  updateTicket,
} from '@/api/tickets'
import { listUsers } from '@/api/users'
import { listProjects } from '@/api/projects'
import { getAttachments, uploadAttachment } from '@/api/attachments'
import client from '@/api/client'

import { ConfirmDialog, ErrorState, LoadingState } from '@/components/ui'
import { TicketDetailHeader } from '@/components/tickets/TicketDetailHeader'
import { TicketConversation } from '@/components/tickets/TicketConversation'
import { TicketSidebar } from '@/components/tickets/TicketSidebar'
import { LinkProjectDialog, TransferTicketDialog } from '@/components/tickets/TicketDialogs'

const VALID_NEXT = {
  Open: ['In Progress'],
  'In Progress': ['Waiting', 'Resolved'],
  Waiting: ['In Progress', 'Resolved'],
  Resolved: ['Closed', 'In Progress'],
  Closed: ['Open'],
}

export default function TicketDetailPage() {
  const { id } = useParams()
  const {
    ticket,
    comments: replies = [],
    activities = [],
    sla,
    loading,
    error: ticketError,
    reply,
    refetch,
    appendReply,
    silentRefetch,
  } = useTicket(id)
  const { user } = useAuthStore()
  const { isStaff, isAdmin } = useRole()
  const isStaffOrAdmin = isStaff || isAdmin

  const [message, setMessage] = useState('')
  const [isInternal, setIsInternal] = useState(false)
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState('')
  const [statusUpdating, setStatusUpdating] = useState(false)

  const [attachments, setAttachments] = useState([])
  const [replyFiles, setReplyFiles] = useState([])
  const [uploadError, setUploadError] = useState('')

  const [staffList, setStaffList] = useState([])
  const [transferReq, setTransferReq] = useState(null)
  const [assignUpdating, setAssignUpdating] = useState(false)
  const [assignmentError, setAssignmentError] = useState('')
  const [showTransferDialog, setShowTransferDialog] = useState(false)

  const [projectActionLoading, setProjectActionLoading] = useState(false)
  const [showLinkProjectDialog, setShowLinkProjectDialog] = useState(false)
  const [showUnlinkConfirm, setShowUnlinkConfirm] = useState(false)
  const [projectSearch, setProjectSearch] = useState('')
  const [projectSearchResults, setProjectSearchResults] = useState([])

  const [aiPrediction, setAiPrediction] = useState(null)
  const [summary, setSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  const refreshAttachments = useCallback(() => {
    if (!id) return
    getAttachments(id).then(setAttachments).catch(() => {})
  }, [id])

  useEffect(() => {
    if (!ticket) return
    refreshAttachments()

    if (isStaffOrAdmin) {
      client.get(`/ai/tickets/${id}/summary`)
        .then((response) => {
          if (!response.data) return
          setSummary(response.data)
          setCooldown(response.data.cooldown_remaining || 0)
        })
        .catch(() => {})
    }
  }, [id, ticket?.id, isStaffOrAdmin, refreshAttachments])

  useEffect(() => {
    if (cooldown <= 0) return undefined
    const timer = setInterval(() => setCooldown((value) => Math.max(0, value - 1)), 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  useEffect(() => {
    if (!isAdmin) return
    listUsers({ role: 'staff', per_page: 100 })
      .then((data) => setStaffList(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => {})
  }, [isAdmin])

  const loadTransferRequest = useCallback(() => {
    if (!id || !isStaffOrAdmin) return
    getTransferRequest(id)
      .then((data) => setTransferReq(data || null))
      .catch(() => setTransferReq(null))
  }, [id, isStaffOrAdmin])

  useEffect(() => {
    loadTransferRequest()
  }, [loadTransferRequest])

  useEffect(() => {
    const ticketId = Number(id)
    return subscribeSocketEvent('new_reply', (data) => {
      if (Number(data.ticket_id) !== ticketId) return
      silentRefetch?.()
      refreshAttachments()
    })
  }, [id, silentRefetch, refreshAttachments])

  useEffect(() => {
    if (!showLinkProjectDialog) return undefined
    if (!projectSearch.trim()) {
      setProjectSearchResults([])
      return undefined
    }

    const timer = setTimeout(() => {
      listProjects({ q: projectSearch.trim(), org_id: ticket?.org_id, per_page: 20 })
        .then((data) => setProjectSearchResults(Array.isArray(data) ? data : (data?.items ?? [])))
        .catch(() => setProjectSearchResults([]))
    }, 300)

    return () => clearTimeout(timer)
  }, [projectSearch, showLinkProjectDialog, ticket?.org_id])

  const handleSummarize = async () => {
    if (summaryLoading) return
    setSummaryLoading(true)
    try {
      const response = await client.post(`/ai/tickets/${id}/summarize`)
      setSummary(response.data)
      setCooldown(response.data.cooldown_remaining || 120)
    } catch (requestError) {
      if (requestError.response?.status === 429) setCooldown(120)
    } finally {
      setSummaryLoading(false)
    }
  }

  const handleSend = async (event) => {
    event.preventDefault()
    if (sending || (!message.trim() && replyFiles.length === 0)) return

    setSending(true)
    setSendError('')
    setUploadError('')
    try {
      const created = await reply(message.trim(), isInternal)
      appendReply?.(created)

      if (replyFiles.length > 0) {
        const results = await Promise.allSettled(
          replyFiles.map((file) => uploadAttachment(id, file, created?.id)),
        )
        const failed = results.find((result) => result.status === 'rejected')
        if (failed) {
          setUploadError(failed.reason?.message || 'The reply was sent, but an attachment could not be uploaded.')
        } else {
          setReplyFiles([])
        }
      }

      setMessage('')
      setIsInternal(false)
      refreshAttachments()
    } catch (requestError) {
      setSendError(requestError.response?.data?.detail || requestError.message || 'Failed to send reply')
    } finally {
      setSending(false)
    }
  }

  const handleStatusChange = useCallback(async (newStatus) => {
    if (!ticket || statusUpdating) return
    setStatusUpdating(true)
    try {
      await updateTicket(ticket.id, { status: newStatus })
      await refetch()
    } finally {
      setStatusUpdating(false)
    }
  }, [ticket, statusUpdating, refetch])

  const handleAssign = async (newAssigneeId) => {
    if (assignUpdating) return
    setAssignUpdating(true)
    setAssignmentError('')
    try {
      if (newAssigneeId) {
        await assignTicket(ticket.id, Number(newAssigneeId))
      } else {
        await updateTicket(ticket.id, { assignee_ids: [], assignment_mode: 'none' })
      }
      await refetch()
      loadTransferRequest()
    } catch (requestError) {
      setAssignmentError(requestError.response?.data?.detail || requestError.message || 'Assignment update failed')
    } finally {
      setAssignUpdating(false)
    }
  }

  const handleRequestTransfer = async (toStaffId) => {
    try {
      const request = await createTransferRequest(ticket.id, toStaffId)
      setTransferReq(request)
      setShowTransferDialog(false)
    } catch (requestError) {
      setAssignmentError(requestError.response?.data?.detail || requestError.message || 'Transfer request failed')
    }
  }

  const handleAcceptTransfer = async () => {
    if (!transferReq) return
    try {
      await acceptTransfer(ticket.id, transferReq.id)
      setTransferReq(null)
      await refetch()
      loadTransferRequest()
    } catch (requestError) {
      setAssignmentError(requestError.response?.data?.detail || requestError.message || 'Transfer failed')
    }
  }

  const handleDeclineTransfer = async () => {
    if (!transferReq) return
    try {
      await declineTransfer(ticket.id, transferReq.id)
      setTransferReq(null)
      loadTransferRequest()
    } catch (requestError) {
      setAssignmentError(requestError.response?.data?.detail || requestError.message || 'Transfer failed')
    }
  }

  const handleCreateProject = async () => {
    if (!ticket || projectActionLoading) return
    setProjectActionLoading(true)
    try {
      await createProjectFromTicket(id)
      await refetch()
    } catch (requestError) {
      window.alert(requestError.response?.data?.detail || 'Failed to create project')
    } finally {
      setProjectActionLoading(false)
    }
  }

  const closeProjectDialog = () => {
    setShowLinkProjectDialog(false)
    setProjectSearch('')
    setProjectSearchResults([])
  }

  const handleLinkProject = async (projectId) => {
    if (projectActionLoading) return
    setProjectActionLoading(true)
    try {
      await linkProject(id, projectId)
      closeProjectDialog()
      await refetch()
    } catch (requestError) {
      window.alert(requestError.response?.data?.detail || 'Failed to link project')
    } finally {
      setProjectActionLoading(false)
    }
  }

  const handleUnlinkProject = async () => {
    if (projectActionLoading) return
    setProjectActionLoading(true)
    try {
      await unlinkProject(id)
      setShowUnlinkConfirm(false)
      await refetch()
    } catch (requestError) {
      window.alert(requestError.response?.data?.detail || 'Failed to unlink project')
    } finally {
      setProjectActionLoading(false)
    }
  }

  if (loading) {
    return <LoadingState className="mx-auto max-w-content px-4 py-8 sm:px-6" label="Loading ticket" rows={8} />
  }

  if (ticketError || !ticket) {
    return (
      <div className="mx-auto max-w-content px-4 py-8 sm:px-6">
        <ErrorState
          title={ticket ? 'Could not load ticket' : 'Ticket not found'}
          description={ticketError || 'This ticket may not exist or you may not have access to it.'}
          onRetry={refetch}
        />
      </div>
    )
  }

  const isClosed = ticket.status === 'Closed'
  const validNext = VALID_NEXT[ticket.status] ?? []
  const visibleReplies = user?.role === 'customer'
    ? replies.filter((item) => !item.is_internal)
    : replies

  return (
    <div className="bg-background">
      <TicketDetailHeader
        ticket={ticket}
        isStaffOrAdmin={isStaffOrAdmin}
        statusUpdating={statusUpdating}
        validNext={validNext}
        onStatusChange={handleStatusChange}
        aiPrediction={aiPrediction}
      />

      <main className="mx-auto grid w-full max-w-content grid-cols-1 items-start gap-3 px-3 py-3 sm:gap-4 sm:px-6 sm:py-4 lg:grid-cols-[minmax(0,3.1fr)_minmax(18rem,1fr)] lg:gap-5 lg:py-5">
        <div className="min-w-0">
          <TicketConversation
            ticket={ticket}
            replies={visibleReplies}
            attachments={attachments}
            currentUserId={user?.id}
            message={message}
            onMessageChange={setMessage}
            isInternal={isInternal}
            onInternalChange={setIsInternal}
            files={replyFiles}
            onAddFiles={(newFiles) => {
              const names = new Set(replyFiles.map((file) => file.name))
              setReplyFiles((current) => [...current, ...newFiles.filter((file) => !names.has(file.name))])
            }}
            onRemoveFile={(name) => setReplyFiles((current) => current.filter((file) => file.name !== name))}
            onSubmit={handleSend}
            sending={sending}
            error={sendError || uploadError}
            isStaffOrAdmin={isStaffOrAdmin}
            isClosed={isClosed}
          />
        </div>

        <div className="lg:sticky lg:top-4">
          <TicketSidebar
          ticket={ticket}
          sla={sla}
          activities={activities}
          isStaffOrAdmin={isStaffOrAdmin}
          isAdmin={isAdmin}
          isStaff={isStaff}
          user={user}
          staffList={staffList}
          transferReq={transferReq}
          assignUpdating={assignUpdating}
          assignmentError={assignmentError}
          projectActionLoading={projectActionLoading}
          onAssign={handleAssign}
          onOpenTransfer={() => setShowTransferDialog(true)}
          onAcceptTransfer={handleAcceptTransfer}
          onDeclineTransfer={handleDeclineTransfer}
          onCreateProject={handleCreateProject}
          onOpenLinkProject={() => setShowLinkProjectDialog(true)}
          onUnlinkProject={() => setShowUnlinkConfirm(true)}
          onPredictionChange={setAiPrediction}
          summary={summary}
          summaryLoading={summaryLoading}
          cooldown={cooldown}
          onSummarize={handleSummarize}
          />
        </div>
      </main>

      <LinkProjectDialog
        open={showLinkProjectDialog}
        onClose={closeProjectDialog}
        search={projectSearch}
        onSearchChange={setProjectSearch}
        results={projectSearchResults}
        loading={projectActionLoading}
        onSelect={handleLinkProject}
      />

      <TransferTicketDialog
        open={showTransferDialog}
        onClose={() => setShowTransferDialog(false)}
        staff={staffList}
        currentUserId={user?.id}
        onSelect={handleRequestTransfer}
      />

      <ConfirmDialog
        open={showUnlinkConfirm}
        onClose={() => setShowUnlinkConfirm(false)}
        onConfirm={handleUnlinkProject}
        title="Unlink project?"
        description="The project and ticket will remain available, but their link will be removed."
        confirmLabel="Unlink project"
        destructive
        isLoading={projectActionLoading}
      />
    </div>
  )
}
