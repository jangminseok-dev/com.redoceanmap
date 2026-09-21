"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CircleCheck, CircleX, LoaderCircle } from "lucide-react";
import { apiVerifyEmail } from "@/lib/authApi";
import { Button } from "@/components/ui/button";

type Result = { status: "checking" | "done" | "failed"; message: string };

// 메일 링크가 도착하는 화면 — 로그인하지 않은 기기에서 눌러도 된다(토큰이 주소 소유를 증명한다)
function VerifyEmail() {
  const token = useSearchParams()?.get("token") ?? "";
  const [result, setResult] = useState<Result>({ status: "checking", message: "이메일을 확인하고 있어요…" });

  useEffect(() => {
    if (!token) {
      setResult({ status: "failed", message: "링크가 올바르지 않아요. 메일의 링크를 다시 눌러 주세요." });
      return;
    }
    apiVerifyEmail(token)
      .then(() => setResult({ status: "done", message: "이메일 인증이 끝났어요. 이제 메일 알림을 받을 수 있어요." }))
      .catch((e: Error) => setResult({ status: "failed", message: e.message }));
  }, [token]);

  const Icon = result.status === "done" ? CircleCheck : result.status === "failed" ? CircleX : LoaderCircle;
  return (
    <main className="min-h-dvh grid place-items-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-6 text-center" role="status">
        <Icon
          size={28}
          className={`mx-auto ${result.status === "done" ? "text-brand" : "text-foreground-muted"} ${result.status === "checking" ? "animate-spin" : ""}`}
        />
        <h1 className="mt-3 text-base font-semibold">이메일 인증</h1>
        <p className="mt-1.5 text-sm text-foreground-muted leading-relaxed">{result.message}</p>
        {result.status !== "checking" && (
          <Button asChild size="lg" className="mt-5 w-full">
            <Link href={result.status === "done" ? "/" : "/profile"}>
              {result.status === "done" ? "redoceanmap으로 가기" : "프로필에서 다시 받기"}
            </Link>
          </Button>
        )}
      </div>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmail />
    </Suspense>
  );
}
