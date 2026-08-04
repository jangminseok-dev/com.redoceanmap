"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Plus, Trash2 } from "lucide-react";
import {
  createAdminGrade,
  deleteAdminGrade,
  fetchAdminGrades,
  updateAdminGrade,
  type AdminGrade,
} from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import ConfirmDialog from "@/components/admin/ConfirmDialog";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";
import { showToast } from "@/components/admin/toast";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// 탭 키 → 라벨 (백엔드 hub tab_ontology.TAB_KEYS와 동일한 5종)
const TAB_LABELS: Record<string, string> = {
  history: "지난 대화",
  market: "상권 분석",
  stock: "주식 분석",
  vision: "비전처리",
  automation: "자동화",
};
const TAB_KEYS = Object.keys(TAB_LABELS);

export default function GradesPage() {
  // REACT_RULES 패턴 B: 모달 상태 단일 객체 (추가 폼 입력은 FormData — 패턴 A)
  const [ui, setUi] = useState<{ dialog: AdminGrade | null }>({ dialog: null });
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-grades"],
    queryFn: fetchAdminGrades,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-grades"] });
    queryClient.invalidateQueries({ queryKey: ["admin-roles"] }); // 회원 페이지 역할 칩 동기화
    queryClient.invalidateQueries({ queryKey: ["visible-tabs"] }); // 내 상단 탭 즉시 반영
  };

  const create = useMutation({
    mutationFn: ({ code, name }: { code: string; name: string }) =>
      createAdminGrade(code, name, TAB_KEYS), // 새 등급은 전부 노출로 시작 — 매트릭스에서 조정
    onSuccess: (g) => {
      invalidate();
      showToast(`${g.name} 등급을 추가했습니다.`);
    },
    onError: (e) => showToast(e instanceof Error ? e.message : "등급 추가에 실패했습니다.", "error"),
  });
  const update = useMutation({
    mutationFn: ({ code, body }: { code: string; body: { name?: string; tabs?: string[] } }) =>
      updateAdminGrade(code, body),
    onSuccess: () => invalidate(),
    onError: (e) => showToast(e instanceof Error ? e.message : "변경에 실패했습니다.", "error"),
  });
  const remove = useMutation({
    mutationFn: (code: string) => deleteAdminGrade(code),
    onSuccess: () => {
      invalidate();
      showToast("등급을 삭제했습니다.");
    },
    onError: (e) => showToast(e instanceof Error ? e.message : "삭제에 실패했습니다.", "error"),
  });

  const mutating = create.isPending || update.isPending || remove.isPending;
  const grades = data?.grades ?? [];

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const code = String(formData.get("code") ?? "").trim();
    const name = String(formData.get("name") ?? "").trim();
    if (!code || !name) return;
    create.mutate({ code, name });
    e.currentTarget.reset();
  };

  const handleRename = (grade: AdminGrade) => (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const name = String(new FormData(e.currentTarget).get("name") ?? "").trim();
    if (!name || name === grade.name || mutating) return;
    update.mutate({ code: grade.code, body: { name } });
  };

  const toggleTab = (grade: AdminGrade, tabKey: string) => {
    if (mutating) return;
    const tabs = grade.tabs.includes(tabKey)
      ? grade.tabs.filter((t) => t !== tabKey)
      : [...grade.tabs, tabKey];
    update.mutate({ code: grade.code, body: { tabs } });
  };

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight">등급 관리</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          등급(역할)별로 상단 탭 노출을 구성 · 회원 등급 부여/회수는 회원 관리에서
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 max-w-md">
        <Kpi label="등급 종류" value={String(grades.length)} />
        <Kpi
          label="등급 보유 회원 (합산)"
          value={grades.reduce((acc, g) => acc + g.member_count, 0).toLocaleString()}
        />
      </div>

      {/* 등급 추가 — 새 등급은 탭 전부 노출로 시작하고 아래 매트릭스에서 조정 */}
      <form
        onSubmit={handleCreate}
        className="flex flex-wrap items-center gap-2 rounded-2xl bg-surface border border-border p-4"
      >
        <Input
          name="code"
          placeholder="코드 (예: premium)"
          pattern="[a-z][a-z0-9_\-]{0,49}"
          title="소문자로 시작하는 영문·숫자·-·_ 조합"
          required
          className="px-3.5 h-10 rounded-full bg-background border border-border text-sm outline-none font-mono flex-1 min-w-36"
        />
        <Input
          name="name"
          placeholder="이름 (예: 프리미엄)"
          required
          maxLength={100}
          className="px-3.5 h-10 rounded-full bg-background border border-border text-sm outline-none flex-1 min-w-36"
        />
        <Button
          type="submit"
          disabled={mutating}
          
        >
          <Plus size={15} /> 등급 추가
        </Button>
      </form>

      {/* 등급 × 탭 매트릭스 */}
      <section className="rounded-2xl bg-surface border border-border overflow-hidden">
        {isPending && <BlockSkeleton rows={4} />}
        {isError && <Empty msg="등급 목록을 불러오지 못했습니다." />}
        {!isPending && !isError && grades.length === 0 && <Empty msg="등록된 등급이 없습니다." />}
        {grades.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[640px]">
              <thead>
                <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                  <th className="font-medium px-5 py-2.5">등급</th>
                  <th className="font-medium px-3 py-2.5 text-center">회원</th>
                  {TAB_KEYS.map((key) => (
                    <th key={key} className="font-medium px-3 py-2.5 text-center">
                      {TAB_LABELS[key]}
                    </th>
                  ))}
                  <th className="font-medium px-5 py-2.5 text-right">관리</th>
                </tr>
              </thead>
              <tbody>
                {grades.map((g) => {
                  const isAdmin = g.code === "admin"; // 삭제·개명 보호 (탭 변경은 허용)
                  return (
                    <tr key={g.code} className="border-b border-border last:border-0 hover:bg-background/40">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <span className="grid place-items-center w-8 h-8 rounded-xl bg-brand/10 text-brand shrink-0">
                            <Layers size={15} strokeWidth={1.9} />
                          </span>
                          <div className="min-w-0">
                            <form onSubmit={handleRename(g)}>
                              <Input
                                name="name"
                                key={`${g.code}-${g.name}`}
                                defaultValue={g.name}
                                disabled={isAdmin || mutating}
                                maxLength={100}
                                title={isAdmin ? "admin 역할은 이름을 변경할 수 없습니다" : "이름 수정 후 Enter"}
                                className="font-medium bg-transparent outline-none rounded-md px-1 -mx-1 focus:bg-background border border-transparent focus:border-border w-28 disabled:opacity-100"
                              />
                            </form>
                            <p className="text-xs text-foreground-muted font-mono">{g.code}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-center text-foreground-muted tabular-nums">
                        {g.member_count.toLocaleString()}
                      </td>
                      {TAB_KEYS.map((key) => (
                        <td key={key} className="px-3 py-3 text-center">
                          <input
                            type="checkbox"
                            checked={g.tabs.includes(key)}
                            disabled={mutating}
                            onChange={() => toggleTab(g, key)}
                            aria-label={`${g.name} — ${TAB_LABELS[key]} 노출`}
                            className="w-4 h-4 accent-[var(--brand,#e0493f)] cursor-pointer disabled:cursor-default"
                          />
                        </td>
                      ))}
                      <td className="px-5 py-3">
                        <div className="flex justify-end">
                          <button
                            type="button"
                            title={isAdmin ? "admin 역할은 삭제할 수 없습니다" : "등급 삭제"}
                            aria-label="등급 삭제"
                            disabled={isAdmin || mutating}
                            onClick={() => setUi({ dialog: g })}
                            className="grid place-items-center w-8 h-8 rounded-full border border-border text-red-500 hover:bg-red-50 hover:text-red-700 transition-colors disabled:opacity-30 disabled:pointer-events-none"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="text-xs text-foreground-muted leading-relaxed">
        탭 체크를 바꾸면 즉시 저장됩니다. 유저에게는 보유 등급들의 탭 합집합이 노출되고,
        비로그인 사용자는 기본(basic) 등급 구성을 따릅니다. 탭 숨김은 화면 게이팅이며 변경
        이력은 감사 로그에 기록됩니다.
      </p>

      {ui.dialog && (
        <ConfirmDialog
          title="등급 삭제"
          message={`대상: ${ui.dialog.name} (${ui.dialog.code})\n\n이 등급을 보유한 회원 ${ui.dialog.member_count}명에게서 등급이 함께 회수됩니다.\n되돌릴 수 없습니다.`}
          confirmLabel="삭제"
          danger
          withReason={false}
          onClose={() => setUi({ dialog: null })}
          onConfirm={() => {
            remove.mutate(ui.dialog!.code);
            setUi({ dialog: null });
          }}
        />
      )}
    </div>
  );
}
