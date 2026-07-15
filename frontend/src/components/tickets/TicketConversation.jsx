import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LockClosedIcon } from '@heroicons/react/24/outline'
import { formatDistanceToNow } from 'date-fns'

import AttachmentList from '@/components/ui/AttachmentList'
import { Card } from '@/components/ui'
import { cn, parseUTC } from '@/lib/utils'

import { TicketBody } from './TicketContent'
import { TicketComposer } from './TicketComposer'

function formatRelative(time) {
  const date = parseUTC(time)
  if (!date || Number.isNaN(date.getTime())) return ''
  try {
    return formatDistanceToNow(date, { addSuffix: true })
  } catch {
    return ''
  }
}

function isCurrentUserMessage(item, currentUserId) {
  return item?.author_id != null && currentUserId != null && Number(item.author_id) === Number(currentUserId)
}

function getAuthorName(item, ticket) {
  if (item.kind === 'original') {
    return item.author_name || item.author_email || 'Customer'
  }
  return item.author_name || item.author_email?.split('@')[0] || item.author_email || 'Unknown author'
}

function getRoleLabel(item, ticket, mine) {
  if (item.kind === 'original') return 'Original request'
  const customerMessage = Number(item.author_id) === Number(ticket.raised_by)
  if (item.is_internal) return 'Internal note'
  if (mine) return 'Your reply'
  return customerMessage ? 'Customer reply' : 'Staff reply'
}

function buildTimeline(ticket, replies) {
  const original = {
    id: `ticket-${ticket.id}-original`,
    author_id: ticket.raised_by,
    author_email: ticket.raised_by_email,
    author_name: ticket.raised_by_name || ticket.raised_by_email || 'Customer',
    content: ticket.description || '',
    created_at: ticket.created_at,
    is_internal: false,
    source: 'portal',
    kind: 'original',
  }

  const orderedReplies = [...(replies || [])]
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .map((reply) => ({ ...reply, kind: 'reply' }))

  return [original, ...orderedReplies]
}

function groupTimelineItems(ticket, replies, currentUserId) {
  const timeline = buildTimeline(ticket, replies)
  const groups = []

  for (const item of timeline) {
    const mine = item.kind !== 'original' && isCurrentUserMessage(item, currentUserId)
    const side = item.kind === 'original' ? 'left' : (mine ? 'right' : 'left')
    const prev = groups[groups.length - 1]
    const mergeable = prev
      && prev.side === side
      && prev.authorId === item.author_id
      && prev.isInternal === Boolean(item.is_internal)
      && item.kind !== 'original'

    if (mergeable) {
      prev.items.push(item)
      prev.latestAt = item.created_at
    } else {
      groups.push({
        side,
        authorId: item.author_id,
        authorName: item.kind === 'original' ? getAuthorName(item, ticket) : (mine ? 'You' : getAuthorName(item, ticket)),
        roleLabel: getRoleLabel(item, ticket, mine),
        isInternal: Boolean(item.is_internal),
        items: [item],
        latestAt: item.created_at,
      })
    }
  }

  return groups
}

function MessageBubble({ item, ticket, currentUserId, currentUserName, attachments, showHeader = true }) {
  const mine = item.kind !== 'original' && isCurrentUserMessage(item, currentUserId)
  const toneClass = item.is_internal
    ? 'bg-warning-muted/70 border-warning/15'
    : mine
      ? 'bg-surface border-border/75'
      : 'bg-surface-muted/55 border-border/70'
  const alignClass = mine ? 'ml-auto' : 'mr-auto'
  const name = item.kind === 'original'
    ? getAuthorName(item, ticket)
    : (mine ? 'You' : getAuthorName(item, ticket))
  const role = getRoleLabel(item, ticket, mine)
  const noteIcon = item.is_internal ? (
    <span
      className="absolute right-2 top-2 inline-flex items-center justify-center rounded-full text-muted-foreground"
      aria-label="Internal note"
      title="Internal note"
    >
      <LockClosedIcon className="h-3.5 w-3.5" aria-hidden="true" />
    </span>
  ) : null

  return (
    <div className={cn('flex w-full', mine ? 'justify-end' : 'justify-start')}>
      <div className={cn('w-full max-w-[85%] sm:max-w-[80%] lg:max-w-[76%]', alignClass)}>
        {showHeader && (
          <div className={cn('mb-1.5 flex items-center gap-2 text-[11px] leading-4 text-muted-foreground', mine ? 'justify-end text-right' : 'justify-start text-left')}>
            <span className="font-medium text-secondary-foreground" title={mine && currentUserName ? currentUserName : undefined}>{name}</span>
            <span>{role}</span>
            <time className="tabular-nums" dateTime={item.created_at}>
              {formatRelative(item.created_at)}
            </time>
          </div>
        )}

        <div className={cn('relative rounded-xl border px-4 py-3 text-sm leading-6 shadow-none', toneClass, noteIcon && 'pr-8')}>
          {noteIcon}
          <TicketBody content={item.content} />
          {attachments.length > 0 && <AttachmentList attachments={attachments} />}
        </div>
      </div>
    </div>
  )
}

