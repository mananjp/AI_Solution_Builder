import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  // One base string, not several. cva's signature is (base, config), so extra
  // arguments break the overload and VariantProps stops resolving — which shows
  // up as `variant` and `size` disappearing from the component's props.
  //
  // Shape and elevation follow the lab controls: the raised shadow and the
  // press-scale come from theme-toggle and magnetic-button. The radius is
  // deliberately not `rounded-full` — a stadium only reads correctly on a
  // circular icon control, and on a text button the fully-round end caps crowd
  // the label. This is the app's single control radius: `rounded-sm`,
  // `rounded-md` and `rounded-lg` all resolve to the same value in globals.css,
  // so a hand-written `rounded-sm` button matches this one without either call
  // site knowing. The two larger sizes step up to `rounded-xl` to keep the
  // proportion.
  //
  // Colours are unchanged: every variant already resolves through theme tokens,
  // and --primary is var(--foreground), so the solid variant is the same
  // monochrome as the rest of the app. The decorative `border
  // border-transparent` is gone — it drew nothing but inset the content by 1px.
  "group/button inline-flex shrink-0 cursor-pointer touch-manipulation select-none items-center justify-center rounded-lg bg-clip-padding text-sm font-medium shadow-raised whitespace-nowrap outline-hidden transition-[background-color,color,box-shadow,scale] duration-150 ease-out active:scale-[0.96] motion-reduce:transition-[background-color,color] focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-2 focus-visible:outline-foreground disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:outline-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/85",
        outline:
          "bg-transparent text-foreground hover:bg-surface hover:text-foreground aria-expanded:bg-surface aria-expanded:text-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_5%)] aria-expanded:bg-secondary aria-expanded:text-secondary-foreground",
        ghost:
          "bg-transparent shadow-none hover:bg-surface hover:text-foreground aria-expanded:bg-surface aria-expanded:text-foreground dark:hover:bg-surface/50",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:outline-destructive dark:bg-destructive/20 dark:hover:bg-destructive/30",
        link: "bg-transparent text-primary underline-offset-4 shadow-none hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-3 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 px-2.5 text-[0.8rem] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-10 gap-2 rounded-xl px-5 text-sm has-data-[icon=inline-end]:pr-3.5 has-data-[icon=inline-start]:pl-3.5",
        pill: "h-12 gap-2 rounded-xl px-6 text-sm has-data-[icon=inline-end]:pr-4 has-data-[icon=inline-start]:pl-4",
        icon: "size-8",
        "icon-xs": "size-6 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-7",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
