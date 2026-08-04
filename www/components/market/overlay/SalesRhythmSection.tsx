import type { AreaDetail } from "@/lib/types";
import { formatMoney } from "./format";

const DAY_LABELS: [string, string][] = [
  ["mon", "월"], ["tue", "화"], ["wed", "수"], ["thu", "목"],
  ["fri", "금"], ["sat", "토"], ["sun", "일"],
];
const TIME_LABELS: [string, string][] = [
  ["t00_06", "0-6"], ["t06_11", "6-11"], ["t11_14", "11-14"],
  ["t14_17", "14-17"], ["t17_21", "17-21"], ["t21_24", "21-24"],
];

// 값 비례 배경 농도의 1행 히트스트립 — 요일·시간대는 각각 실측(교차 데이터 없음)
// counts를 주면 툴팁에 객단가(금액÷건수)를 함께 낸다 — 칸 자체는 매출 비중 그대로다.
function HeatStrip({
  entries,
  values,
  counts,
}: {
  entries: [string, string][];
  values: Record<string, number>;
  counts?: Record<string, number> | null;
}) {
  const total = entries.reduce((sum, [key]) => sum + (values[key] ?? 0), 0);
  const max = Math.max(...entries.map(([key]) => values[key] ?? 0));
  if (total <= 0 || max <= 0) return null;
  return (
    <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${entries.length}, 1fr)` }}>
      {entries.map(([key, label]) => {
        const v = values[key] ?? 0;
        const share = Math.round((v / total) * 100);
        const intensity = 0.08 + (v / max) * 0.72;
        const per = counts ? ticket(v, counts[key] ?? 0) : null;
        return (
          <div
            key={key}
            className="rounded-md py-1.5 text-center"
            style={{ backgroundColor: `rgba(153, 27, 27, ${intensity})` }}
            title={`${label}: ${formatMoney(v)} (${share}%)${per ? ` · 객단가 ${per}` : ""}`}
          >
            <p className={`text-xs leading-tight ${intensity > 0.45 ? "text-white/80" : "text-foreground-muted"}`}>
              {label}
            </p>
            <p className={`text-xs font-semibold leading-tight ${intensity > 0.45 ? "text-white" : "text-foreground"}`}>
              {share}%
            </p>
          </div>
        );
      })}
    </div>
  );
}

// 객단가 = 금액 ÷ 건수. 건수가 0이면 만들지 않는다.
function ticket(amount: number, count: number): string | null {
  if (!count) return null;
  const per = amount / count;
  return per >= 10000 ? `${(per / 10000).toFixed(1)}만원` : `${Math.round(per).toLocaleString()}원`;
}

export default function SalesRhythmSection({
  salesMix,
  floating,
}: {
  salesMix: NonNullable<AreaDetail["salesMix"]>;
  floating: AreaDetail["floating"];
}) {
  const weekTotal = salesMix.weekdayAmount + salesMix.weekendAmount;
  const weekendPct = weekTotal > 0 ? Math.round((salesMix.weekendAmount / weekTotal) * 100) : null;
  const trafficTotal = floating ? floating.weekdayPop + floating.weekendPop : 0;
  const trafficWeekendPct =
    trafficTotal > 0 ? Math.round((floating!.weekendPop / trafficTotal) * 100) : null;
  const weekdayTicket = ticket(salesMix.weekdayAmount, salesMix.weekdayCount);
  const weekendTicket = ticket(salesMix.weekendAmount, salesMix.weekendCount);

  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="text-xs text-foreground-muted mb-1.5">요일별 매출 비중</p>
        <HeatStrip entries={DAY_LABELS} values={salesMix.byDay} counts={salesMix.countByDay} />
      </div>
      <div>
        <p className="text-xs text-foreground-muted mb-1.5">시간대별 매출 비중</p>
        <HeatStrip entries={TIME_LABELS} values={salesMix.byTime} counts={salesMix.countByTime} />
      </div>
      {weekendPct !== null && (
        <div>
          <p className="text-xs text-foreground-muted mb-1">
            주중 {100 - weekendPct}% · 주말 {weekendPct}%
          </p>
          <div className="flex h-2 rounded-full overflow-hidden bg-border">
            <div className="bg-brand/80" style={{ width: `${100 - weekendPct}%` }} />
            <div className="bg-brand/40" style={{ width: `${weekendPct}%` }} />
          </div>
          {/* 통행을 같은 축으로 겹쳐 보여준다 — 두 바의 차이가 곧 '구매 전환' 이야기다 */}
          {trafficWeekendPct !== null && (
            <>
              <p className="text-xs text-foreground-muted mt-2 mb-1">
                통행 주중 {100 - trafficWeekendPct}% · 주말 {trafficWeekendPct}%
              </p>
              <div className="flex h-2 rounded-full overflow-hidden bg-border">
                <div className="bg-foreground/40" style={{ width: `${100 - trafficWeekendPct}%` }} />
                <div className="bg-foreground/20" style={{ width: `${trafficWeekendPct}%` }} />
              </div>
            </>
          )}
          {(weekdayTicket || weekendTicket) && (
            <p className="text-xs text-foreground-muted mt-2">
              객단가 — 주중 {weekdayTicket ?? "—"} · 주말 {weekendTicket ?? "—"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
