import { useState, useEffect } from 'react'
import {
  DocumentIcon,
  ArchiveBoxIcon,
  DocumentTextIcon,
  FilmIcon,
  MusicalNoteIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  PhotoIcon,
} from '@heroicons/react/24/outline'
import { fetchAttachmentBlobUrl, openOrDownloadAttachment } from '@/api/attachments'

function fileIcon(mimeType) {
  if (!mimeType) return DocumentIcon
  if (mimeType.startsWith('image/'))  return PhotoIcon
  if (mimeType.startsWith('video/'))  return FilmIcon
  if (mimeType.startsWith('audio/'))  return MusicalNoteIcon
  if (mimeType.startsWith('text/') || mimeType === 'application/pdf') return DocumentTextIcon
  if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('tar'))
    return ArchiveBoxIcon
  return DocumentIcon
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ImageThumb({ attachment }) {
  const [blobUrl, setBlobUrl] = useState(null)
  const [error, setError]     = useState(false)
  const [lightbox, setLightbox] = useState(false)

  useEffect(() => {
    let objectUrl = null
    fetchAttachmentBlobUrl(attachment.id)
      .then(url => { objectUrl = url; setBlobUrl(url) })
      .catch(() => setError(true))
    return () => { if (objectUrl) window.URL.revokeObjectURL(objectUrl) }
  }, [attachment.id])

  // Fallback to file chip if image can't be loaded
  if (error) return <FileChip attachment={attachment} />

  return (
    <>
      <button
        type="button"
        onClick={() => blobUrl && setLightbox(true)}
        className="relative group rounded-lg overflow-hidden border border-gray-200 bg-gray-100 flex items-center justify-center cursor-pointer"
        style={{ width: 160, height: 120 }}
        title={attachment.file_name}
      >
        {blobUrl ? (
          <img src={blobUrl} alt={attachment.file_name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-400 rounded-full animate-spin" />
        )}
        {blobUrl && (
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/25 transition-colors" />
        )}
      </button>

      {/* Lightbox */}
      {lightbox && blobUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex flex-col items-center justify-center p-4"
          onClick={() => setLightbox(false)}
        >
          <div className="flex items-center justify-between w-full max-w-3xl mb-2 px-1">
            <span className="text-white/70 text-sm truncate">{attachment.file_name}</span>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                className="text-white/70 hover:text-white text-xs flex items-center gap-1 px-2 py-1 rounded border border-white/20 hover:border-white/50 transition"
                onClick={e => { e.stopPropagation(); openOrDownloadAttachment(attachment) }}
              >
                <ArrowDownTrayIcon className="w-3.5 h-3.5" /> Download
              </button>
              <button
                className="text-white/70 hover:text-white p-1 rounded-full border border-white/20 hover:border-white/50 transition"
                onClick={() => setLightbox(false)}
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
          <img
            src={blobUrl}
            alt={attachment.file_name}
            className="max-w-full max-h-[80vh] rounded shadow-2xl object-contain"
            onClick={e => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}

function FileChip({ attachment }) {
  const Icon = fileIcon(attachment.mime_type)
  return (
    <button
      type="button"
      onClick={() => openOrDownloadAttachment(attachment)}
      className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 transition-colors max-w-[220px]"
      title={`${attachment.file_name} — click to open`}
    >
      <Icon className="w-4 h-4 text-gray-400 flex-shrink-0" />
      <span className="truncate flex-1 text-left text-xs text-gray-700">{attachment.file_name}</span>
      <span className="text-[10px] text-gray-400 flex-shrink-0">{formatSize(attachment.file_size)}</span>
    </button>
  )
}

export default function AttachmentList({ attachments }) {
  if (!attachments || attachments.length === 0) return null

  const images = attachments.filter(a => a.mime_type?.startsWith('image/'))
  const others  = attachments.filter(a => !a.mime_type?.startsWith('image/'))

  return (
    <div className="mt-3 space-y-2">
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 items-end">
          {images.map(att => (
            <div key={att.id} className="flex flex-col items-start">
              <ImageThumb attachment={att} />
            </div>
          ))}
        </div>
      )}
      {others.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {others.map(att => <FileChip key={att.id} attachment={att} />)}
        </div>
      )}
    </div>
  )
}
