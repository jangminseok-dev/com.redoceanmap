---
layout: home
---

<div class="cn-grid">

<div class="cn-card cn-bg-dark cn-statement cn-wide">
  <p class="cn-label">개발 기록</p>
  <h1>전국 상권 분석·주식 대화형 플랫폼<br>및 로컬 LLM 기반 실데이터 해설 서비스</h1>
  <p>혼자 쓰던 분석 도구를 누구나 쓰는 서비스로, 한 단계씩 키워가는 기록이에요.<br>
  redoceanmap — Nationwide Commercial District Analysis<br>
  and Conversational Stock Platform with Local-LLM Grounded Explanations</p>
  <p class="cn-actions">
    <a class="btn btn--primary" href="{{ '/overview/' | relative_url }}">프로젝트 개요</a>
    <a class="btn" href="https://redoceanmap.com">서비스 사이트</a>
  </p>
</div>

{% include card.html img="/assets/img/market-map.jpg" bg="sage" title="상권 워크스페이스"
   desc="지도에서 동네를 고르면 바로 물어볼 수 있어요. 답은 서울시 상권 데이터를 3NF로 정규화한 실데이터에서 나옵니다." %}
{% include card.html img="/assets/img/question-home.png" bg="warm" title="대화형 질문 홈"
   desc="상권이든 주식이든 질문 하나로 시작해요. 질문의 의도를 먼저 읽고(phase0), 맞는 데이터로 연결합니다." %}

<div class="cn-card cn-bg-plain cn-body cn-wide" markdown="1">

| 개발 기간 | 2026년 5월 ~ 진행 중 <span style="color:#9a9aa2;font-size:0.9em;">— 단계적 고도화 로드맵 3단계 (①·② 대부분 완료, ③ 진행 중)</span> |
| 개발 | 장민석 <span style="color:#9a9aa2;font-size:0.9em;">— 1인 개발 · 온프레미스 운영</span> |
| 문서 작성일 | 2026년 8월 23일 |
| 깃허브 주소 | [github.com/jangminseok-dev/com.redoceanmap](https://github.com/jangminseok-dev/com.redoceanmap) |
| 서비스 사이트 | [redoceanmap.com](https://redoceanmap.com) |

</div>

{% include card.html img="/assets/img/dark-mode.png" bg="dark" title="다크 모드"
   desc="라이트와 다크, 어느 쪽에서도 크림+적색의 분위기가 그대로예요." %}
{% include card.html img="/assets/img/auth-login.jpg" bg="warm" title="회원 인증 — 자체 + 소셜 3종"
   desc="카카오·네이버·구글 계정으로 간편하게 로그인해요. 토큰을 만드는 열쇠(JWT 개인키)는 인증 서버만 갖고 있습니다." %}

</div>

<p style="text-align: center; margin: 2.2rem 0 1rem;"><a class="btn" href="{{ '/toc/' | relative_url }}">목차 보기 →</a></p>
