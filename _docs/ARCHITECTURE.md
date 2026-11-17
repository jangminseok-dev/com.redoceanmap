# 아키텍처 요약 (이전 README에서 옮김)

> 2026-11 README 개편 때 루트 README의 "무엇이 다른가", "구조", "대화 파이프라인", "스택", "실행" 절을 내용 그대로 옮겼습니다.
> 숫자와 문장은 작성 당시(2026-08~10) 기준이며, 상대 링크만 이 폴더 위치에 맞게 고쳤습니다.
> 아래 "CI 없이도 기계 검증된다"는 작성 당시 문장이며, CI는 2026-10-06 다시 켰습니다(`.github/workflows/ci.yml`).
> 서비스는 2026-10-26 운영을 종료했습니다.

## 무엇이 다른가

- **아키텍처가 문서가 아니라 계약이다** — 앱 내부는 헥사고날(`adapter → app → domain`),
  앱 사이는 허브-스포크 스타 토폴로지. 두 구조 모두 [import-linter 계약 5종](../minseok/.importlinter)으로
  CI 없이도 기계 검증된다(클린 계층 · 스포크 상호 독립 · 프레임워크 격리 · 도메인 순수성 · 허브 격리).
- **소형 LLM을 믿지 않는다** — 의도 분류·상권 선택은 LLM이 하되, 오답 패턴은 코드로 막는다:
  서울 외 지역 결정론 차단, 질문 지역 보정, 직전 추천 승계, 단위/통화 명시, 근거 없는 입지 서술 금지.
  프롬프트에는 원값이 아니라 **의미 해석 문장**(구간 폭 보정된 피크 시간, 절대 건수 병기 폐업률)을 주입한다.
- **주장에는 숫자를 붙인다** — 상권 종합점수는 워크포워드 백테스트로 예측력을 실측하고
  (우수 등급 t+1 상대 유동인구 +5.07%p, 컴포넌트 ρ는 약함 — "예측기가 아니라 현황 요약"으로 한계 명시),
  조회 성능은 인덱스 재설계 2.2ms→0.065ms · 벤치마크 캐시 330ms→12.4ms로 계측했다.
- **LLM 품질을 회귀 테스트한다** — 골든셋 134문항 → 실모델 러너 → 결정론 채점(의도 정확도·상권 적중률·
  환각 숫자·금지 표현·가드 발동률·p95 지연) → baseline 대비 게이트. LLM-as-judge를 쓰지 않는다.
  → [minseok/apps/chat/_docs/EVAL.md](../minseok/apps/chat/_docs/EVAL.md)

## 구조

```
                        ┌─ www/  Next.js 16 · React 19 (Vercel)
  브라우저 ─ /api/backend ┘            │ rewrite
                                      ▼
  minseok/  FastAPI 모듈러 모놀리식 ── 스타 토폴로지
  ┌─────────────────────────────────────────────────────┐
  │                    hub (허브)                        │
  │   계약(포트+DTO)만 소유 — 스포크를 모른다               │
  └──┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘
     ▼      ▼      ▼      ▼      ▼      ▼      ▼
   chat   market  stock  auth  admin  recommendation · mail
   (LLM)  (상권)  (주식)  (JWT)  (RBAC) (모의투자)
     각 앱 내부 = 헥사고날: adapter → app(ports/use_cases) → domain
```

- 스포크끼리 직접 import 금지 — 교차 협력은 허브 포트 경유, 구현은 `main.py`가 주입
- 인증은 별도 프로세스(`auth_main.py`)가 개인키를 분리 보유 — 백엔드는 토큰 발급 불가
- market은 전용 DB(3NF: 차원 5 + 팩트 9, 20분기) — 공유 DB와 불가침

## 대화 파이프라인 (chat 앱)

```
질문 → phase0 의도분류(4종) ─┬─ market: phase1 상권·업종 선택 → 팩트·점수·인사이트·기사 주입 → phase2 서술
   Gemma 4 e4b QAT(로컬 생성)  ├─ stock: 종목 해석 → 지표·뉴스RAG·과거통계·펀더멘털 → 서술(매매지시 금지)
                             ├─ market_news: 뉴스 의미검색(embeddinggemma+pgvector) → 서술
                             └─ general: 외부 Gemini 위임(폴백)
        각 단계 사이에 결정론 가드 — LLM 오답을 코드가 보정하고, 보정률 자체를 평가 지표로 측정
```

## 스택

| 영역 | 기술 |
| --- | --- |
| 백엔드 | Python 3.11 · FastAPI · SQLAlchemy 2(asyncio) · Pydantic 2 · Alembic |
| LLM | 오케스트레이터 3갈래 — 로컬 생성 Gemma 4 e4b QAT(Ollama, 사고 off) · 임베딩 embeddinggemma(768) · 외부 Gemini(일반 질문·폴백) · pgvector 의미 검색 |
| 데이터 | PostgreSQL 17(pgvector) · Redis 7 · Neo4j · 서울 열린데이터광장(팩트 9종 · 인허가 68만건) |
| 프론트 | Next.js 16 · React 19 · TS 5 · Tailwind 4 · zustand · TanStack Query |
| 인프라 | 온프레미스(앱 k3s · DB 도커 compose, 루프백 바인딩) · cloudflared 터널 · 일일 백업 cron |

## 실행

```bash
cd infra && docker compose up -d pgvector redis  # DB 계층(도커)
kubectl apply -k infra/k8s/overlays/dev-mac         # 앱(k3s) — 사전: infra/k8s/secrets.sh redocean-dev, infra/k8s/load-image.sh dev (infra/k8s/README.md)
cd minseok/apps/market && docker compose up -d  # market 전용 DB(:5434, 선택)
cd www && pnpm run dev                        # 프론트(:3000) — NEXT_PUBLIC_API_URL=http://192.168.64.2:18000
```

검증(호스트에 파이썬 없음 — 도커 경유):

```bash
# 테스트 151파일
docker run --rm -v $PWD:/work -w /work -e PYTHONPATH=/work/minseok:/work/minseok/apps \
  minseok97/redoceanmap-backend:latest python -m pytest minseok/apps -q -m "not ollama and not network"
# 아키텍처 계약 5종
docker run --rm -v $PWD:/work -w /work/minseok -e PYTHONPATH=apps \
  minseok97/redoceanmap-backend:latest lint-imports --config .importlinter
cd www && pnpm run typecheck
```

