# P05 정우진 — 38세 미국주식 데이터 트레이더, NVDA 스윙 (재실행, 가입 정상)

## 여정 로그
| # | 행동 | 본 것 | 초 | 마찰 |
|---|---|---|---|---|
| 1-2 | 가입·로그인 | ok | 2 | - |
| 3 | quote | 230.36 delayed:true, prev 228.45 | 1.2 | **기준 시각 필드 없음** |
| 4 | POST /stock/analyze {"query":"NVDA"} | **symbol "AAPL"** RSI 53.95 MA20 313 … | 23 | **심각**: 다른 종목 데이터, 경고 없음 |
| 5 | forecast | as_of 9/4, up_rate 0.4208 n=3379 CI 0.404~0.438 baseline 0.417, RSI 60.4 ATR 3.31% regime BULL | 12 | as_of 나흘 전(휴장 때문 — 화면에 설명 없음) |
| 6-7 | 5m/1d prices | 마지막 봉 9/4 | 0.01 | "5분봉인데 나흘 전" — 9/5~7 휴장이라 정상이나 고지 없음 |
| 8 | news | 20건, 최신 9/8 05:20, **sentiment/eventType 전부 null** | 0.07 | 라벨 0건 |
| 9 | fundamentals | asOf 9/7 PER 29.2 PBR 24.3 ROE 117% | 0.01 | - |
| 10-11 | 북마크·알림 | id 7 / id 3 | 0.4 | - |

## 지표
```json
{"task_success": "partial", "steps": 11, "optimal_steps": 9, "time_to_first_meaningful_action_s": 5, "friction_count": 5,
 "heuristic_violations": ["9 오류 복구: analyze가 조용히 다른 종목을 반환", "1 가시성: quote에 기준 시각 없음·휴장 설명 없음", "4 일관성: news 라벨 필드는 있는데 전부 null"], "abandoned": false, "chat_asks": 0}
```

## 막힌 지점
analyze 결과가 NVDA가 아니어서 지표 8개 목표 미달(forecast에서 6개 확보). 뉴스 라벨 0건.

## 개선 제안 3개
1. `/stock/analyze` 심볼 불일치 — 응답 symbol이 요청과 다르면 잡는 회귀 테스트.
2. quote·prices·forecast에 "기준: 9/4 종가(미국 휴장 9/5~7)" 같은 절대 시각·휴장 고지.
3. news 라벨이 없으면 "라벨링 대기중" 표시, 배지는 숨김.

## 한 줄 결론
지표 물어봤더니 딴 종목 답이 나오고, 뉴스는 라벨 칸만 있고 비어 있다 — 북마크·알림은 됐지만 이 화면으로 스윙 진입 타이밍은 못 잡는다.
