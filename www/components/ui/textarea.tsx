import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        // Input과 같은 radius를 쓰되 높이는 내용에 맞춰 늘어난다 (DESIGN.md §4)
        "flex field-sizing-content min-h-16 w-full rounded-xl border border-input bg-transparent px-3.5 py-2.5 text-sm outline-none",
        "transition-[color,box-shadow,border-color] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)]",
        "placeholder:text-muted-foreground",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40",
        "disabled:cursor-not-allowed disabled:opacity-40",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
