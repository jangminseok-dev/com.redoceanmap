#!/usr/bin/env bash
# 백엔드 PC 1커맨드 배포 — window 브랜치 pull → 이미지 재빌드·k3s 반입 → 운영 overlay 적용 → 재시작.
# DB 계층(docker-compose.prod.yaml)은 건드리지 않는다. 첫 컷오버 절차는 k8s/README.md.
set -euo pipefail
cd "$(dirname "$0")"

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "window" ]; then
  echo "[deploy] 현재 브랜치가 window가 아닙니다: $BRANCH — 배포는 window에서만." >&2
  exit 1
fi

git pull origin window
echo "[deploy] 굽는 커밋: $(git rev-parse --short HEAD)"

# build + containerd 반입. 네임스페이스를 넘기지 않는다 — 재시작은 apply 뒤에 한 번만.
k8s/load-image.sh latest

kubectl apply -k k8s/overlays/prod
# :latest 재반입은 태그가 같아 파드를 다시 띄워야 새 이미지를 쓴다(imagePullPolicy Never)
kubectl -n redocean rollout restart deploy backend auth
kubectl -n redocean rollout status deploy backend --timeout=180s
kubectl -n redocean rollout status deploy auth --timeout=120s
kubectl -n redocean get pods
echo "[deploy] 완료 — 확인: curl -s 127.0.0.1:8000/health | python3 -m json.tool | grep commit"
