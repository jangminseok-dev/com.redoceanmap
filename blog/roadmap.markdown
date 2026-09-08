---
layout: page
title: 단계별 진행 현황
nav_title: 진행 현황
permalink: /roadmap/
---

<div class="cn-grid">

<div class="cn-card cn-bg-warm cn-statement cn-wide">
  <p class="cn-label">로드맵</p>
  <h2>① 개인 투자/분석 도구 → ② 운영·품질 기반 완성 → ③ 실사용자 서비스</h2>
  <p>목표는 단계적이다.</p>
</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

## 운영 방식 — 마일스톤 · 게이트

- **마일스톤 단위**로 운영한다. 1인 개발이라 스크럼 의식(儀式) 대신, 마일스톤마다
  **검증 게이트**(테스트·실측 기준)를 먼저 정의하고 통과해야만 완료로 표기한다.
- **"구현 완료"와 "완료"를 구분한다** — 코드가 끝나도 실행·판정(E2E·사람 라벨링)이 남으면
  완료가 아니다. 아래 표의 "구현 완료 · 잔여" 표기가 그 상태다.
- 게이트 미달 실험은 **기각하고 근거를 남긴다** — 기각도 결과다.
- 마일스톤을 끝낼 때마다 리뷰 포스트(무엇을 / 왜 / 어떻게 / 아쉬운 점)를 남긴다.

</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

## 작업 영역 <span style="color:#9a9aa2;font-size:0.85rem;font-weight:400;">(1인 개발 — 역할이 아니라 영역으로 나눈다)</span>

| 영역 | 범위 | 주요 산출물 |
| --- | --- | --- |
| <span class="st st-be">백엔드</span> | FastAPI 모듈러 모놀리식 — 앱 8개(허브·스포크 7, game은 2026-09 폐기), 헥사고날 내부 구조 | API·유스케이스·인터랙터 테스트 |
| <span class="st st-fe">프론트</span> | Next.js 워크스페이스 — 지도·채팅·자료 3패널, 어드민 화면 | 주식/상권 워크스페이스, 북마크 보드 |
| <span class="st st-ml">데이터·ML</span> | 수집 배치 6종, 백테스트, 평가 하네스(생성·검색), 임베딩 | 골든셋, baseline 리포트, 채택/기각 판정 문서 |
| <span class="st st-op">운영</span> | k3s 단일 노드 배포(앱) + 도커 컴포즈(DB 계층), 백업 3계층, 로깅·모니터링, 공개 접점 | 배포 체계, 복원 리허설, 업타임 알림 |

</div>

<div class="cn-card cn-bg-plain cn-body" markdown="1">

## Phase ① — 개인 투자/분석 도구 <span class="st st-done">완료</span>

| 마일스톤 | 상태 |
| --- | --- |
| 인증 가드 전면 적용 + 리프레시 토큰 | <span class="st st-done">완료 2026-07</span> |
| 주식 피처 확장 + 백테스트 재채점 | <span class="st st-done">완료 2026-07</span> |
| 상권 시계열·스코어링 v1 (종합점수 4컴포넌트) | <span class="st st-done">완료 2026-07</span> |
| 뉴스 수집 상시화 | <span class="st st-done">완료 2026-07</span> |
| 채팅 실데이터 결합 — 지표 해석 + 뉴스 RAG + 상권 근거 주입 | <span class="st st-done">완료 2026-07</span> |
| 프론트-백엔드 정합 (스코어 카드·뉴스 근거 카드) | <span class="st st-done">완료 2026-07</span> |

</div>

<div class="cn-card cn-bg-plain cn-body" markdown="1">

## Phase ② — 운영·품질 기반 완성

| 마일스톤 | 상태 |
| --- | --- |
| 프로덕션 컴포즈 + 배포 스크립트 (컷오버 검증) | <span class="st st-done">완료 2026-08</span> |
| 앱 계층 k3s 전환 — 백엔드·인증·CronJob 5종, DB는 도커에 잔류 | <span class="st st-done">완료 2026-09</span> 24h 관찰 통과 |
| 백업 3계층 — 로컬 일간 · 오프사이트 주간 · 복원 리허설 | <span class="st st-wip">구현 완료 · 첫 실행 잔여</span> |
| RBAC + 어드민 실구현 | <span class="st st-done">완료 2026-07</span> |
| 상권 전용 DB 런타임 전환 (60만+ 행 이관) | <span class="st st-done">완료 2026-07</span> |
| GitHub Actions CI / n8n 탈피 / 문서 정합 | <span class="st st-drop">취소 (사용자 결정)</span> |

