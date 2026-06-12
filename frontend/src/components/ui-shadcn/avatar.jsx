import * as AvatarPrimitive from '@radix-ui/react-avatar'
import { cn } from '@/lib/utils'

export function Avatar({ className, ...props }) {
  return (
    <AvatarPrimitive.Root
      className={cn('relative flex h-9 w-9 shrink-0 overflow-hidden rounded-full', className)}
      {...props}
    />
  )
}

export function AvatarFallback({ className, ...props }) {
  return (
    <AvatarPrimitive.Fallback
      className={cn('flex h-full w-full items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold', className)}
      {...props}
    />
  )
}
