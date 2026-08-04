import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        // 기하는 Button의 md 단계를 따른다 — 40px / 12px (DESIGN.md §4)
        "h-10 w-full min-w-0 rounded-xl border border-input bg-transparent px-3.5 text-sm outline-none",
        "transition-[color,box-shadow,border-color] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)]",
        "selection:bg-primary selection:text-primary-foreground placeholder:text-muted-foreground",
        "file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40",
        "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    />
  )
}

export { Input }
