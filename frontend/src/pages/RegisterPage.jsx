import { Link } from 'react-router-dom'

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6">
      <div className="w-full max-w-sm text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto">
          <svg className="w-6 h-6 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round"
              d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
        <h1 className="font-display font-bold text-2xl text-foreground">Account required</h1>
        <p className="text-sm text-muted-foreground">
          Accounts are created by the OSD support team. Please contact your administrator to get access.
        </p>
        <p className="text-sm text-muted-foreground">
          Email:{' '}
          <a href="mailto:ticket@osd.vn" className="text-primary hover:underline font-medium">
            ticket@osd.vn
          </a>
        </p>
        <Link
          to="/login"
          className="inline-block mt-2 px-5 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:opacity-90 transition"
        >
          Back to login
        </Link>
      </div>
    </div>
  )
}
