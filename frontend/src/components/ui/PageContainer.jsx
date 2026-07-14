import { cn } from '@/lib/utils'

export function PageContainer({ children, className, as: Comp = 'div' }) {
  return (
    <Comp className={cn('mx-auto w-full max-w-content space-y-6 px-4 py-5 sm:px-6 sm:py-6 lg:px-8 lg:py-8', className)}>
      {children}
    </Comp>
  )
}
