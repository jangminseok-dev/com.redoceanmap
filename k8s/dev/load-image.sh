#!/usr/bin/env bash
# 백엔드 이미지를 docker로 빌드해 k3s(containerd)에 반입한다.
# 처음 한 번 빠르게 띄우려면 빌드 대신 실운영 이미지를 재태그해도 된다(코드는 hostPath라 무관):
#   docker tag minseok97/redoceanmap-backend:latest minseok97/redoceanmap-backend:dev && SKIP_BUILD=1 k8s/dev/load-image.sh
# k3s는 도커 이미지 저장소를 보지 않으므로 build 뒤 반드시 import가 필요하다(매니페스트는 imagePullPolicy: Never).
# 2단계(도커 엔진 제거)에서는 이 스크립트를 nerdctl/buildkit 빌드로 교체한다.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=minseok97/redoceanmap-backend:dev   # 실운영 :latest 태그와 분리 — 재빌드가 실운영 배포 태그를 덮지 않게

[ -n "${SKIP_BUILD:-}" ] || docker build \
  --build-arg GIT_SHA="$(git -C "$ROOT" rev-parse --short HEAD)" \
  --build-arg BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  -t "$IMAGE" "$ROOT/minseok"

# ~4GB 이미지 — 파이프 반입에 수 분 걸린다
docker save "$IMAGE" | sudo k3s ctr images import -
sudo k3s ctr images ls -q | grep -F "$IMAGE"
echo "import ok: $IMAGE"

# 이미지를 갈아끼웠으면 파드를 다시 띄워야 새 레이어를 쓴다(코드는 hostPath라 대개 불필요 — requirements 변경 시)
if kubectl get ns redocean-dev >/dev/null 2>&1; then
  kubectl -n redocean-dev rollout restart deploy backend auth
fi
