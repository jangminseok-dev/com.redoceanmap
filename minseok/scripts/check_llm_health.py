"""LLM 계약·호스트 자원 감시 — 지표가 정상으로 보이는 붕괴를 잡는다.

배경(2026-08-24~28 실장애): I-10이 phase1 표에 열 하나를 더하자 프롬프트가 4,178토큰이 되어
Ollama 기본 창 4,096을 넘었다. 초과분은 **앞에서** 잘려 JSON 형식 지시문이 통째로 사라졌고,
phase1의 코드 반환이 40/40 → 0/44로 죽었다. 그런데 결정론 지역 가드가 이를 대신 채워
`region_hit_rate`는 1.0을 유지했다 — **골든셋 지표로도 안 잡히는 붕괴**였고 4일이 걸렸다.
이어서 같은 날 러너가 커널 OOM으로 중단됐다(llama-server anon-rss 7.7GiB / 시스템 10.7GiB).

그래서 두 축을 본다:
  ① 계약 카나리아 — 실제 phase1 모양의 프롬프트를 넣어 **스키마와 토큰 예산**을 확인한다.
     지표(정확도·적중률)가 아니라 계약(형식)을 본다. 폴백이 가려도 이건 안 가려진다.
  ② 호스트 자원 — Ollama 생존, 최근 OOM, 여유 메모리. ①이 실패하는 흔한 원인이다.

발송은 check_freshness와 같은 창구(n8n 웹훅)다 — 비밀은 백엔드에 두지 않는다.

실행(호스트 cron — 도커 밖에서 systemd·journal을 봐야 한다):
    venv/bin/python minseok/scripts/check_llm_health.py
    venv/bin/python minseok/scripts/check_llm_health.py --dry-run
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

OLLAMA = _secrets.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
MODEL = _secrets.get("LLM_MODEL", "exaone3.5:7.8b")

# llm_orchestrator.NUM_CTX와 같은 값이어야 한다. 앱 코드를 import하지 않는 이유: 이 스크립트는
# sqlalchemy 없는 호스트 venv에서 돈다(core.llm은 ollama 패키지를 끌어온다).
NUM_CTX = 8192
BUDGET_RATIO = 0.9          # 창의 이 비율을 넘으면 경고 — 넘기 전에 알아야 한다
MIN_FREE_MEM_GIB = 2.0      # 이 아래면 OOM 사정권

# phase1과 **같은 계약 + 같은 크기**여야 한다. 표를 작게 만들면 스키마는 확인되지만
# 토큰 예산 감시가 무의미해진다 — 2026-08-24 사고가 바로 "열 하나로 창을 넘은" 사건이다.
# 실제 phase1은 상한 80행이므로 여기서도 80행을 만든다(≈4,100토큰, 실측 프롬프트와 동급).
_CANARY_ROWS = 80


def _canary_prompt() -> str:
    header = (
        "다음 상권 표에서 질문에 맞는 상권 3곳을 고르시오.\n"
        'JSON만 출력: {"service_code": "...", "service_name": "...", "trdar_codes": [숫자, ...]}\n\n'
        "질문: 성수동 카페\n업종코드: CS100009 커피-음료\n\n"
        "상권코드|상권명|자치구|행정동|상권전체월매출합계(만원)|매출전년동분기대비(%)|질문지역\n"
    )
    rows = [
        f"{3110000 + i}|성수{i}번상권|성동구|성수{i % 4 + 1}가{i % 3 + 1}동|"
        f"{6639857 - i * 41237}|{'-' if i % 3 else f'{i % 20 - 10:+.1f}'}|{'★' if i % 7 == 0 else ''}"
        for i in range(_CANARY_ROWS)
    ]
    return header + "\n".join(rows) + "\n"


def canary() -> tuple[bool, str]:
    """실제 추론 1회 — 스키마 준수와 프롬프트 토큰을 함께 본다."""
    try:
        res = requests.post(
            f"{OLLAMA}/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": _canary_prompt()}],
                "stream": False,
                "options": {"num_ctx": NUM_CTX},
            },
            timeout=180,
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:  # 네트워크·타임아웃·5xx 전부 계약 실패로 본다
        return False, f"추론 호출 실패: {type(e).__name__} {e}"

    raw = (data.get("message") or {}).get("content", "")
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = text.find("{"), text.rfind("}")
    try:
        parsed = json.loads(text[start:end + 1]) if start >= 0 < end else {}
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed.get("trdar_codes"), list):
        return False, (
            f"스키마 이탈 — trdar_codes 없음(응답 {len(raw)}자). "
            f"프롬프트 {data.get('prompt_eval_count')}토큰. "
            "창 초과로 지시문이 잘렸을 수 있다(2026-08-24 선례)."
        )

    used = data.get("prompt_eval_count") or 0
    if used >= NUM_CTX * BUDGET_RATIO:
        return False, f"토큰 예산 근접 — 프롬프트 {used}토큰 / 창 {NUM_CTX}({used / NUM_CTX:.0%})"
    return True, f"정상 — 스키마 OK, 프롬프트 {used}토큰 / 창 {NUM_CTX}"


def _cmd(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def host_resources() -> list[str]:
    """Ollama 생존·최근 OOM·여유 메모리. 카나리아 실패의 흔한 원인들이다."""
    problems: list[str] = []

    if _cmd(["systemctl", "is-active", "ollama"]) != "active":
        problems.append("Ollama 서비스가 active가 아니다 — 추론 전 경로가 멈춘다")

    oom = _cmd(["journalctl", "-u", "ollama", "--since", "24 hours ago", "--no-pager"])
    if "oom-kill" in oom or "OOM killer" in oom:
        problems.append(
            "최근 24시간 내 Ollama가 커널 OOM으로 죽었다 — 호스트 RAM 부족"
            "(mmap이 꺼지면 가중치가 회수 불가 익명 메모리로 올라간다)"
        )

    try:
        info = dict(
            (k.strip(), int(v.split()[0]))
            for k, v in (line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        )
        free_gib = info["MemAvailable"] / 1024 / 1024
        if free_gib < MIN_FREE_MEM_GIB:
            problems.append(f"여유 메모리 {free_gib:.1f}GiB < 기준 {MIN_FREE_MEM_GIB}GiB — OOM 사정권")
    except Exception as e:
        problems.append(f"메모리 확인 실패: {type(e).__name__}")

    return problems


# 오케스트레이터가 남기는 근접 경고(llm_orchestrator._warn_if_near_context)를 걷어온다.
# 카나리아는 합성 프롬프트라 하한만 본다 — **실제 프로덕션 프롬프트**가 창에 닿았는지는
# 이 로그만 안다. 로그를 사람이 읽을 일이 없으므로 감시가 대신 읽는다.
_WARN_MARK = "컨텍스트 창"
# backend는 k3s 파드(ns redocean). 이 스크립트는 호스트 venv cron에서 돌아 KUBECONFIG가 없으므로 경로를 명시한다.
_KUBECONFIG = "/etc/rancher/k3s/k3s.yaml"
_BACKEND_DEPLOY = "deploy/backend"


def runtime_context_warnings() -> list[str]:
    logs = _cmd([
        "kubectl", "--kubeconfig", _KUBECONFIG, "-n", "redocean",
        "logs", "--since=24h", _BACKEND_DEPLOY,
    ])
    hits = [ln for ln in logs.splitlines() if _WARN_MARK in ln]
    if not hits:
        return []
    return [
        f"실제 프롬프트가 컨텍스트 창에 근접한 경고 {len(hits)}건(24시간) — "
        f"최근: {hits[-1][-160:]}"
    ]


def build_body(canary_msg: str, ok: bool, resource_problems: list[str]) -> str:
    lines = ["LLM 경로에 이상이 감지됐습니다.", ""]
    if not ok:
        lines += ["[계약 카나리아]", f"  · {canary_msg}", ""]
    if resource_problems:
        lines += ["[호스트 자원]"] + [f"  · {p}" for p in resource_problems] + [""]
    lines += [
        "조치: `journalctl -u ollama -n 100`으로 적재 로그 확인.",
        "  · 스키마 이탈이면 프롬프트가 창을 넘었는지 본다(llm_orchestrator.NUM_CTX).",
        "  · OOM이면 .wslconfig 메모리 상향 또는 도커 스택 축소.",
        "",
        "이 감시도 백엔드 PC 안에서 돕니다 — PC가 꺼지면 이 메일도 오지 않습니다.",
    ]
    return "\n".join(lines)


def send(subject: str, body: str) -> None:
    to = _secrets.get("ALERT_EMAIL")
    if not to:
        raise RuntimeError("ALERT_EMAIL 미설정 — .env에 수신 주소를 넣어야 알림이 나갑니다.")
    res = requests.post(
        _secrets.require("N8N_EMAIL_WEBHOOK_URL"),
        json={"to": to, "subject": subject, "body": body},
        headers={"X-Webhook-Token": _secrets.get("N8N_OUTBOUND_TOKEN", "")},
        timeout=30,
    )
    res.raise_for_status()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    stamp = f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"

    ok, canary_msg = canary()
    resource_problems = host_resources() + runtime_context_warnings()
    print(f"  계약 카나리아: {canary_msg}")
    for p in resource_problems:
        print(f"  자원: {p}")

    if ok and not resource_problems:
        print(f"{stamp} LLM 경로 정상 — 알림 없음", flush=True)
        return 0

    parts = ([] if ok else ["계약 위반"]) + (["호스트 자원"] if resource_problems else [])
    subject = f"[redoceanmap] LLM {' / '.join(parts)}"
    body = build_body(canary_msg, ok, resource_problems)
    print(f"{stamp} 이상 감지\n{body}", flush=True)
    if dry_run:
        print("(--dry-run — 발송 생략)")
        return 1
    send(subject, body)
    print("알림 발송 완료", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
