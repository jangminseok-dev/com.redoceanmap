---
layout: default
title: 홈
---

<div class="cn-grid">

<div class="cn-card cn-bg-dark cn-statement cn-wide cn-hero">
  <p class="cn-label">redoceanmap 개발 기록</p>
  <h1>서울 어디에 창업할지, 이 주식이 지금 어떤지 —<br>공공데이터와 로컬 LLM으로 답하는 서비스를<br>혼자 만들고 운영하는 기록</h1>
  <p>상권 분석 · 주식 해설 · AI 모의투자. 매매 권유는 하지 않고 검증에 떨어진 것은 기각해 기록합니다.</p>
  <p class="cn-actions">
    <a class="btn btn--primary" href="{{ '/posts/' | relative_url }}">개발 기록 읽기</a>
    <a class="btn" href="{{ '/overview/' | relative_url }}">프로젝트 개요</a>
    <a class="btn" href="https://redoceanmap.com">서비스 열기 →</a>
  </p>
</div>

<div class="cn-wide cn-stats">
  <div class="cn-stat"><span class="cn-stat__value">2026.05 ~</span><span class="cn-stat__label">1인 개발 · 온프레미스(k3s) 운영</span></div>
  <div class="cn-stat"><span class="cn-stat__value">③ 진행 중</span><span class="cn-stat__label">로드맵 3단계 — ①·② 완료</span></div>
  <div class="cn-stat"><span class="cn-stat__value">1,000+</span><span class="cn-stat__label">백엔드 테스트 함수 · 아키텍처 계약 5종</span></div>
  <div class="cn-stat"><span class="cn-stat__value">134문항</span><span class="cn-stat__label">채팅 골든셋 회귀 게이트</span></div>
</div>

<div class="cn-card cn-bg-plain cn-body cn-wide cn-latest" markdown="0">
  <div class="cn-latest__head">
    <h2>최근 기록</h2>
    <a href="{{ '/posts/' | relative_url }}">전체 보기 →</a>
  </div>
  <ul class="cn-postlist">
  {% for post in site.posts limit:3 %}
    <li>
      <a href="{{ post.url | relative_url }}">
        <span class="cn-postlist__date">{{ post.date | date: "%m.%d" }}</span>
        <span class="cn-postlist__title">{{ post.title | escape }}</span>
        <span class="cn-postlist__arrow">›</span>
      </a>
    </li>
  {% endfor %}
  </ul>
</div>

<div class="cn-card cn-bg-sage cn-statement cn-wide">
  <p class="cn-label">무엇을 만들었나</p>
  <h2>지도에서 고르고, 대화로 묻고, AI가 굴리는 것을 지켜본다</h2>
</div>

{% include card.html img="/assets/img/question-home-260908b.jpg" bg="warm" title="질문 홈 — 상권이든 주식이든 질문 하나로"
   desc="의도를 먼저 읽고 맞는 데이터로 연결합니다. 결론 첫 줄은 LLM이 아니라 코드가 씁니다." %}
{% include card.html img="/assets/img/market-map-260908b.jpg" bg="sage" title="상권 — 지도 위에서 묻는다"
   desc="동네·업종·예산을 말하면 서울시 분기 데이터와 공정위 창업비용으로 답합니다." %}
{% include card.html img="/assets/img/paper-board-260908b.jpg" bg="dark" title="AI 모의투자 — EXAONE이 굴리는 가상 1억"
   desc="매일 우리 예측·뉴스 라벨을 읽고 판단한 것을 다음 장 시가에 사후 체결. 검증된 지표 규칙·SPY 보유와 나란히 둡니다. 권유는 없습니다." %}
{% include card.html img="/assets/img/stock-board-260908b.jpg" bg="warm" title="주식 — 오늘의 신호 보드"
   desc="워치리스트 종목의 5거래일 방향 신호와 과거 같은 신호일 때의 적중 비율을 평소 비율과 함께 보여 줍니다." %}

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

| 개발 기간 | 2026년 5월 ~ 진행 중 |
| 개발·운영 | 장민석 <span class="cn-dim">— 1인 개발 · 백엔드 PC k3s 단일 노드 · 비용 0원</span> |
| 스택 | FastAPI(모듈러 모놀리식·헥사고날) · Next.js 16 · PostgreSQL(pgvector) · EXAONE 7.8B(Ollama) |
| 문서 갱신일 | 2026년 9월 8일 |
| 저장소 | [github.com/jangminseok-dev/com.redoceanmap](https://github.com/jangminseok-dev/com.redoceanmap) |
| 서비스 | [redoceanmap.com](https://redoceanmap.com) |

</div>

</div>
