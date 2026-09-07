#!/usr/bin/env bash
# 루트 .env / .env.auth → k3s Secret. 값은 디스크에 남기지 않고 kubectl로만 넘긴다.
#   redocean-env       ← .env      (backend·auth·pgvector 공용)
#   redocean-auth-env  ← .env.auth (auth 전용 — JWT 개인키 발급 경계, backend에는 절대 붙이지 않는다)
# 재실행 = 갱신(apply). 값을 바꾼 뒤엔 파드를 재시작해야 반영된다: kubectl -n redocean-dev rollout restart deploy
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NS=redocean-dev

[ -f "$ROOT/.env" ] || { echo ".env 없음: $ROOT/.env" >&2; exit 1; }
[ -f "$ROOT/.env.auth" ] || { echo ".env.auth 없음: $ROOT/.env.auth" >&2; exit 1; }

# neo4j 이미지는 NEO4J_AUTH=user/password 한 키만 받는다 — compose의 neo4j/${NEO4J_PASSWORD}와 동일하게 파생
NEO4J_PASSWORD="$(grep -E '^NEO4J_PASSWORD=' "$ROOT/.env" | cut -d= -f2- || true)"

kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create ns "$NS"

# kubectl은 --from-env-file과 --from-literal을 같이 못 쓴다 — 프로세스 치환으로 합쳐 디스크에 남기지 않는다.
# 앞의 개행은 .env가 개행 없이 끝날 때 마지막 키에 들러붙는 것을 막는다(실측: PGADMIN_PASSWORD 오염).
kubectl -n "$NS" create secret generic redocean-env \
  --from-env-file=<(cat "$ROOT/.env"; printf "\nNEO4J_AUTH=neo4j/%s\n" "$NEO4J_PASSWORD") \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NS" create secret generic redocean-auth-env \
  --from-env-file="$ROOT/.env.auth" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "secrets ok: $(kubectl -n "$NS" get secret redocean-env redocean-auth-env -o name | tr '\n' ' ')"
