import { cn } from '@/lib/utils'

export function Card({ className, ...props }) {
  return <div className={cn('rounded-lg border border-border bg-surface text-foreground shadow-sm', className)} {...props} />
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex flex-col space-y-1.5 p-5', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return <h3 className={cn('card-title', className)} {...props} />
}

export function CardDescription({ className, ...props }) {
  return <p className={cn('secondary-text', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('p-5 pt-0', className)} {...props} />
}

export function CardFooter({ className, ...props }) {
  return <div className={cn('flex items-center border-t border-border p-5', className)} {...props} />
}
