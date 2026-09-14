import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import InsightList from "@/components/common/InsightList";
import { Button } from "@/components/ui/button";
import { fetchAreaPublic } from "@/lib/publicApi.server";
import type { AreaPublic } from "@/lib/types";

/**
 * 공개 상권 상세(A-4) — 비로그인·검색 유입용 SEO 앵커. `(seoul)` 그룹 밖이라 TabGuard가 걸리지
 * 않고, 서버 컴포넌트가 백엔드 공개 경로를 직접 읽어 HTML로 내보낸다(ISR 하루).
 * 데이터 표면이 본진, 챗은 그 위의 코파일럿(SITE_SPLIT §확정 방향) — 챗 도크는 LLM 교체 뒤.
 */

type Params = { trdarCode: string };

const won = (v: number | null) => {
  if (v == null) return "—";
  if (v >= 100_000_000) return `${(v / 100_000_000).toFixed(1)}억원`;
  return `${Math.round(v / 10_000).toLocaleString()}만원`;
};
const pct = (v: number | null) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);
const quarterLabel = (yq: number | null) =>
  yq ? `${String(yq).slice(0, 4)}년 ${String(yq).slice(4)}분기` : "기준 분기 없음";

// AreaScoreCard와 같은 등급 표기 — 방향 토큰 2개(up/down)만 쓴다(DESIGN.md §7)
const GRADE_STYLE: Record<string, string> = {
  우수: "text-up bg-up-weak border-up/20",
  양호: "text-up bg-up-weak/50 border-up/10",
  보통: "text-foreground bg-surface border-border",
  주의: "text-down bg-down-weak/50 border-down/10",
  위험: "text-down bg-down-weak border-down/20",
};

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { trdarCode } = await params;
  const area = await fetchAreaPublic(trdarCode);
  if (!area) return { title: "상권을 찾지 못했습니다 | redoceanmap" };
  const title = `${area.trdarName} 상권 분석 — ${area.districtName} | redoceanmap`;
  const grade = area.score ? `종합 ${area.score.grade}(${Math.round(area.score.total)}점)` : "종합점수 산출 전";
  const sales = area.salesPerStore != null && area.serviceName
    ? ` · ${area.serviceName} 점포당 월매출 ${won(area.salesPerStore)}`
    : "";
  const description = `${area.districtName} ${area.trdarName}(${area.divisionName}) — ${grade}${sales}. 서울시 공공데이터로 본 상권 요약과 해석.`;
  return {
    title,
    description,
    alternates: { canonical: `/areas/${area.trdarCode}` },
    openGraph: { title, description, type: "article", locale: "ko_KR" },
    twitter: { card: "summary", title, description },
  };
}

export default async function AreaPublicPage({ params }: { params: Promise<Params> }) {
  const { trdarCode } = await params;
  const area = await fetchAreaPublic(trdarCode);
  if (!area) notFound();

  return (
    <article className="mx-auto w-full max-w-2xl px-4 py-6 flex flex-col gap-4">
      <header>
        <p className="text-xs text-foreground-muted">
          {area.districtName} · {area.divisionName} · {quarterLabel(area.yearQuarter)} 기준
        </p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">{area.trdarName}</h1>
      </header>

      <ScoreBlock score={area.score} />
      <MetricsBlock area={area} />

      {area.insights.length > 0 && (
        <section className="bg-surface border border-border rounded-xl p-3.5">
          <h2 className="text-sm font-semibold mb-2">이 상권은 어떤 곳인가</h2>
          <InsightList insights={area.insights} />
        </section>
      )}

      <section className="flex flex-col gap-2">
        <Button asChild size="lg" className="w-full">
          <Link href={`/market?trdar=${area.trdarCode}`}>지도에서 자세히 보기</Link>
        </Button>
        <p className="text-xs text-foreground-muted">
          로그인하면 매출 요일·시간대 분해, 인구 구조, 업종별 순위, 최근 개·폐업 업소를 볼 수 있습니다.
        </p>
      </section>

      {/* 자료 패널과 같은 한계 고지(I-9) — 공개 페이지에서도 뺄 수 없다 */}
      <footer className="text-xs text-foreground-muted leading-relaxed border-t border-border pt-3">
        서울시 상권분석서비스 추정 집계입니다(실결제·카드 표본이 아님). 분기 데이터라 1~2분기 시차가
        있고, 임대료·권리금은 제공되지 않습니다. 창업비용은 공정위 가맹 정보공개서 기준이며 개인
        창업은 표에 없습니다.
      </footer>
    </article>
  );
}

function ScoreBlock({ score }: { score: AreaPublic["score"] }) {
  if (!score) return null;
  const gradeStyle = GRADE_STYLE[score.grade] ?? GRADE_STYLE["보통"];
  return (
    <section className="bg-surface border border-border rounded-xl p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="text-2xl font-bold tabular-nums">
            {score.total}
            <span className="text-sm font-medium text-foreground-muted ml-0.5">점</span>
          </div>
          <p className="text-xs text-foreground-muted mt-0.5">서울 평균 대비 종합점수 · 50점 = 평균 수준</p>
        </div>
        <span className={`inline-flex px-2.5 py-1 rounded-full border text-xs font-semibold ${gradeStyle}`}>
          {score.grade}
        </span>
      </div>
      <ul className="mt-3 flex flex-col gap-1.5">
        {score.components.map((c) => (
          <li key={c.key} className="flex items-center justify-between text-xs">
            <span className="text-foreground-muted">{c.name}</span>
            <span
              title="50점 = 서울 평균"
              className={`font-semibold tabular-nums ${c.score >= 55 ? "text-up" : c.score <= 45 ? "text-down" : ""}`}
            >
              {c.score}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function MetricsBlock({ area }: { area: AreaPublic }) {
  const cells: { label: string; value: string }[] = [
    { label: `${area.serviceName ?? "기준 업종"} 점포당 월매출`, value: won(area.salesPerStore) },
    { label: "매출 전분기 대비", value: pct(area.salesQoq) },
    { label: "폐업률", value: area.closureRate == null ? "—" : `${area.closureRate.toFixed(1)}%` },
    { label: "주간 통행 인구", value: area.floatingPop == null ? "—" : `${Math.round(area.floatingPop / 10_000).toLocaleString()}만명` },
  ];
  return (
    <section className="grid grid-cols-2 gap-2">
      {cells.map((c) => (
        <div key={c.label} className="bg-surface border border-border rounded-xl p-3">
          <p className="text-xs text-foreground-muted">{c.label}</p>
          <p className="mt-1 text-lg font-bold tabular-nums">{c.value}</p>
        </div>
      ))}
      {area.storeCount != null && (
        <p className="col-span-2 text-xs text-foreground-muted">
          {area.serviceName} 점포 {area.storeCount}개 기준 · 점포당 월매출은 상권 합계 ÷ 점포 수
        </p>
      )}
    </section>
  );
}
