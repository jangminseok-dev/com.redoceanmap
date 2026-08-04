import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"
import { Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

// 크기는 높이·radius·폰트가 **한 세트로** 움직인다 — DESIGN.md §4.
// 셋 중 하나만 바꾸거나 표에 없는 단계를 새로 만들지 않는다.
//
//   sm  32px / 8px  / 13px    인라인·칩·테이블 액션
//   md  40px / 12px / 14px    기본 폼·대화상자
//   lg  48px / 12px / 15px    섹션 주요 액션
//   xl  56px / 16px / 17px    화면 단위 주요 액션(주문·가입)
const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap",
    "font-medium outline-none select-none",
    // pressed 피드백 — 촉각적 느낌의 핵심. duration/easing은 DESIGN.md §15의 3단 중 상태 전환.
    "transition-[color,background-color,border-color,transform,opacity] duration-150 ease-[cubic-bezier(0.22,1,0.36,1)]",
    "active:scale-[0.98]",
    "focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/40",
    "disabled:pointer-events-none disabled:opacity-40",
    // 로딩 중에는 흐려지지 않는다 — 진행 중임을 스피너가 이미 말한다
    "data-[loading]:opacity-100",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-brand-deep",
        // 약한 쌍 — 코드 곳곳에 손으로 쓰여 있던 `bg-brand/10 text-brand` 패턴이 이 역할이다
        weak: "bg-accent text-brand hover:bg-secondary",
        outline: "border border-border bg-transparent hover:bg-accent",
        ghost: "hover:bg-accent",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 focus-visible:ring-destructive/30",
        link: "text-brand underline-offset-4 hover:underline active:scale-100",
      },
      size: {
        sm: "h-8 rounded-lg px-3 text-[13px] [&_svg:not([class*='size-'])]:size-3.5",
        md: "h-10 rounded-xl px-4 text-sm [&_svg:not([class*='size-'])]:size-4",
        lg: "h-12 rounded-xl px-5 text-[15px] font-semibold [&_svg:not([class*='size-'])]:size-4",
        xl: "h-14 rounded-2xl px-5 text-[17px] font-semibold [&_svg:not([class*='size-'])]:size-5",
        // 아이콘 버튼은 radius를 크기에 맞추되 원형은 호출부에서 rounded-full로 지정한다
        icon: "size-10 rounded-xl",
        "icon-sm": "size-8 rounded-lg",
        "icon-lg": "size-12 rounded-xl",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "md",
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    /** 진행 중 표시. 라벨 자리를 남겨 **버튼 너비가 유지된다** (DESIGN.md §4·§14). */
    loading?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"
  // asChild는 자식이 단일 엘리먼트여야 한다 — 스피너를 끼우면 Slot이 깨지므로 조합하지 않는다
  const showLoading = loading && !asChild

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      data-loading={showLoading || undefined}
      disabled={disabled || showLoading}
      aria-busy={showLoading || undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {showLoading ? (
        <>
          {/* 라벨을 자리만 남긴다 — "청산"이 "청산 중…"으로 바뀌며 버튼이 들썩이지 않게 */}
          <span className="invisible inline-flex items-center gap-2">{children}</span>
          <Loader2 className="absolute size-4 animate-spin" aria-hidden />
        </>
      ) : (
        children
      )}
    </Comp>
  )
}

export { Button, buttonVariants }
