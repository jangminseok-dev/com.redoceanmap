#!/usr/bin/env bash
# 루트 .env / .env.auth → k3s Secret. 값은 디스크에 남기지 않고 kubectl로만 넘긴다.
#   redocean-env       ← .env      (backend·auth·CronJob 공용)
#   redocean-auth-env  ← .env.auth (auth 전용 — JWT 개인키 발급 경계, backend에는 절대 붙이지 않는다)
#   cloudflared-credentials ← 터널 자격증명 JSON (운영, 2번째 인자를 줄 때만)
# 사용: infra/k8s/secrets.sh <namespace> [cloudflared-credentials.json 경로]
#   개발(맥):        infra/k8s/secrets.sh redocean-dev
#   운영(백엔드 PC): infra/k8s/secrets.sh redocean /home/host/.cloudflared/4b03c4a0-3030-4710-9d74-592c7860acbf.json
# 재실행 = 갱신(apply). 값을 바꾼 뒤엔 파드 재시작: kubectl -n <ns> rollout restart deploy
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NS="${1:?namespace 인자 필요 (redocean-dev | redocean)}"
CF_CRED="${2:-}"

[ -f "$ROOT/.env" ] || { echo ".env 없음: $ROOT/.env" >&2; exit 1; }
[ -f "$ROOT/.env.auth" ] || { echo ".env.auth 없음: $ROOT/.env.auth" >&2; exit 1; }

kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create ns "$NS"

# 앞의 개행은 .env가 개행 없이 끝날 때 마지막 키에 들러붙는 것을 막는다(실측: PGADMIN_PASSWORD 오염).
kubectl -n "$NS" create secret generic redocean-env \
  --from-env-file=<(cat "$ROOT/.env"; printf "\n") \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NS" create secret generic redocean-auth-env \
  --from-env-file=<(cat "$ROOT/.env.auth"; printf "\n") \
  --dry-run=client -o yaml | kubectl apply -f -

if [ -n "$CF_CRED" ]; then
  [ -f "$CF_CRED" ] || { echo "cloudflared 자격증명 없음: $CF_CRED" >&2; exit 1; }
  kubectl -n "$NS" create secret generic cloudflared-credentials \
    --from-file=credentials.json="$CF_CRED" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

echo "secrets ok ($NS): $(kubectl -n "$NS" get secret -o name | tr '\n' ' ')"
