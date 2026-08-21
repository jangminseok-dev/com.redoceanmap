import type { Metadata } from "next";

import AppFooter from "@/components/shell/AppFooter";

export const metadata: Metadata = {
  title: "서비스 소개 — redoceanmap",
  description:
    "서울 상권 공공데이터와 주식 시세를 대화로 분석합니다. 무엇을 답하고 무엇을 답하지 못하는지, 실측 수치로 밝힙니다.",
};

/**
 * 서비스 소개 — 제품 목소리로 쓴다. 이력·경력을 나열하지 않는다.
 *
 * 연락처는 9절에만 둔다(사용자 결정, 2026-08-21). 처리방침 8항·약관 5항과 **같은 주소**이므로
 * 바꿀 때 세 곳을 함께 고친다 — 한 곳만 고치면 탈퇴 요청이 죽은 주소로 간다.
 * 푸터에는 넣지 않는다(모든 문서 페이지에 반복 노출될 자리다).
 *
 * **한계를 먼저 놓는 순서가 이 페이지의 결정이다.** 이 서비스는 판정 근거를 백테스트로
 * 검증하고 미달하면 기각하는 방식으로 만들어졌다(펀더멘털 축은 실제로 기각됐다).
 * 그 태도가 드러나려면 잘하는 것보다 못하는 것이 위에 있어야 한다.
 *
 * **수치는 전부 실측이며 근거 없이 고치지 않는다.** 출처:
 * - 대화 채점: apps/chat/tests/eval/baseline.json — **관측 최소값(바닥)**이지 최고 기록이 아니다
 *   (EVAL.md §baseline은 최고 기록이 아니라 바닥이다). 페이지에도 그렇게 적는다.
 * - 유해 분류기: apps/mail/_docs/CLAUDE.md — KcELECTRA-base + Unsmile, 검증 macro-F1 0.707
 * - 판정 적중률: forecast_snapshots 집계 (2026-08-21 실측). 표본이 자체 기준(n≥100)에
 *   미달한 상태다 — 조건 없이 단독 인용하지 않는다.
 * - 데이터 규모: 각 테이블 count (2026-08-21 실측)
 */

const MEASURED_ON = "2026년 8월 21일";

const CONTACT_EMAIL = "jang971121@gmail.com";

type Metric = { label: string; value: string; note?: string };
type Section = { title: string; body: string[]; metrics?: Metric[]; email?: string };

