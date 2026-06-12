import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { UserAvatar } from './UserAvatar'

describe('UserAvatar', () => {
  it('renders initials when no avatar_url is provided', () => {
    render(<UserAvatar user={{ full_name: 'Ada Lovelace' }} />)
    expect(screen.getByText('AL')).toBeInTheDocument()
  })

  it('falls back to email when full_name is missing', () => {
    render(<UserAvatar user={{ email: 'demo@example.com' }} />)
    // "demo" -> first two chars uppercased = "DE"
    expect(screen.getByText('DE')).toBeInTheDocument()
  })

  it('renders the image when avatar_url is set', () => {
    render(<UserAvatar user={{ full_name: 'Ada', avatar_url: '/api/auth/avatars/1/abc.png?v=1' }} />)
    const img = screen.getByRole('img', { name: /ada/i })
    expect(img).toBeInTheDocument()
    // The component normalizes relative paths against the configured API
    // base so split-origin deployments still resolve correctly. We only
    // assert the path suffix because the origin depends on the env.
    expect(img.getAttribute('src')).toContain('/api/auth/avatars/1/abc.png?v=1')
  })

  it('falls back to initials when the image fails to load', async () => {
    const { findByText } = render(
      <UserAvatar user={{ full_name: 'Ada Lovelace', avatar_url: '/api/auth/avatars/1/missing.png' }} />,
    )
    const img = document.querySelector('img')
    expect(img).toBeTruthy()
    // Simulate broken image
    img.dispatchEvent(new Event('error'))
    expect(await findByText('AL')).toBeInTheDocument()
  })
})
