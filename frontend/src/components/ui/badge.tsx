import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/cn"
import { Slot } from "radix-ui"

type BadgeProps = React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }


const badgeVariants = cva(  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-4xl border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground [a]:hover:bg-primary/80",
        secondary:
          "bg-secondary text-secondary-foreground [a]:hover:bg-secondary/80",
        destructive:
          "bg-destructive/10 text-destructive focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:focus-visible:ring-destructive/40 [a]:hover:bg-destructive/20",
        outline:
          "border-border text-foreground [a]:hover:bg-surface [a]:hover:text-muted",
        ghost:
          "hover:bg-surface hover:text-muted dark:hover:bg-surface/50",
        link: "text-primary underline-offset-4 hover:underline",
        /* Status variants. These replace the ad-hoc .badge-green / -amber /
           -blue / -grey classes this file used to be paired with, so a status
           is picked from the same variant list as everything else rather than
           from a second parallel set of class names. The wash/edge pairs carry
           the translucency, which is what keeps the tint readable in both
           schemes without a second set of dark: overrides. */
        success:
          "border-[var(--green-edge)] bg-[var(--green-wash)] text-[var(--green)]",
        warning:
          "border-[var(--amber-edge)] bg-[var(--amber-wash)] text-[var(--amber)]",
        info: "border-[var(--info-edge)] bg-[var(--info-wash)] text-[var(--info)]",
        neutral:
          "border-[var(--border)] bg-[var(--surface)] text-[var(--muted)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  asChild = false,
  ...props
}: BadgeProps) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants, type BadgeProps }