</div>

<div class="cn-card cn-bg-plain cn-body" markdown="1">

<h2 id="r-track">R 트랙 — 검색(RAG) 품질</h2>

생성 품질만 재던 평가 하네스에 **검색 품질 축**(recall@k·nDCG·MRR)을 추가하는 트랙.
라벨링은 사람이 한다 — LLM이 자기 검색을 심판하는 순환은 금지.

| 마일스톤 | 상태 |
| --- | --- |
| R1 검색 품질 계측 기반 — 골든셋·채점기·회귀 게이트 | <span class="st st-done">완료 2026-08</span> baseline 박제(nDCG@5 0.77) |
| R2 하이브리드 검색 (trigram + 벡터 RRF) | <span class="st st-drop">측정 후 기각</span> 개선폭 게이트 미달 — 현행 유지 |
| R3 청킹 전략 3종 비교 (공시 원문·표·각주) | <span class="st st-drop">측정 후 기각</span> 표 인지 청킹이 대조군 이하 — 고정 청킹 유지 |
| R4 문장 단위 출처 인용 + dangling citation 절대 규칙 | <span class="st st-done">완료 2026-08</span> |

※ R2·R3는 게이트 미달 시 **기각하고 현행 유지**한다 — 측정해서 기각한 이력도 결과다.

</div>

<div class="cn-card cn-bg-plain cn-body" markdown="1">

## Phase ③ — 실사용자 서비스

| 마일스톤 | 상태 |
| --- | --- |
| 공개 접점 — HTTPS + rate limit (무차별 로그인 차단 실측) | <span class="st st-done">완료 2026-08</span> |
| 북마크/관심종목 | <span class="st st-done">완료 2026-08</span> |
| 알림 v1 — 이메일 + 텔레그램 채널, dedupe + 회원별 수신 설정 | <span class="st st-done">완료 2026-08</span> |
| 운영 관측 — 구조화 로깅 + 업타임 모니터링 (강제 다운 → 알림 2분 28초 실측) | <span class="st st-done">완료 2026-08</span> |
| 데이터 갱신 자동화 + LLM 교체 스위치 | <span class="st st-done">완료 2026-08</span> |
| 개인화 ⓪ 투자·창업 프로파일 / ① 관심 목록 상태 보드 | <span class="st st-done">완료 2026-08</span> |
| 알림 v2 — 가격 도달(one-shot)·관심 종목 뉴스(커서 dedupe), 매시 스캔 | <span class="st st-done">완료 2026-09</span> |
| 프로덕션 페르소나 테스트 3회(85턴) → 결정론 가드 일괄 | <span class="st st-done">완료 2026-09</span> |
| game 스포크 폐기 → AI 모의투자(EXAONE 직접 판단·숏 허용·6주 리플레이) | <span class="st st-done">완료 2026-09</span> 입지 적합도는 상권으로 이관 |
| 목적별 페르소나 10명 QA(가입→목표) → 개선 22건 중 21건 배포 | <span class="st st-done">완료 2026-09</span> 잔여 1건은 답변 골격 전환 |
| 공정위 브랜드 창업비용 팩트 — 예산 질문에 업종 후보 제시 | <span class="st st-done">완료 2026-09</span> 월 1회 자동 적재 |
| 개인화 ② 선호 프로파일 | <span class="st st-wait">수요 게이트 뒤</span> |
| 매물(listing) 스포크 | <span class="st st-wait">수요 게이트 뒤</span> |

</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

## 데이터·모델 트랙 (발췌)

| 실험 | 결과 |
| --- | --- |
| 5분봉 이벤트 연구 — 뉴스 후 30·60분 초과수익 | <span class="st st-done">완료</span> 초과수익 사실상 없음 — 값은 되돌림에서 나온다 |
| 가중치 재적합·자동 승격 루프 | <span class="st st-done">완료</span> 채점→재적합→승격 자동화 — 변동성 초과 적중 정의로 첫 실전 승격(하한 0.50 > 기준선 0.34) |
| 펀더멘털 → 판정 편입 | <span class="st st-drop">측정 후 기각</span> 전 조합 게이트 미달(역방향) — 서술 축 유지 |
| LLM 라이선스 실사 | <span class="st st-done">완료</span> 공개 서비스 전 모델 교체 필수 판정 |
| Neo4j 그래프 질의 게이트(E4) | <span class="st st-wait">측정 후 보류</span> 실질문 129건 전수 판정 — graph-only 0건, 착수 조건 미달 |
| AI 모의투자 리플레이 30거래일(7/30~9/8) | <span class="st st-done">완료</span> EXAONE −5.5% · 지표 규칙 +7.0% · SPY 보유 +3.8% — LLM 판단이 규칙보다 뒤졌다는 기록 자체가 결과 |

