"""프로젝트 검증 명령을 MCP 도구로 노출하는 stdio 서버 — 의존성 없음(표준 라이브러리만).

호스트에 파이썬 개발 환경이 없어 백엔드 검증은 전부 도커를 경유한다(루트 CLAUDE.md "명령어").
그 긴 명령을 매번 손으로 옮기지 않도록 세 개만 도구로 감싼다.

프로토콜: JSON-RPC 2.0 / 줄 단위(newline-delimited) / stdin·stdout.
**stdout에는 JSON-RPC 응답만 쓴다** — 로그는 전부 stderr로 보낸다(섞이면 클라이언트가 파싱 실패).

등록은 `~/.claude.json`의 최상위 `mcpServers`에 있다:
    "redoceanmap-tools": {
      "type": "stdio",
      "command": "<repo>/venv/bin/python3",
      "args": ["<repo>/minseok/scripts/mcp_server.py"]
    }
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_IMAGE = "minseok97/redoceanmap-backend:latest"
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "redoceanmap-tools", "version": "0.1.0"}

# 출력 상한 — 실패한 테스트 목록은 뒤쪽에 나오므로 넘치면 앞을 자른다
MAX_OUTPUT_CHARS = 20_000
# 도커 pytest 전체가 수 분 걸린다
TIMEOUT_SECONDS = 1_200

# pytest 대상 경로 화이트리스트 — 셸을 쓰지 않지만 임의 경로 주입은 막는다
TARGET_PATTERN = re.compile(r"^minseok[A-Za-z0-9_./-]*$")


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run(argv: list[str], cwd: Path) -> str:
    """셸 없이 실행하고 stdout+stderr를 합쳐 돌려준다. 종료 코드는 본문에 적는다."""
    log(f"run: {' '.join(argv)}")
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        return f"실행 파일을 찾을 수 없습니다: {exc}"
    except subprocess.TimeoutExpired:
        return f"시간 초과({TIMEOUT_SECONDS}초) — 명령을 중단했습니다."

    body = (proc.stdout or "") + (proc.stderr or "")
    if len(body) > MAX_OUTPUT_CHARS:
        body = "…(앞부분 생략)…\n" + body[-MAX_OUTPUT_CHARS:]
    return f"exit={proc.returncode}\n\n{body.strip()}"


def docker_backend(workdir: str, command: list[str], pythonpath: str) -> list[str]:
    return [
        "docker", "run", "--rm",
        "-v", f"{REPO_ROOT}:/work",
        "-w", workdir,
        "-e", f"PYTHONPATH={pythonpath}",
        BACKEND_IMAGE,
        *command,
    ]


def tool_run_backend_tests(args: dict) -> str:
    target = args.get("target") or "minseok/apps"
    if not TARGET_PATTERN.match(target):
        raise ValueError(f"target은 minseok 아래 경로여야 합니다 (받은 값: {target!r})")

    command = ["python", "-m", "pytest", target, "-q", "-p", "no:cacheprovider"]
    if args.get("skip_integration"):
        command += ["-m", "not ollama and not network"]
    return run(
        docker_backend("/work", command, "/work/minseok:/work/minseok/apps"),
        REPO_ROOT,
    )


def tool_run_import_linter(_args: dict) -> str:
    return run(
        docker_backend("/work/minseok", ["lint-imports", "--config", ".importlinter"], "apps"),
        REPO_ROOT,
    )


def tool_run_tsc(_args: dict) -> str:
    return run(["npx", "tsc", "--noEmit"], REPO_ROOT / "www")


TOOLS = [
    {
        "name": "run_backend_tests",
        "description": (
            "백엔드 pytest를 도커로 실행한다(호스트에 파이썬 환경이 없어 도커 경유가 유일한 경로). "
            "기본 대상은 minseok/apps 전체."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "pytest 대상 경로. minseok 아래여야 한다. 기본값 minseok/apps",
                },
                "skip_integration": {
                    "type": "boolean",
                    "description": "true면 ollama·network 마커를 제외한다(외부 API·로컬 LLM 미사용).",
                },
            },
            "additionalProperties": False,
        },
        "handler": tool_run_backend_tests,
    },
    {
        "name": "run_import_linter",
        "description": (
            "import-linter로 아키텍처 계약 5종을 검사한다 — 클린 아키텍처(adapter>app>domain)·"
            "스포크 상호 독립·프레임워크 격리·도메인 순수성·허브 격리. "
            "구조 변경 뒤에는 테스트와 별도로 이걸 돌린다."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": tool_run_import_linter,
    },
    {
        "name": "run_tsc",
        "description": (
            "프론트엔드 타입 체크(www에서 tsc --noEmit). www에는 테스트 러너가 없어 이것이 유일한 "
            "검증 수단이다. 구 경로 캐시로 오탐이 나면 www/.next/types를 지우고 다시 부른다."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "handler": tool_run_tsc,
    },
]

HANDLERS = {tool["name"]: tool["handler"] for tool in TOOLS}
TOOL_SPECS = [{k: v for k, v in tool.items() if k != "handler"} for tool in TOOLS]


def handle(method: str, params: dict) -> dict:
    if method == "initialize":
        # 클라이언트가 요청한 버전을 그대로 되돌려준다(모르는 값이면 우리 기본값).
        version = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOL_SPECS}
    if method == "tools/call":
        name = params.get("name")
        handler = HANDLERS.get(name)
        if handler is None:
            return {
                "content": [{"type": "text", "text": f"알 수 없는 도구: {name}"}],
                "isError": True,
            }
        try:
            text = handler(params.get("arguments") or {})
        except ValueError as exc:  # 인자 거부 — 도구 실패로 알린다(프로토콜 오류가 아니다)
            return {"content": [{"type": "text", "text": f"거부: {exc}"}], "isError": True}
        return {"content": [{"type": "text", "text": text}], "isError": False}
    raise LookupError(method)


def main() -> None:
    log(f"redoceanmap-tools MCP 서버 시작 (repo={REPO_ROOT})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"JSON 파싱 실패: {exc}")
            continue

        request_id = message.get("id")
        method = message.get("method", "")
        # id가 없으면 알림(notification) — 응답을 보내지 않는다.
        if request_id is None:
            log(f"알림 수신: {method}")
            continue

        try:
            result = handle(method, message.get("params") or {})
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except LookupError:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"지원하지 않는 메서드: {method}"},
            }
        except Exception as exc:  # 서버가 죽으면 세션 내내 도구를 못 쓴다 — 오류로 응답만 한다
            log(f"처리 실패: {method}: {exc!r}")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": f"내부 오류: {exc}"},
            }

        print(json.dumps(response, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
