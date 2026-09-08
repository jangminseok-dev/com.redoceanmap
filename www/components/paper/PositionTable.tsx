import type { PaperPosition } from "@/lib/types";
import { fmtKrw, fmtPct, fmtPrice } from "./format";

export default function PositionTable({ positions }: { positions: PaperPosition[] }) {
  if (positions.length === 0) return <p className="text-sm text-foreground-muted">열린 포지션이 없습니다.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-foreground-muted border-b border-border">
            <th className="py-2 pr-2 font-medium">종목</th>
            <th className="py-2 pr-2 font-medium">방향</th>
            <th className="py-2 pr-2 font-medium text-right">수량</th>
            <th className="py-2 pr-2 font-medium text-right">평단</th>
            <th className="py-2 pr-2 font-medium text-right">현재</th>
            <th className="py-2 pr-2 font-medium text-right">손익률</th>
            <th className="py-2 font-medium text-right">평가액</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={`${p.ticker}-${p.side}`} className="border-b border-border last:border-0">
              <td className="py-2 pr-2 font-medium">{p.ticker} <span className="text-xs text-foreground-muted">{p.name}</span></td>
              <td className="py-2 pr-2">
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs ${p.side === "LONG" ? "text-up bg-up-weak" : "text-down bg-down-weak"}`}>
                  {p.side === "LONG" ? "롱" : "숏"}
                </span>
              </td>
              <td className="py-2 pr-2 text-right tabular-nums">{p.quantity.toLocaleString("ko-KR")}</td>
              <td className="py-2 pr-2 text-right tabular-nums">{fmtPrice(p.avg_price, p.ticker)}</td>
              <td className="py-2 pr-2 text-right tabular-nums">{p.last_price == null ? "—" : fmtPrice(p.last_price, p.ticker)}</td>
              <td className={`py-2 pr-2 text-right tabular-nums ${(p.unrealized_pct ?? 0) >= 0 ? "text-up" : "text-down"}`}>{fmtPct(p.unrealized_pct)}</td>
              <td className="py-2 text-right tabular-nums">{fmtKrw(p.value_krw)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
