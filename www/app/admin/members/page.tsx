"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Ban, Coins, Download, KeyRound, LogOut, RotateCcw, Search, ShieldCheck, UserX } from "lucide-react";
import {
  downloadCsv,
  fetchAdminMembers,
  fetchAdminRoles,
  fetchAllAdminMembers,
  grantAdminRole,
  reinstateMember,
  revokeAdminRole,
  revokeMemberSessions,
  suspendMember,
  withdrawMember,
  formatDate,
  type AdminMember,
} from "@/lib/adminApi";
import BlockSkeleton from "@/components/admin/BlockSkeleton";
import ConfirmDialog from "@/components/admin/ConfirmDialog";
import Empty from "@/components/admin/Empty";
import Kpi from "@/components/admin/Kpi";
import { showToast } from "@/components/admin/toast";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const PAGE_SIZE = 20;

// permission 코드 → 설명 (백엔드 alembic 시드와 동일한 7종)
const PERMISSION_DESC: Record<string, string> = {
  "dashboard:read": "대시보드 KPI 조회",
  "areas:read": "상권 목록 조회",
  "members:read": "회원·역할 구성 조회",
  "members:write": "회원 역할 부여/회수·제재",
  "recommendations:read": "추천 기록 조회",
  "datasources:read": "데이터셋 현황 조회",
  "audit:read": "감사 로그 조회",
};

type DialogAction = "suspend" | "revoke-sessions" | "withdraw";

const DIALOG_META: Record<
  DialogAction,
  { title: string; message: string; confirmLabel: string; danger: boolean; withReason: boolean }
> = {
  suspend: {
    title: "계정 정지",
    message:
      "정지하면 즉시 모든 API 접근이 차단되고 강제 로그아웃됩니다.\n해제하면 재로그인 후 이전 상태 그대로 복구됩니다.",
    confirmLabel: "정지",
    danger: false,
    withReason: true,
  },
  "revoke-sessions": {
    title: "세션 강제 만료",
    message: "이 회원의 모든 로그인 세션(리프레시 토큰)을 폐기합니다.\n회원은 다시 로그인해야 합니다.",
    confirmLabel: "세션 만료",
    danger: false,
    withReason: false,
  },
  withdraw: {
    title: "탈퇴 처리 (비가역)",
    message:
      "이메일·이름이 익명화되고 로그인 수단이 무효화됩니다.\n되돌릴 수 없습니다. 약관 제8조의 이메일 접수 요청 처리에만 사용하세요.",
    confirmLabel: "탈퇴 처리",
    danger: true,
    withReason: false,
  },
};

