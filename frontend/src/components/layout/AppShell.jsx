import { useState } from 'react'
import { useSocket } from '@/hooks/useSocket'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import { ToastContainer } from '@/components/ui'
import CommandPalette from '@/components/ui/CommandPalette'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { MobileNavigation } from './MobileNavigation'

export default function AppShell({ children }) {
  useSocket()
  const [mobileOpen, setMobileOpen] = useState(false)
  const { open: paletteOpen, setOpen: setPaletteOpen } = useCommandPalette()

  return (
    <div className="flex h-dvh min-w-0 overflow-hidden bg-background">
      <ToastContainer />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

      <div className="hidden shrink-0 md:block">
        <Sidebar onOpenSearch={() => setPaletteOpen(true)} />
      </div>

      <MobileNavigation
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onOpenSearch={() => setPaletteOpen(true)}
      />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Topbar onMenuClick={() => setMobileOpen(true)} />
        <main className="scrollbar-thin min-w-0 flex-1 overflow-x-hidden overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