const SECTIONS: Section[] = [
  {
    title: "1. 무엇을 하는 서비스인가",
    body: [
      "서울의 상권과 국내·미국 주식을 대화로 분석합니다. 지역과 업종을 말하면 공공데이터를 근거로 상권을 추천하고, 종목을 물으면 시세 지표와 뉴스를 근거로 현재 상황을 설명합니다.",
      "숫자를 나열하는 대시보드가 아니라, 그 숫자가 무엇을 의미하는지 문장으로 답하는 것을 목표로 합니다.",
    ],
  },
  {
    title: "2. 먼저, 하지 못하는 것",
    body: [
      "서울만 다룹니다. 다른 지역은 상권 데이터를 확보하지 못했고, 비슷한 이름의 서울 상권으로 대신 답하지 않도록 코드로 차단해 두었습니다.",
      "임대료·보증금·권리금 데이터가 없습니다. 창업 비용의 큰 축이 빠져 있다는 뜻이며, 추정해서 말하지 않습니다. 상가 매매 실거래가는 자치구 단위로만 제공합니다.",
      "상권 데이터는 분기 단위이고 공표까지 1~2분기가 걸립니다. '지금 이 순간'이 아니라 '가장 최근에 확정된 분기'입니다. 그 공백은 인허가 대장(개·폐업)으로 일부만 메웁니다.",
      "상권 종합점수는 예측기가 아니라 현황 요약입니다. 워크포워드 백테스트에서 우수 등급 상권의 다음 분기 상대 유동인구가 +5.07%p로 나왔지만 개별 구성 요소의 상관은 약했습니다. 등급을 미래 보장으로 읽으면 안 됩니다.",
      "주식은 매수·매도를 권하지 않고 상승·하락 확률을 단정하지 않습니다. 방향 판정은 과거 데이터로 검증한 참고 신호일 뿐이며, 투자 판단은 본인 책임입니다.",
    ],
  },
  {
    title: "3. 다루는 데이터",
    body: [
      `아래는 ${MEASURED_ON} 기준 실제 적재량입니다. 답변에 쓰인 수치는 모두 이 출처에서 나온 값이며, 없는 수치는 만들어 쓰지 않습니다.`,
    ],
    metrics: [
      { label: "상권 팩트", value: "9종 × 20분기", note: "서울 열린데이터광장 상권분석서비스" },
      { label: "인허가 업소", value: "683,040건", note: "지방행정 인허가 대장 — 개·폐업 시점 보유" },
      { label: "상가 매매 실거래", value: "27,726건", note: "국토교통부 — 자치구 단위 평단가 산출" },
      { label: "종목 뉴스", value: "73,549건", note: "감성 라벨 70,777건 부여" },
      { label: "상권 뉴스", value: "2,077건", note: "지역별 의미 검색용" },
      { label: "시세 봉", value: "1,191,614건", note: "일봉·5분봉" },
      { label: "재무 스냅샷", value: "657건", note: "금융감독원 DART · yfinance" },
    ],
  },
  {
    title: "4. 쓰는 모델과 성능",
    body: [
      "답변을 만드는 언어 모델은 외부 API가 아니라 자체 장비에서 돌아갑니다. 질문 내용이 외부 사업자에게 전송되지 않는다는 뜻이며, 대신 쓸 수 있는 모델 크기에 제약이 생깁니다. 다음 항목(5번)은 그 제약을 검사로 메우려는 시도입니다.",
      "유해 표현 분류기는 직접 학습시켰습니다. KcELECTRA를 Unsmile 데이터셋(혐오 9종 + 정상, 멀티라벨)으로 파인튜닝했고 검증 macro-F1은 0.707입니다. 클래스 불균형이 큰 데이터라 정확도 대신 macro-F1으로 재며, 소수 카테고리를 놓치면 바로 값이 떨어집니다.",
    ],
    metrics: [
      { label: "답변 생성", value: "EXAONE 3.5 7.8B", note: "자체 장비 추론 · 의도 분류부터 최종 서술까지 단일 모델" },
      { label: "의미 검색 임베딩", value: "bge-m3 (1024차원)", note: "뉴스 근거 검색 · pgvector 코사인 유사도" },
      { label: "유해 표현 분류", value: "KcELECTRA + Unsmile 파인튜닝", note: "멀티라벨 10종 · 판정 임계값 0.5" },
      { label: "└ 검증 macro-F1", value: "0.707" },
      { label: "뉴스 감성 라벨", value: "70,777건 부여", note: "수집 뉴스에 호재·악재 방향 태깅" },
    ],
  },
  {
    title: "5. 답변 품질을 어떻게 지키는가",
    body: [
      "언어 모델은 그럴듯한 문장을 만드는 데 능하고 사실을 지키는 데는 약합니다. 그래서 모델을 믿는 대신 검사합니다.",
      "미리 만들어 둔 질문 120문항을 실제 모델에 통과시킨 뒤, 규칙으로 채점합니다. 채점에 언어 모델을 쓰지 않습니다 — 답을 만든 모델이 자기 답을 심판하면 순환이 되기 때문에, 모든 지표를 규칙으로 계산해 같은 기록은 언제 채점해도 같은 결과가 나오게 했습니다.",
      "아래는 자랑할 최고 기록이 아니라 회귀 검사의 기준선입니다. 같은 질문도 실행할 때마다 답이 조금씩 달라지므로 여러 번 돌려 본 값 중 가장 낮은 쪽을 기준선으로 박아 둡니다. 여기서 더 떨어지면 검증이 실패합니다.",
    ],
    metrics: [
      { label: "질문 의도 분류 정확도", value: "≥ 99%", note: "상권 / 종목 / 시장동향 / 일반 4분류" },
      { label: "종목 질의 추출 정확도", value: "≥ 93%" },
      { label: "지역 적중률", value: "≥ 95%", note: "지역을 지정한 질문에서 그 지역을 추천했는가" },
      { label: "이전 대화 승계율", value: "100%", note: "직전에 추천한 상권을 이어받아 답하는가" },
      { label: "위험 요인 언급률", value: "100%", note: "추천 이유마다 '유의할 점'을 붙였는가" },
      { label: "서울 외 지역 차단", value: "100%", note: "타협 없는 절대 규칙 — 1건이라도 뚫리면 실패" },
      { label: "환각 숫자", value: "120문항 중 4건 이하", note: "제공되지 않은 숫자를 답변에 쓴 경우" },
      { label: "코드 보정 발동률", value: "43.6%", note: "모델 답을 규칙이 바로잡은 비율 — 가드가 없었으면 틀렸을 비율" },
    ],
  },
  {
    title: "6. 주식 방향 판정은 얼마나 맞았나",
    body: [
      "판정을 내린 시점의 근거를 그대로 저장해 두고, 기간이 지나면 실제 주가와 대조해 채점합니다. 아래는 채점이 끝난 건만 집계한 결과입니다.",
      "다만 이 수치를 '적중률 67%'라고 단정하지 않습니다. 신뢰구간이 55.9%~76.6%로 넓고, 표본 76건은 저희가 스스로 정한 기준(100건)에 미치지 못합니다. 기준을 넘기 전까지는 확률을 화면에 제시하지 않으며, 이 페이지에서도 조건 없이 인용하지 않습니다.",
      "'유지' 판정 2,888건은 방향을 말하지 않으므로 채점 대상이 아닙니다.",
    ],
    metrics: [
      { label: "'상승' 판정 채점 완료", value: "76건", note: "80개 종목 · 2026-07-29 ~ 08-21" },
      { label: "그중 적중", value: "51건 (67.1%)" },
      { label: "95% 신뢰구간", value: "55.9% ~ 76.6%", note: "표본이 작아 폭이 넓습니다" },
      { label: "같은 기간 기준선", value: "53.6%", note: "판정 없이 올랐을 비율 — 이 값을 넘어야 의미가 있습니다" },
      { label: "자체 판정 기준", value: "표본 100건 이상", note: "미달 — 현재 확률 제시 보류 중" },
    ],
  },
  {
    title: "7. 어떻게 만들었는가",
    body: [
      "1인 개발이며 2026년 5월에 시작했습니다.",
      "판정에 새 근거를 넣을 때는 먼저 과거 데이터로 검증하고, 기준에 미달하면 넣지 않습니다. 재무 지표를 방향 판정에 넣으려던 시도는 검증에서 기준을 넘지 못해 실제로 기각했고, 지금은 참고 서술로만 쓰입니다.",
    ],
  },
  {
    title: "8. 앞으로",
    body: [
      "정해진 출시일은 없습니다. 아래는 우선순위이며, 검증을 통과하지 못한 항목은 넣지 않고 기각합니다.",
      "① 판정 표본 쌓기 — 100건 기준을 넘으면 방향 판정의 신뢰구간이 좁아집니다. 그전까지 확률 제시는 보류합니다.",
      "② 근거 검색 품질 — 지금은 뉴스 제목만으로 근거를 찾습니다. 본문 단위 검색과 키워드·의미 혼합 검색을 붙이고, 개선 여부를 검색 정확도 지표로 측정합니다.",
      "③ 관심 목록 개인화 — 찜해 둔 종목·상권의 현재 상태를 한 화면에 모읍니다.",
      "④ 알림 — 관심 종목에 신호가 생기면 메일로 알립니다.",
      "⑤ 데이터 공백 메우기 — 임대료(별도 기관 승인 필요)와 지하철 승하차 같은 고빈도 지표를 검토 중입니다.",
    ],
  },
  {
    title: "9. 문의",
    body: [
      "서비스 문의, 데이터 오류 제보, 개인정보 관련 요청과 회원 탈퇴를 아래 주소로 받습니다.",
      "답변이 틀렸거나 수치가 이상하다고 느끼셨다면 어떤 질문이었는지 함께 알려주세요. 골든셋에 추가해 회귀 검사로 고정합니다.",
    ],
    email: CONTACT_EMAIL,
  },
];

