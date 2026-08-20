#!/usr/bin/env bash
# 백엔드 PC 1커맨드 배포 (②-M2) — window 브랜치 pull → 프로덕션 compose 재빌드 기동.
# 첫 전환 절차는 docker-compose.prod.yaml 머리말 참고(볼륨 이름 확인이 선행이다).
set -euo pipefail
cd "$(dirname "$0")"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "window" ]; then
  echo "[deploy] 현재 브랜치가 window가 아닙니다: $BRANCH — 배포는 window에서만." >&2
  exit 1
fi

git pull origin window

# 배포된 코드가 어느 커밋인지 이미지에 굽는다 — pull 뒤에 읽어야 방금 받은 커밋이 잡힌다.
# 이 값이 /health의 version으로 나오고, check_freshness.py --expect-commit이 대조한다.
export GIT_SHA=$(git rev-parse --short HEAD)
export BUILT_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "[deploy] 굽는 커밋: $GIT_SHA ($BUILT_AT)"

docker compose -f docker-compose.prod.yaml up -d --build
docker compose -f docker-compose.prod.yaml ps
echo "[deploy] 완료 — healthcheck 안정화까지 ~1분, 이상 시: docker compose -f docker-compose.prod.yaml logs backend"
