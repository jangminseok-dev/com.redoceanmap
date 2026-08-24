#!/usr/bin/env bash
# 백엔드 PC 디스크 정리 — 기본은 안전한 것만(재생성·재다운로드 가능), 큰 덩어리는 플래그로 선택.
#
#   sudo ./cleanup_disk.sh                      # 도커 빌드캐시·댕글링 이미지, journal 200M, apt 캐시
#   sudo ./cleanup_disk.sh --exaone             # + EXAONE 원본 가중치(30GB) + 학습용 .venv(6.7GB)
#   sudo ./cleanup_disk.sh --gemma              # + Ollama gemma4 2종(14GB) — ③-M5 LLM 비교 후보, 비교 끝난 뒤에만
#   sudo ./cleanup_disk.sh --playwright         # + 도커 playwright 이미지(3.4GB)
#   플래그는 조합 가능. 실행 중 컨테이너·실 DB·백업(/mnt/d)·Ollama exaone/bge-m3·cron용 venv/는 절대 건드리지 않는다.
set -euo pipefail

REPO=/home/host/projects/com.redoceanmap
before=$(df --output=used -BG / | tail -1 | tr -dc '0-9')

echo "── 기본 정리 ──"
docker builder prune -af --filter "until=24h" | tail -1
docker image prune -f | tail -1
journalctl --rotate && journalctl --vacuum-size=200M 2>&1 | tail -1
apt-get clean && echo "apt 캐시 제거"

for flag in "$@"; do
    case "$flag" in
        --exaone)
            echo "── EXAONE 가중치 + .venv ──"
            rm -rf "$REPO/minseok/EXAONE-3.5-7.8B-Instruct" "$REPO/.venv" && echo "제거됨 (재개 시 HF에서 재다운로드)";;
        --gemma)
            echo "── Ollama gemma4 ──"
            sudo -u "${SUDO_USER:-$USER}" ollama rm gemma4:e2b gemma4-hermes:e2b 2>&1 | tail -2;;
        --playwright)
            echo "── playwright 이미지 ──"
            docker rmi mcr.microsoft.com/playwright:v1.61.1-noble 2>&1 | tail -1;;
        *) echo "알 수 없는 플래그: $flag" >&2; exit 1;;
    esac
done

after=$(df --output=used -BG / | tail -1 | tr -dc '0-9')
echo "── 결과: ${before}G → ${after}G ($((before-after))GB 확보) ──"
df -h / | tail -1
