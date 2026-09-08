# P07 오세훈 — 36세 회사원, 여윳돈 500만원 테슬라 vs 애플

## 여정 로그
| # | 행동 | 본 것 | 초 | 마찰 |
|---|---|---|---|---|
| 1-2 | 가입·로그인 | ok | 2 | - |
| 3 | 채팅 "테슬라랑 애플 중에 어디가 나아?" | "여러 종목 비교는 아직 지원하지 않아 '테슬라'만 분석했어요. 애플은 따로 물어봐 주세요." → 테슬라 NEUTRAL "방향을 말하기 어렵습니다" | 17 | **비교 미지원** (다음 행동은 알려줌) |
| 4 | 이어 "애플은 어때?" | 애플 NEUTRAL, 따로 온 텍스트 | 61 | 1분 소요, 나란히 비교 안 됨 |
| 5-8 | TSLA·AAPL forecast/quote | TSLA up_rate 38%(883/2319) baseline 40% $354.08 −5.9% · AAPL 41%(1707/4143) baseline 42% $319.97 −2.5% | 2 | quote는 forecast base_price와 중복 |
| 9-10 | 둘 다 북마크 → /bookmarks/board | 세로 목록, 방향 배지(중립·중립)+현재가+등락률만 | 1 | **보드에 up_rate·기준선 없음** |

## 지표
```json
{"task_success": "partial", "steps": 10, "optimal_steps": 3, "time_to_first_meaningful_action_s": 24, "friction_count": 4,
 "heuristic_violations": ["2 현실 일치: 비교 질문에 단일 분석", "6 인식>회상: 방향·현재가·상승비율·기준선을 한 화면에 모아 주는 곳 없음", "7 효율성: 비교 지름길 없음"], "abandoned": false, "chat_asks": 2}
```

## 막힌 지점
채팅 비교 미지원. 북마크 보드는 나란히 놓지만 결정 근거 수치(상승 비율·기준선)가 빠짐 → forecast 두 개를 손으로 대조.

## 개선 제안 3개
1. "A vs B" 패턴 → 방향·up_rate·baseline·현재가를 한 응답 안의 표/카드 2장으로.
2. `/bookmarks/board`에 up_rate·baseline 추가(BookmarkStockStatus 확장).
3. `/stock?compare=TSLA,AAPL` 비교 뷰.

## 한 줄 결론
물어본 질문은 하나인데 답은 두 번 받아야 했고 나란히도 안 놓아줘서 숫자 네 개를 외웠다 — 표 한 장이면 됐을 걸 화면 세 개를 돌았다.
