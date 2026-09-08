---
layout: default
title: 홈
---

<div class="cn-grid">

<div class="cn-card cn-bg-dark cn-statement cn-wide cn-hero">
  <p class="cn-label">redoceanmap 개발 기록</p>
  <h1>서울 어디에 창업할지, 이 주식이 지금 어떤지 —<br>공공데이터와 로컬 LLM으로 답하는 서비스를<br>혼자 만들고 운영하는 기록</h1>
  <p>상권 분석 · 주식 해설 · AI 모의투자. 매매 권유는 하지 않고, 검증에 떨어진 것은 기각해 기록합니다.</p>
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

{% include card.html img="/assets/img/market-map.jpg" bg="sage" title="상권 — 지도 위에서 묻는다"
   desc="동네와 업종을 고르면 분기 흐름·종합점수·업종 적합도를 서울시 실데이터로 풀어 설명해요. 예산을 말하면 공정위 창업비용 기준으로 드는 업종을 골라 줍니다." %}
{% include card.html img="/assets/img/question-home.png" bg="warm" title="대화형 질문 홈"
   desc="상권이든 주식이든 질문 하나로 시작해요. 의도를 먼저 읽고 맞는 데이터로 연결하며, 결론을 첫 줄에 코드가 씁니다." %}

<div class="cn-card cn-bg-dark cn-body cn-feature" markdown="1">

## AI 모의투자 <span class="st st-wip">2026-09 신설</span>

로컬 LLM(EXAONE 7.8B)이 매일 우리 예측 스냅샷과 뉴스 라벨을 읽고 1억원(가상)을 굴립니다.
판단은 다음 장 시가에 사후 체결되고, 검증된 지표 규칙 계정·SPY 보유와 나란히 놓입니다.
**어느 계정이 무엇을 샀다**는 기록까지만 보여 주고 권유는 하지 않습니다.

[6주 리플레이 결과 읽기]({{ '/posts/' | relative_url }})

</div>

{% include card.html img="/assets/img/auth-login.jpg" bg="warm" title="회원 인증 — 자체 + 소셜 3종"
   desc="카카오·네이버·구글 로그인. 토큰을 만드는 열쇠(JWT 개인키)는 인증 서버만 갖고 있어 본체가 뚫려도 토큰을 위조할 수 없습니다." %}

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

| 개발 기간 | 2026년 5월 ~ 진행 중 <span class="cn-dim">— 로드맵 3단계(①·② 완료, ③ 진행 중)</span> |
| 개발·운영 | 장민석 <span class="cn-dim">— 1인 개발 · 백엔드 PC k3s 단일 노드 · 비용 0원</span> |
| 스택 | FastAPI(모듈러 모놀리식·헥사고날) · Next.js 16 · PostgreSQL(pgvector) · EXAONE 7.8B(Ollama) |
| 문서 갱신일 | 2026년 9월 8일 |
| 저장소 | [github.com/jangminseok-dev/com.redoceanmap](https://github.com/jangminseok-dev/com.redoceanmap) |
| 서비스 | [redoceanmap.com](https://redoceanmap.com) |

</div>

</div>
