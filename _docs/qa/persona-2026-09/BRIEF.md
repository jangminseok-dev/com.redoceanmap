# 페르소나 QA 공통 브리프 (redoceanmap.com — 서울 상권 분석 + 주식 분석 + AI 모의투자 열람)

## 당신의 역할
지정된 페르소나가 되어 **실제 프로덕션 서비스**를 상대로 회원가입부터 목적 달성까지 걷는다. 당신은 개발자가 아니라
그 사람이다 — 화면에 보이는 문구·응답만으로 판단하고, 이해 안 되면 이해 안 된다고 기록한다. 코드를 고치지 않는다.

## 도구(하네스) — 반드시 이걸로만 서비스에 접근
```bash
source /tmp/claude-1000/-home-host-projects-com-redoceanmap/efbb826c-290f-4641-86f7-33631ed7ab53/scratchpad/qa/lib.sh
qa_register qa.personaNN@redoceanmap.com "이름"      # 가입(비밀번호는 하네스 고정) — NN은 당신 번호
qa_login qa.personaNN@redoceanmap.com                # → 이후 호출에 토큰 자동 첨부
qa_page /                                            # 사이트 HTML을 텍스트로(로그인 전 셸·홈 카피). /market /stock /areas /paper /profile /bookmarks /history
qa_get /market/areas/ranking | qa_json 1500          # GET (경로에 한글 금지 → qa_getq)
qa_getq /market/areas/ranking gu=성동구 service_code=CS100010 | qa_json 1500
qa_get "/stock/AAPL/forecast" | qa_json; qa_get "/stock/005930/prices?timeframe=1d&limit=5" | qa_json
qa_post /stock/analyze '{"query":"삼성전자"}' | qa_json 2000        # 종목 분석(느림 5~15초)
qa_post /bookmarks '{"target_type":"area","target_key":"3120052","label":"성수역"}' | qa_json
qa_put /profile '{"purpose":"startup","risk_level":2,"budget_band":"50m_100m","debt_burden":"none","horizon":"mid"}' | qa_json
qa_post /price-alerts '{"ticker":"005930","target_price":70000,"direction":"below"}' | qa_json
qa_ask "성수동에 카페 차릴만해?" | qa_json 3000       # 채팅(20~90초, 다른 페르소나와 LLM을 공유해 더 길 수 있음). 응답 conversationId를 다음 질문 2번째 인자로 넘기면 멀티턴
qa_get /chat/conversations | qa_json; qa_get /stock/board | qa_json; qa_get /stock/paper/board | qa_json; qa_get "/stock/paper/accounts/exaone/decisions?limit=3" | qa_json 3000
```
- 화면 문구·버튼 배치가 궁금하면 소스를 **읽어도 된다**(www/app/(seoul)/**/page.tsx, www/components/**). 단 사용자가 보는 것만 근거로 삼는다.
- 사이트 라우트: `/`(홈·질문) `/market`(상권 워크스페이스) `/areas`(상권 둘러보기) `/stock`(주식) `/paper`(AI 모의투자) `/profile` `/bookmarks` `/history`.

## 예산·규칙
- 도구 호출 **최대 18회**, 채팅 질문 **최대 3회**. 예산 안에 목적을 못 이루면 `ABANDON`을 선언하고 이유를 쓴다.
- 같은 실패를 3번 반복하지 않는다. 막히면 페르소나답게 다른 길(다른 화면·다른 질문)을 찾고, 그것도 안 되면 포기한다.
- 응답을 그대로 신뢰하지 말고 페르소나 눈으로 평가한다: "이 답으로 내 결정을 내릴 수 있나?"
- 이 서비스는 매매 권유·확률 단정을 하지 않는 정책이 있다. 그게 페르소나 목적에 방해되면 **방해된다고 기록**한다(정책 옹호 금지).

## 산출물 — 반드시 아래 파일에 한국어로
`/tmp/claude-1000/-home-host-projects-com-redoceanmap/efbb826c-290f-4641-86f7-33631ed7ab53/scratchpad/qa/report-NN.md`
```
# P{NN} {페르소나 한 줄}
## 목표와 성공 기준
## 여정 로그
| # | 행동 | 본 것(핵심 문구·수치 인용) | 소요(초) | 마찰(있으면) |
## 지표
```json
{"task_success": true|false|"partial", "steps": n, "optimal_steps": n, "time_to_first_meaningful_action_s": n,
 "friction_count": n, "heuristic_violations": ["NN/g 휴리스틱 이름: 근거", ...], "abandoned": false, "chat_asks": n}
```
## 막힌 지점 (있으면 어디서, 왜)
## 개선 제안 3개 (구체적으로 — 어느 화면/문구/응답을 어떻게)
## 한 줄 결론 (페르소나 말투)
```
지표 정의: steps=서비스에 한 행동 수, optimal_steps=이상적 최소 행동 수, time_to_first_meaningful_action=가입 완료부터 목적과 관련된 첫 실질 정보를 얻기까지 초.
