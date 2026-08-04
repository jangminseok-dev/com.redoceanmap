import type { AreaDetail, PermitOpening } from "@/lib/types";

/**
 * 인허가 대장 기준 업소 교체 — "요즘 여기 뭐가 새로 열었나".
 *
 * 기존 상권 팩트(`store`)는 분기별 점포 **수**라 이 질문을 못 받는다. 인허가는 업소 한 곳이
 * 한 행이고 인허가일·폐업일을 그대로 들고 있어 상호까지 보여줄 수 있다.
 *
 * **영업중 수를 점포 수와 나란히 두지 않는다** — 출처(인허가 대장 vs 상권분석서비스)도
 * 집계 기준도 달라서 나란히 놓으면 사용자가 검산하려 들고, 그 검산은 반드시 어긋난다.
 */

const fmtDate = (iso: string) => {
  const [, m, d] = iso.split("-");
  return `${Number(m)}/${Number(d)}`;
};

function OpeningList({ items, empty }: { items: PermitOpening[]; empty: string }) {
  if (items.length === 0) return <p className="text-xs text-muted">{empty}</p>;
  return (
    <ul className="space-y-1">
      {items.map((o) => (
        <li key={`${o.name}-${o.happenedOn}`} className="flex items-baseline gap-2 text-xs">
          <span className="tabular-nums text-muted shrink-0">{fmtDate(o.happenedOn)}</span>
          <span className="truncate">{o.name}</span>
          {o.category && <span className="text-muted shrink-0">{o.category}</span>}
        </li>
      ))}
    </ul>
  );
}

export default function PermitChurnSection({
  churn,
}: {
  churn: NonNullable<AreaDetail["permitChurn"]>;
}) {
  const net = churn.opened - churn.closed;
  return (
    <div className="space-y-3">
      <div className="flex items-baseline gap-3 text-sm">
        <span>
          최근 {churn.months}개월 <b className="tabular-nums">{churn.opened}</b>곳 개업
        </span>
        <span className="text-muted">·</span>
        <span>
          <b className="tabular-nums">{churn.closed}</b>곳 폐업
        </span>
        <span
          className={`tabular-nums ${net > 0 ? "text-emerald-600" : net < 0 ? "text-rose-600" : "text-muted"}`}
        >
          {net > 0 ? "+" : ""}
          {net}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted">새로 연 곳</p>
          <OpeningList items={churn.recentOpenings} empty="최근 개업 없음" />
        </div>
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted">문 닫은 곳</p>
          <OpeningList items={churn.recentClosings} empty="최근 폐업 없음" />
        </div>
      </div>

      <p className="text-xs leading-relaxed text-muted">
        음식점·카페 인허가 대장(서울시) 기준이며, 상권 중심 반경으로 묶은 값입니다. 경계 근처
        업소는 빠질 수 있어 위 업종별 점포 수와는 집계 기준이 다릅니다.
      </p>
    </div>
  );
}