export function TicketConversation({
  ticket,
  replies,
  attachments = [],
  currentUserId,
  currentUserName,
  message,
  onMessageChange,
  isInternal,
  onInternalChange,
  files,
  onAddFiles,
  onRemoveFile,
  onSubmit,
  sending,
  error,
  isStaffOrAdmin,
  isClosed,
  scrollSignal = 0,
}) {
  const scrollRef = useRef(null)
  const didInitialScrollRef = useRef(false)
  const previousCountRef = useRef(0)
  const previousLastIdRef = useRef(null)
  const lastScrollSignalRef = useRef(scrollSignal)
  const isNearBottomRef = useRef(true)
  const [unseenCount, setUnseenCount] = useState(0)

  const timeline = useMemo(() => groupTimelineItems(ticket, replies, currentUserId), [ticket, replies, currentUserId])
  const itemCount = useMemo(() => timeline.reduce((count, group) => count + group.items.length, 0), [timeline])
  const latestItem = useMemo(() => {
    if (!timeline.length) return null
    const lastGroup = timeline[timeline.length - 1]
    return lastGroup.items[lastGroup.items.length - 1] || null
  }, [timeline])

  const scrollToBottom = useCallback((behavior = 'auto') => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
  }, [])

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const nearBottom = distanceFromBottom <= 80
    isNearBottomRef.current = nearBottom
    if (nearBottom) {
      setUnseenCount(0)
    }
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    const currentLastId = latestItem?.id ?? null
    const previousCount = previousCountRef.current
    const previousLastId = previousLastIdRef.current
    const countChanged = itemCount !== previousCount || currentLastId !== previousLastId

    if (!didInitialScrollRef.current) {
      requestAnimationFrame(() => scrollToBottom('auto'))
      didInitialScrollRef.current = true
      setUnseenCount(0)
      isNearBottomRef.current = true
    } else if (scrollSignal !== lastScrollSignalRef.current) {
      lastScrollSignalRef.current = scrollSignal
      requestAnimationFrame(() => scrollToBottom('auto'))
      setUnseenCount(0)
      isNearBottomRef.current = true
    } else if (countChanged) {
      const added = Math.max(0, itemCount - previousCount)
      const latestIsMine = latestItem && latestItem.kind !== 'original' && isCurrentUserMessage(latestItem, currentUserId)
      if (latestIsMine || isNearBottomRef.current) {
        requestAnimationFrame(() => scrollToBottom('auto'))
        setUnseenCount(0)
        isNearBottomRef.current = true
      } else if (added > 0) {
        setUnseenCount((count) => count + added)
      }
    }

    previousCountRef.current = itemCount
    previousLastIdRef.current = currentLastId
  }, [itemCount, latestItem, currentUserId, scrollSignal, scrollToBottom])

  const originalAttachments = useMemo(
    () => attachments.filter((attachment) => attachment.reply_id == null),
    [attachments],
  )

  const getReplyAttachments = useCallback((item) => {
    if (item.kind === 'original') return originalAttachments
    return attachments.filter((attachment) => Number(attachment.reply_id) === Number(item.id))
  }, [attachments, originalAttachments])

  return (
    <Card className="flex h-full min-h-[28rem] flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2.5 sm:px-5">
        <div className="min-w-0">
          <h2 id="conversation-title" className="section-title">Conversation ({itemCount})</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Replies in chronological order</p>
        </div>
      </div>

      <div className="relative min-h-0 flex-1">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className={cn(
            'ticket-conversation-scrollbar h-full min-h-0 overflow-y-auto overscroll-y-auto px-4 py-4 sm:px-5 sm:py-5',
            itemCount === 0 && 'pb-5',
          )}
        >
          <div className="space-y-2.5 pb-2">
            {timeline.map((group) => (
              <div key={`${group.authorId}-${group.latestAt}`} className="space-y-1.5">
                {group.items.map((item, index) => (
                  <MessageBubble
                    key={item.id}
                    item={item}
                    ticket={ticket}
                    currentUserId={currentUserId}
                    currentUserName={currentUserName}
                    attachments={getReplyAttachments(item)}
                    showHeader={index === 0}
                  />
                ))}
              </div>
            ))}

            {timeline.length === 0 && (
              <div className="rounded-xl bg-surface-muted/45 px-4 py-5 text-sm text-muted-foreground">
                No conversation yet.
              </div>
            )}
          </div>
        </div>

        {unseenCount > 0 && (
          <button
            type="button"
            onClick={() => {
              scrollToBottom('smooth')
              setUnseenCount(0)
              isNearBottomRef.current = true
            }}
            className="absolute bottom-4 right-4 z-10 inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs font-medium text-foreground shadow-sm transition-colors hover:bg-surface-muted"
            aria-label={`Scroll to ${unseenCount} new messages`}
          >
            <span aria-hidden="true">↓</span>
            <span>{unseenCount} tin nhắn mới</span>
          </button>
        )}
      </div>

      <div className="shrink-0 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur sm:px-5">
        {isClosed ? (
          <div className="rounded-xl bg-surface-muted/60 px-4 py-3 text-center text-sm text-muted-foreground">
            This ticket is closed and no longer accepts replies.
          </div>
        ) : (
          <TicketComposer
            ticketId={ticket.id}
            message={message}
            onMessageChange={onMessageChange}
            isInternal={isInternal}
            onInternalChange={onInternalChange}
            files={files}
            onAddFiles={onAddFiles}
            onRemoveFile={onRemoveFile}
            onSubmit={onSubmit}
            sending={sending}
            error={error}
            isStaffOrAdmin={isStaffOrAdmin}
            embedded
          />
        )}
      </div>
    </Card>
  )
}
