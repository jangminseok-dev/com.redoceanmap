"use client";

import { useQuery } from "@tanstack/react-query";
import { ShieldCheck, ShieldOff } from "lucide-react";
import { fetchAdminAudit } from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import Empty from "@/components/admin/Empty";

// action 코드 → 한글 라벨·아이콘 (grant=긍정적 행위는 초록, 아니면 주황)
const ACTION_META: Record<string, { label: string; grant: boolean }> = {
  "role.grant": { label: "역할 부여", grant: true },
  "role.revoke": { label: "역할 회수", grant: false },
  "member.suspend": { label: "계정 정지", grant: false },
  "member.reinstate": { label: "정지 해제", grant: true },
  "member.sessions.revoke": { label: "세션 만료", grant: false },
  "member.withdraw": { label: "탈퇴 처리", grant: false },
  "grade.create": { label: "등급 생성", grant: true },
  "grade.update": { label: "등급 수정", grant: true },
  "grade.delete": { label: "등급 삭제", grant: false },
  "pdf.summarize": { label: "문서 요약", grant: true },
  "image.upload": { label: "이미지 업로드", grant: true },
  "game.capital.grant": { label: "게임 자본 지급", grant: true },
  "game.intervene": { label: "게임 주가 개입", grant: false },
  "game.community.hide": { label: "토론방 글 숨김", grant: false },
  "game.community.unhide": { label: "토론방 숨김 해제", grant: true },
};

export default function AuditPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-audit"],
    queryFn: () => fetchAdminAudit(50),
  });

  const items = data?.items ?? [];

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">감사 로그</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          관리자 행위 기록 (역할·제재·등급·문서·게임 운영 · 최근 50건)
        </p>
      </div>

      <section className="rounded-2xl bg-surface border border-border overflow-hidden">
        {isPending && <BlockSkeleton rows={5} />}
        {isError && <Empty msg="감사 로그를 불러오지 못했습니다." />}
        {!isPending && !isError && items.length === 0 && (
          <Empty msg="아직 기록된 관리자 행위가 없습니다." />
        )}
        {items.length > 0 && (
          <>
            <div className="hidden sm:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                    <th className="font-medium px-5 py-2.5">행위</th>
                    <th className="font-medium px-5 py-2.5">내용</th>
                    <th className="font-medium px-5 py-2.5">행위자</th>
                    <th className="font-medium px-5 py-2.5 text-right">시각</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((e) => (
                    <tr key={e.id} className="border-b border-border last:border-0 hover:bg-background/40">
                      <td className="px-5 py-3">
                        <ActionBadge action={e.action} />
                      </td>
                      <td className="px-5 py-3 text-foreground-muted font-mono text-xs">{e.detail}</td>
                      <td className="px-5 py-3 text-foreground-muted tabular-nums">#{e.actor_id}</td>
                      <td className="px-5 py-3 text-right text-foreground-muted tabular-nums whitespace-nowrap">
                        {e.created_at.slice(0, 16).replace("T", " ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="sm:hidden divide-y divide-border">
              {items.map((e) => (
                <div key={e.id} className="px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <ActionBadge action={e.action} />
                    <span className="text-xs text-foreground-muted tabular-nums">
                      {e.created_at.slice(0, 16).replace("T", " ")}
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs text-foreground-muted font-mono">{e.detail}</p>
                  <p className="mt-1 text-xs text-foreground-muted">행위자 #{e.actor_id}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function ActionBadge({ action }: { action: string }) {
  const meta = ACTION_META[action];
  if (!meta) {
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-foreground/5 text-foreground-muted">
        {action}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
        meta.grant ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
      }`}
    >
      {meta.grant ? <ShieldCheck size={12} /> : <ShieldOff size={12} />}
      {meta.label}
    </span>
  );
}