export default function MembersPage() {
  // REACT_RULES 패턴 B: 질의·모달 상태를 단일 객체 useState로 (사유 입력은 모달의 FormData — 패턴 A)
  const [ui, setUi] = useState<{
    search: string;
    page: number;
    dialog: { action: DialogAction; member: AdminMember } | null;
  }>({ search: "", page: 0, dialog: null });
  const queryClient = useQueryClient();

  const { data, isPending, isError } = useQuery({
    queryKey: ["admin-members", ui.search, ui.page],
    queryFn: () => fetchAdminMembers(ui.search, PAGE_SIZE, ui.page * PAGE_SIZE),
  });
  const { data: rolesData } = useQuery({
    queryKey: ["admin-roles"],
    queryFn: fetchAdminRoles,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin-members"] });
  const grant = useMutation({
    mutationFn: ({ userId, roleCode }: { userId: number; roleCode: string }) =>
      grantAdminRole(userId, roleCode),
    onSuccess: (m) => {
      invalidate();
      showToast(`${m.name}에게 역할을 부여했습니다.`);
    },
    onError: (e) => showToast(e instanceof Error ? e.message : "역할 부여에 실패했습니다.", "error"),
  });
  const revoke = useMutation({
    mutationFn: ({ userId, roleCode }: { userId: number; roleCode: string }) =>
      revokeAdminRole(userId, roleCode),
    onSuccess: (m) => {
      invalidate();
      showToast(`${m.name}의 역할을 회수했습니다.`);
    },
    onError: (e) => showToast(e instanceof Error ? e.message : "역할 회수에 실패했습니다.", "error"),
  });
  const moderate = useMutation({
    mutationFn: async ({
      action,
      userId,
      reason,
    }: {
      action: DialogAction | "reinstate";
      userId: number;
      reason: string;
    }) => {
      if (action === "suspend") return { kind: "정지", result: await suspendMember(userId, reason) };
      if (action === "reinstate") return { kind: "정지 해제", result: await reinstateMember(userId) };
      if (action === "withdraw") return { kind: "탈퇴 처리", result: await withdrawMember(userId) };
      const { revoked } = await revokeMemberSessions(userId);
      return { kind: `세션 만료(${revoked}건 폐기)`, result: null };
    },
    onSuccess: ({ kind }) => {
      invalidate();
      showToast(`${kind}를 완료했습니다.`);
    },
    onError: (e) => showToast(e instanceof Error ? e.message : "처리에 실패했습니다.", "error"),
  });

  const handleSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    setUi((prev) => ({ ...prev, search: String(formData.get("q") ?? "").trim(), page: 0 }));
  };

  const exportCsv = async () => {
    try {
      const all = await fetchAllAdminMembers(ui.search);
      downloadCsv(
        "admin-members.csv",
        ["ID", "이름", "이메일", "가입일", "상태", "마케팅 동의", "역할"],
        all.map((m) => [
          m.id,
          m.name,
          m.email ?? "",
          formatDate(m.joined_at),
          m.deleted_at ? "탈퇴" : m.suspended_at ? "정지" : "활성",
          m.marketing_agreed ? "동의" : "미동의",
          m.roles.join("|"),
        ]),
      );
      showToast(`회원 ${all.length}명을 CSV로 내보냈습니다.`);
    } catch {
      showToast("CSV 내보내기에 실패했습니다.", "error");
    }
  };

  const roles = rolesData?.roles ?? [];
  const total = data?.total ?? 0;
  const lastPage = Math.max(Math.ceil(total / PAGE_SIZE) - 1, 0);
  const mutating = grant.isPending || revoke.isPending || moderate.isPending;

  // 마지막 페이지의 마지막 회원이 목록에서 빠지면(탈퇴로 검색 조건 이탈 등) 빈 페이지에
  // 고립되므로 유효 범위로 되돌린다.
  useEffect(() => {
    if (!isPending && data && data.items.length === 0 && ui.page > 0) {
      setUi((prev) => ({ ...prev, page: Math.min(prev.page - 1, lastPage) }));
    }
  }, [isPending, data, ui.page, lastPage]);

  const toggleRole = (member: AdminMember, roleCode: string) => {
    if (mutating) return;
    const has = member.roles.includes(roleCode);
    (has ? revoke : grant).mutate({ userId: member.id, roleCode });
  };

  // 해제는 모달 없이 즉시 실행 — 재렌더 전 연타로 중복 요청되지 않게 mutate 직전에도 잠근다.
  const handleReinstate = (userId: number) => {
    if (moderate.isPending) return;
    moderate.mutate({ action: "reinstate", userId, reason: "" });
  };

  const openDialog = (action: DialogAction, member: AdminMember) =>
    setUi((prev) => ({ ...prev, dialog: { action, member } }));
  const closeDialog = () => setUi((prev) => ({ ...prev, dialog: null }));

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">회원 관리</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            회원 조회 · 역할(RBAC) 부여 · 정지/탈퇴 처리
          </p>
        </div>
        <Button
          type="button"
          onClick={exportCsv}
          disabled={total === 0}
          variant="outline"
        >
          <Download size={15} /> CSV 내보내기
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 max-w-md">
        <Kpi label={ui.search ? "전체 회원 (검색 결과)" : "전체 회원"} value={total.toLocaleString()} />
        <Kpi label="운영 역할 종류" value={String(roles.length)} />
      </div>

      <form onSubmit={handleSearch}>
        <label className="flex items-center gap-2 px-3.5 h-10 rounded-full bg-surface border border-border text-sm">
          <Search size={16} className="text-foreground-muted shrink-0" />
          <Input
            name="q"
            defaultValue={ui.search}
            placeholder="이름 또는 이메일 검색 (Enter)"
            className="bg-transparent outline-none flex-1 placeholder:text-foreground-muted"
          />
        </label>
      </form>

      <section className="rounded-2xl bg-surface border border-border overflow-hidden">
        {isPending && <BlockSkeleton rows={5} />}
        {isError && <Empty msg="회원 목록을 불러오지 못했습니다." />}
        {!isPending && !isError && (data?.items.length ?? 0) === 0 && (
          <Empty msg="조건에 맞는 회원이 없습니다." />
        )}
        {(data?.items.length ?? 0) > 0 && (
          <>
            <div className="hidden sm:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-foreground-muted border-b border-border bg-background/60">
                    <th className="font-medium px-5 py-2.5">회원</th>
                    <th className="font-medium px-5 py-2.5">가입일</th>
                    <th className="font-medium px-5 py-2.5">상태</th>
                    <th className="font-medium px-5 py-2.5">역할</th>
                    <th className="font-medium px-5 py-2.5 text-right">관리</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.items.map((m) => (
                    <tr key={m.id} className="border-b border-border last:border-0 hover:bg-background/40">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <span className="grid place-items-center w-8 h-8 rounded-full bg-brand/10 text-brand text-xs font-semibold">
                            {m.name[0] ?? "?"}
                          </span>
                          <div>
                            <p className="font-medium flex items-center gap-1.5">
                              {m.name}
                              <IdChip id={m.id} />
                            </p>
                            <p className="text-xs text-foreground-muted">{m.email ?? "카카오 로그인 (이메일 없음)"}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3 text-foreground-muted tabular-nums">{formatDate(m.joined_at)}</td>
                      <td className="px-5 py-3">
                        <StatusBadge member={m} />
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex gap-1.5 flex-wrap">
                          {m.deleted_at ? (
                            <span className="text-xs text-foreground-muted">—</span>
                          ) : (
                            roles.map((r) => (
                              <RoleChip
                                key={r.code}
                                label={r.name}
                                active={m.roles.includes(r.code)}
                                disabled={mutating}
                                onClick={() => toggleRole(m, r.code)}
                              />
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <MemberActions
                          member={m}
                          disabled={mutating}
                          onSuspend={() => openDialog("suspend", m)}
                          onReinstate={() => handleReinstate(m.id)}
                          onRevokeSessions={() => openDialog("revoke-sessions", m)}
                          onWithdraw={() => openDialog("withdraw", m)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="sm:hidden divide-y divide-border">
              {data!.items.map((m) => (
                <div key={m.id} className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="grid place-items-center w-10 h-10 rounded-full bg-brand/10 text-brand text-sm font-semibold shrink-0">
                      {m.name[0] ?? "?"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium flex items-center gap-1.5">
                        {m.name}
                        <IdChip id={m.id} />
                      </p>
                      <p className="text-xs text-foreground-muted truncate">
                        {m.email ?? "카카오 로그인"} · {formatDate(m.joined_at)}
                      </p>
                    </div>
                    <StatusBadge member={m} />
                  </div>
                  {!m.deleted_at && (
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <div className="flex gap-1.5 flex-wrap">
                        {roles.map((r) => (
                          <RoleChip
                            key={r.code}
                            label={r.name}
                            active={m.roles.includes(r.code)}
                            disabled={mutating}
                            onClick={() => toggleRole(m, r.code)}
                          />
                        ))}
                      </div>
                      <MemberActions
                        member={m}
                        disabled={mutating}
                        onSuspend={() => openDialog("suspend", m)}
                        onReinstate={() => handleReinstate(m.id)}
                        onRevokeSessions={() => openDialog("revoke-sessions", m)}
                        onWithdraw={() => openDialog("withdraw", m)}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      {/* 페이지네이션 */}
      {total > PAGE_SIZE && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button
            type="button"
            disabled={ui.page === 0}
            onClick={() => setUi((prev) => ({ ...prev, page: prev.page - 1 }))}
            variant="outline"
          >
            이전
          </Button>
          <span className="text-foreground-muted tabular-nums">
            {ui.page + 1} / {lastPage + 1}
          </span>
          <Button
            type="button"
            disabled={ui.page >= lastPage}
            onClick={() => setUi((prev) => ({ ...prev, page: prev.page + 1 }))}
            variant="outline"
          >
            다음
          </Button>
        </div>
      )}

      {/* 역할·권한(RBAC) 구성 — 읽기 전용 (구 설정 페이지에서 이동) */}
      <section className="space-y-4 pt-2">
        <div>
          <h2 className="text-lg font-bold tracking-tight">역할·권한 구성</h2>
          <p className="mt-0.5 text-sm text-foreground-muted">
            읽기 전용 — 역할 부여/회수는 위 회원 목록에서, 변경 이력은 감사 로그에서 확인
          </p>
        </div>
        {roles.map((role) => (
          <div key={role.code} className="rounded-2xl bg-surface border border-border p-5">
            <div className="flex items-center gap-2.5">
              <span className="grid place-items-center w-10 h-10 rounded-xl bg-brand/10 text-brand">
                <ShieldCheck size={17} strokeWidth={1.9} />
              </span>
              <div>
                <h3 className="font-semibold">{role.name}</h3>
                <p className="text-xs text-foreground-muted font-mono">{role.code}</p>
              </div>
            </div>
            <div className="mt-4 divide-y divide-border">
              {role.permissions.length === 0 && (
                <p className="py-3 text-sm text-foreground-muted">부여된 권한이 없습니다.</p>
              )}
              {role.permissions.map((code) => (
                <div key={code} className="flex items-center gap-3 py-3">
                  <KeyRound size={14} className="text-foreground-muted shrink-0" />
                  <span className="text-sm font-mono">{code}</span>
                  <span className="ml-auto text-xs text-foreground-muted">
                    {PERMISSION_DESC[code] ?? ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </section>

      {ui.dialog && (
        <ConfirmDialog
          {...DIALOG_META[ui.dialog.action]}
          message={`대상: ${ui.dialog.member.name} (${ui.dialog.member.email ?? "이메일 없음"})\n\n${DIALOG_META[ui.dialog.action].message}`}
          onClose={closeDialog}
          onConfirm={(reason) => {
            moderate.mutate({ action: ui.dialog!.action, userId: ui.dialog!.member.id, reason });
            closeDialog();
          }}
        />
      )}
    </div>
  );
}

function StatusBadge({ member }: { member: AdminMember }) {
  if (member.deleted_at) {
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-foreground/5 text-foreground-muted">
        탈퇴
      </span>
    );
  }
  if (member.suspended_at) {
    return (
      <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700">
        정지
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700">
      활성
    </span>
  );
}

function MemberActions({
  member,
  disabled,
  onSuspend,
  onReinstate,
  onRevokeSessions,
  onWithdraw,
}: {
  member: AdminMember;
  disabled: boolean;
  onSuspend: () => void;
  onReinstate: () => void;
  onRevokeSessions: () => void;
  onWithdraw: () => void;
}) {
  if (member.deleted_at) return <span className="block text-right text-xs text-foreground-muted">—</span>;
  return (
    <div className="flex justify-end gap-1">
      {/* 게임운영은 회원 ID로만 지갑을 찾는다 — 사람이 숫자를 옮겨 적지 않게 링크로 넘긴다. */}
      <Link
        href={`/admin/game?userId=${member.id}`}
        title="게임 지갑 열기"
        aria-label="게임 지갑 열기"
        className="grid place-items-center w-8 h-8 rounded-full border border-border text-foreground-muted transition-colors hover:bg-accent hover:text-foreground"
      >
        <Coins size={15} />
      </Link>
      {member.suspended_at ? (
        <ActionIcon title="정지 해제" onClick={onReinstate} disabled={disabled}>
          <RotateCcw size={15} />
        </ActionIcon>
      ) : (
        <ActionIcon title="계정 정지" onClick={onSuspend} disabled={disabled}>
          <Ban size={15} />
        </ActionIcon>
      )}
      <ActionIcon title="세션 강제 만료" onClick={onRevokeSessions} disabled={disabled}>
        <LogOut size={15} />
      </ActionIcon>
      <ActionIcon title="탈퇴 처리 (비가역)" onClick={onWithdraw} disabled={disabled} danger>
        <UserX size={15} />
      </ActionIcon>
    </div>
  );
}

/** 회원 ID — 게임운영 등 다른 화면이 이 숫자를 요구한다. 눌러서 복사한다. */
function IdChip({ id }: { id: number }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(String(id));
      showToast(`ID ${id}를 복사했습니다.`);
    } catch {
      showToast("복사할 수 없습니다. 숫자를 직접 옮겨 적어 주세요.", "error");
    }
  };
  return (
    <button
      type="button"
      title="ID 복사"
      onClick={copy}
      className="text-xs font-normal tabular-nums text-foreground-muted hover:text-foreground transition-colors"
    >
      #{id}
    </button>
  );
}

function ActionIcon({
  title,
  onClick,
  disabled,
  danger = false,
  children,
}: {
  title: string;
  onClick: () => void;
  disabled: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className={`grid place-items-center w-8 h-8 rounded-full border border-border transition-colors disabled:opacity-40 ${
        danger
          ? "text-red-500 hover:bg-red-50 hover:text-red-700"
          : "text-foreground-muted hover:bg-accent hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function RoleChip({
  label,
  active,
  disabled,
  onClick,
}: {
  label: string;
  active: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={active ? `${label} 역할 회수` : `${label} 역할 부여`}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors disabled:opacity-50 ${
        active
          ? "bg-brand text-white border-brand"
          : "bg-surface text-foreground-muted border-border hover:text-foreground"
      }`}
    >
      <ShieldCheck size={12} /> {label}
    </button>
  );
}