function MetricList({ metrics }: { metrics: Metric[] }) {
  return (
    <dl className="mt-4 divide-y divide-border border-y border-border">
      {metrics.map((m) => (
        <div key={m.label} className="py-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <dt className="text-sm text-foreground-muted min-w-0 flex-1">{m.label}</dt>
          <dd className="text-sm font-semibold tabular-nums text-foreground">{m.value}</dd>
          {m.note && <p className="w-full text-xs text-foreground-muted">{m.note}</p>}
        </div>
      ))}
    </dl>
  );
}

export default function AboutPage() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-bold">redoceanmap 소개</h1>
      <p className="mt-2 text-sm text-foreground-muted">
        서울 상권과 주식을 대화로 분석합니다. 무엇을 답하지 못하는지 먼저 밝히고, 성능은 실측
        수치로 적습니다. 별도 표기가 없으면 {MEASURED_ON} 기준입니다.
      </p>
      {SECTIONS.map((s) => (
        <section key={s.title} className="mt-8">
          <h2 className="font-semibold">{s.title}</h2>
          {s.body.map((p, i) => (
            <p key={i} className="mt-2 text-sm leading-relaxed text-foreground-muted">
              {p}
            </p>
          ))}
          {s.metrics && <MetricList metrics={s.metrics} />}
          {s.email && (
            <a
              href={`mailto:${s.email}`}
              className="mt-3 inline-block text-sm font-medium text-brand hover:underline"
            >
              {s.email}
            </a>
          )}
        </section>
      ))}
      <AppFooter />
    </main>
  );
}