</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

## 경쟁 벤치마크 트랙 — 5개 서비스 대조 (2026-08-24)

경쟁 서비스 5곳과 기능을 대조해 도출한 개선·신규 항목. **추천 착수 순서 7건을 전부 구현 완료**했다
(백엔드 테스트 1189 passed · 아키텍처 계약 5 KEPT · 프론트 타입 체크 통과).

| 항목 | 상태 |
| --- | --- |
| I-10 반경·전년대비(YoY) 질의 가드 — 좌표 유클리드 필터 + 미적용 시 결정론 명시 | <span class="st st-done">완료 2026-08</span> |
| I-1 상권변화지표 해석 팩트 — 4분류 톤 서술 + chat 주입 + 랭킹 필터 | <span class="st st-done">완료 2026-08</span> |
| I-3 랭킹 필터·행정동 롤업 축 | <span class="st st-done">완료 2026-08</span> |
| I-2 골든셋 경쟁사 예시 질문 편입 (129케이스) | <span class="st st-done">완료 2026-09</span> 전건 완주·baseline 박제 |
| B1 상권 북마크 알림 — 분기·등급 상태 스캔 + dedupe | <span class="st st-done">완료 2026-08</span> |
| B2 주가 영향 키워드 Top-N 결정론 추출 | <span class="st st-done">완료 2026-08</span> |
| I-7 알림 채널 텔레그램 추가 — 실발송(이메일+텔레그램 동시 수신) 검증 | <span class="st st-done">완료 2026-08</span> |

</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

<h2 id="risks">위험 관리 방안</h2>

1인 개발·온프레미스 운영에서 실제로 발생했거나 발생 가능한 위험과 대응이다.

| 위험 | 대응 |
| --- | --- |
| 데이터 유실 | 백업 3계층 — 일간 로컬 로테이션 + 주간 오프사이트 미러 + 분기 복원 리허설(실복원으로 검증, 백업 파일 존재만 믿지 않는다) |
| 서비스 다운을 모르고 지나감 | 구조화 로깅 + 업타임 모니터링, 강제 다운 시 5분 내 알림을 게이트로 검증 |
| LLM 라이선스 리스크 | 현행 모델은 연구 전용(비상용) — 실사로 확인했고, 공개 서비스 전 상용 가능 모델로 교체하는 스위치·회귀 절차를 준비해뒀다 |
| 잘못된 통계로 인한 오도 | 표본 기준 미달 통계는 확률 주장 금지, 백테스트 게이트(유효표본 보정·Wilson 하한) 미달 시 기각 |
| 품질 저하를 모르고 배포 | 평가 하네스 baseline 회귀 게이트 — 프롬프트·모델 변경은 골든셋 대조 후에만 |

</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

<h2 id="next">작업 보드 <span style="color:#9a9aa2;font-size:0.85rem;font-weight:400;">(2026-09-08 기준)</span></h2>

<div class="kb-wrap">
<div class="kb">

<div class="kb-col">
<h4>📋 Backlog <span style="color:#9a9aa2;font-weight:400;font-size:0.8rem;">게이트 대기</span></h4>
<div class="kb-card">개인화 ② 선호 프로파일 — 실사용자 확보가 착수 조건<span class="kb-tag kb-be">백엔드</span></div>
<div class="kb-card">매물(listing) 스포크 — 수요 게이트 뒤<span class="kb-tag kb-be">백엔드</span></div>
<div class="kb-card">상가임대차(lease) 스포크 후보 — 법령 RAG 게이트 검토<span class="kb-tag kb-be">백엔드</span></div>
<div class="kb-card">뉴스 감성 피처 재채점 — 라벨 3개월 축적 후(~10월)<span class="kb-tag kb-ml">데이터·ML</span></div>
</div>

