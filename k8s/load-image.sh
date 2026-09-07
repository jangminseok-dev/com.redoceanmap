#!/usr/bin/env bash
# 백엔드 이미지를 docker로 빌드해 k3s에 넣는다.
#   백엔드 PC(k3s 네이티브, containerd): docker build → docker save | k3s ctr images import
#   맥(colima docker 런타임): k3s가 cri-dockerd로 도커 이미지를 직접 보므로 build만 하면 끝
# 사용: k8s/load-image.sh <tag> [namespace]
#   맥:        k8s/load-image.sh dev redocean-dev
#   백엔드 PC: k8s/load-image.sh latest redocean   (deploy.sh가 부른다)
# 네임스페이스를 주면 backend·auth를 재시작해 새 레이어를 쓰게 한다(코드가 hostPath인 개발은 requirements 변경 때만 필요).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:?tag 인자 필요 (dev | latest)}"
NS="${2:-}"
IMAGE="minseok97/redoceanmap-backend:$TAG"

docker build \
  --build-arg GIT_SHA="$(git -C "$ROOT" rev-parse --short HEAD)" \
  --build-arg BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "$IMAGE" "$ROOT/minseok"

if command -v k3s >/dev/null 2>&1; then
  # ~4GB — 파이프 반입에 수 분
  docker save "$IMAGE" | sudo k3s ctr images import -
  sudo k3s ctr images ls -q | grep -F "$IMAGE"
  echo "import ok: $IMAGE"
else
  echo "k3s 바이너리 없음 — colima(docker 런타임)로 간주, 반입 생략: $IMAGE"
fi

if [ -n "$NS" ] && kubectl get ns "$NS" >/dev/null 2>&1; then
  kubectl -n "$NS" rollout restart deploy backend auth
fi
