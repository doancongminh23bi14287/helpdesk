import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
  'p', 'br', 'b', 'strong', 'i', 'em', 'u', 'ul', 'ol', 'li',
  'blockquote', 'pre', 'code', 'a', 'span', 'div', 'h1', 'h2',
  'h3', 'h4', 'table', 'thead', 'tbody', 'tr', 'td', 'th',
]

const ALLOWED_ATTR = ['href', 'target', 'rel', 'class']

const FORBID_TAGS = ['script', 'style', 'iframe', 'object',
                     'embed', 'form', 'input', 'button', 'svg']

// Force all links to open in a new tab safely.
// Registered once — DOMPurify deduplicates hook registrations.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

export default function SafeHtml({ html, className }) {
  const clean = DOMPurify.sanitize(html ?? '', {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    FORBID_TAGS,
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
    ALLOW_DATA_ATTR: false,
  })

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
}