<div class="kb-col">
<h4>🗂 To Do <span style="color:#9a9aa2;font-weight:400;font-size:0.8rem;">실행·판정만 잔여</span></h4>
<div class="kb-card">오프사이트 백업 첫 미러(Google Drive + USB 이중화) + 복원 리허설 (게이트)<span class="kb-tag kb-op">운영</span></div>
<div class="kb-card">AI 모의투자 첫 자동 step(매일 14:00 스냅샷 뒤) 로그 확인<span class="kb-tag kb-op">운영</span></div>
<div class="kb-card">창업비용 첫 자동 적재(10/1) 확인 — 수동 적재는 완료<span class="kb-tag kb-ml">데이터·ML</span></div>
<div class="kb-card">상권 신규 분기 첫 자동 적재<span class="kb-tag kb-ml">데이터·ML</span></div>
<div class="kb-card">LLM 교체 후보 pull → 134문항 회귀 비교<span class="kb-tag kb-ml">데이터·ML</span></div>
</div>

<div class="kb-col">
<h4>🔄 In Progress</h4>
<div class="kb-card">채팅 답변 골격(AnswerSkeleton) 전환 — 결론 첫 줄을 코드가 쓰는 파이프라인, QA 잔여 1건<span class="kb-tag kb-be">백엔드</span></div>
<div class="kb-card">골든셋 134문항 baseline 재박제 — 9월 가드 반영 후 회귀 게이트 재실행<span class="kb-tag kb-ml">데이터·ML</span></div>
<div class="kb-card">개발 기록 블로그 9월 개편·소급 리뷰<span class="kb-tag kb-op">운영</span></div>
</div>

<div class="kb-col">
<h4>✅ Done <span style="color:#9a9aa2;font-weight:400;font-size:0.8rem;">최근 완료</span></h4>
<div class="kb-card">game 스포크 폐기 → AI 모의투자 슬라이스 + 30거래일 리플레이<span class="kb-tag kb-be">백엔드</span></div>
<div class="kb-card">페르소나 10명 QA → 개선 21건 배포(예산 답·비교표·결론 첫 줄·한국 종목명 KIND 소스)<span class="kb-tag kb-be">백엔드</span></div>
<div class="kb-card">공정위 창업비용 팩트 적재 + 월 1회 CronJob<span class="kb-tag kb-ml">데이터·ML</span></div>
<div class="kb-card">앱 계층 k3s 컷오버 — CronJob 5종 이전, DB는 도커 잔류<span class="kb-tag kb-op">운영</span></div>
<div class="kb-card">/paper 화면 게임식 재구성(점수판·활동 피드·보유 카드), 알림 진입점·툴팁·모바일 라벨<span class="kb-tag kb-fe">프론트</span></div>
</div>

</div>
</div>

※ 보드는 마일스톤 진행에 따라 갱신한다. 마일스톤 종료 시점의 보드 스냅샷은 리뷰 포스트에 기록한다.

</div>

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

<h2 id="rejected">탈락 아이디어 검토 근거</h2>

**측정 후 기각** — 실험해서 숫자로 확인하고 버린 것들. 기각 근거는 문서로 남긴다.

- 펀더멘털(PER/PBR) 판정 편입 — 워크포워드 백테스트 전 조합 게이트 미달(역방향). 서술 축으로만 유지
- 뉴스 후 30·60분 단기 반응 매매 — 이벤트 연구 결과 초과수익 사실상 없음
- 지역지 RSS 별도 수집 — 기존 수집원 키워드 조합으로 충분함을 dry-run으로 확인

**명시적 비추천 (과설계 방지 목록)** — 이력서용 기술 나열이 되지 않도록, 규모에 맞지 않는
도입을 목록으로 막아둔다.

- 메시지 브로커 · MSA 분리 · 클라우드 전환 (k3s 단일 노드는 예외 — 배포·CronJob·재시작을 한 곳에서 보려는 운영 편의이지 확장 목적이 아니다)
- MLflow · Airflow · DVC (배치 스크립트 + git 태그로 충분)
- GraphQL · BFF · 벡터 DB 교체(Qdrant 등) · 청킹 라이브러리 · 실험 관리 도구
- 결제/유료 기능 — 무료 범위 원칙과 충돌

</div>

</div>

[← 개발 기록]({{ '/posts/' | relative_url }}) · [프로젝트 개요]({{ '/overview/' | relative_url }}) · [목차]({{ '/toc/' | relative_url }})
