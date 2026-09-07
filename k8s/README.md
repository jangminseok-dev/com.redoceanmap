# k8s — 쿠버네티스(k3s) 앱 계층

앱(backend·auth·cloudflared·blog-static·CronJob 5건)은 k3s, 상태(DB·Redis·Neo4j·n8n·uptime-kuma)는 도커 compose.
결정 배경·토폴로지·컷오버 설계는 [`_docs/k3s-migration-2026-09.md`](../_docs/k3s-migration-2026-09.md), 실행 계획은
[`_docs/k3s-migration-2026-09-plan.md`](../_docs/k3s-migration-2026-09-plan.md)가 정본이다. DB는 추후 Supabase 계열로 옮기므로
클러스터에 넣지 않았다 — 도커 엔진 제거는 그때 한다.

## 토폴로지

| 도커 compose(상태) | k3s(앱) |
| --- | --- |
| pgvector :5432 · market-pgvector :5434 · redis :6379 · neo4j :7687 · n8n :5678 · uptime-kuma | backend · auth · cloudflared · blog-static · CronJob 5 |

경계는 양방향 모두 **도커 브리지 게이트웨이 172.17.0.1**이다(market DB가 이미 쓰던 방식).
- 파드 → 도커: `base/external-services.yaml`의 셀렉터 없는 Service + EndpointSlice(`pgvector`·`redis`·`neo4j`·`n8n`). 앱의 연결 문자열은 그대로.
  compose 쪽은 `172.17.0.1:<port>` 바인딩을 추가로 가진다(127.0.0.1 유지, LAN 비노출).
- 도커 → 파드: backend·auth hostPort가 `127.0.0.1`과 `172.17.0.1`(운영)에 열린다. n8n·uptime-kuma는 `host.docker.internal:8000/9000`로 부른다.

## 디렉토리

| 경로 | 내용 |
| --- | --- |
| `base/` | backend·auth Deployment/Service, 외부 서비스 EndpointSlice, 비밀 아닌 런타임 env ConfigMap(`redocean-runtime`) |
| `overlays/dev-mac/` | 맥 개발(ns `redocean-dev`): hostPath 핫리로드, 포트 18000/19000, Ollama→맥 호스트, market DB 없음 |
| `overlays/prod/` | 백엔드 PC 운영(ns `redocean`): 이미지 코드, 포트 8000/9000 이중 hostIP, cloudflared·blog-static, `cronjobs/` |
| `secrets.sh <ns> [cloudflared.json]` | `.env`→`redocean-env`, `.env.auth`→`redocean-auth-env`(auth 전용), 자격증명→`cloudflared-credentials` |
| `load-image.sh <tag> [ns]` | `docker build` → 백엔드 PC는 `k3s ctr import`, 맥(colima)은 build만 |

## 맥 — 설치(1회)

Docker Desktop을 **끄고**(삭제하지 않는다 — 다른 프로젝트 볼륨 보존) colima 한 VM에 docker+k3s를 둔다. 두 런타임 동시 기동 금지(5432 충돌).

```bash
brew install colima docker docker-compose
# ~/.docker/config.json 에 "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
colima start --runtime docker --kubernetes --cpu 4 --memory 6 --disk 60 --network-address
docker context use colima && kubectl config use-context colima
```

실측(2026-09-07):
- **hostPort는 `127.0.0.1`로 못 닿는다.** iptables DNAT이라 Lima 포트 포워딩에 안 잡힌다. dev-mac overlay는 hostIP를 colima VM IP(`192.168.64.2`, `colima ls -j`의 `address`)로 두고, 접근도 그 IP로 한다. VM IP가 바뀌면 overlay의 hostIP 2곳과 `www/.env.local`을 같이 고친다.
- 파드에서 맥 Ollama는 `host.lima.internal:11434`로 닿는다(Ollama가 127.0.0.1에만 묶여 있어도 됨).
- virtiofs 마운트는 inotify가 안 오므로 `WATCHFILES_FORCE_POLLING=true`로 `--reload`를 살린다.
- Docker Desktop 볼륨은 tar로 옮긴다: `docker run --rm -v <vol>:/v -v ~/redoceanmap-volumes:/backup alpine tar czf /backup/<vol>.tgz -C /v .` → colima에서 `docker volume create <vol>` 후 `tar xzf`.
- 루트 `.env`에 `NEO4J_PASSWORD`·`PGADMIN_EMAIL`·`PGADMIN_PASSWORD`가 없으면 compose가 파싱 단계에서 멈춘다(다른 프로파일의 `:?` 선언). 값을 넣거나 더미로 넘긴다.

## 맥 — 기동

```bash
docker compose up -d pgvector redis          # DB 계층(도커)
k8s/secrets.sh redocean-dev
k8s/load-image.sh dev                         # requirements 변경 때만 재실행(코드는 hostPath)
kubectl apply -k k8s/overlays/dev-mac
kubectl -n redocean-dev get pods -w
```

| 서비스 | 주소 |
| --- | --- |
| backend | http://192.168.64.2:18000 |
| auth | http://192.168.64.2:19000 |
| pgvector / redis (호스트 도구) | 127.0.0.1:5432 / 6379 |

`www/.env.local`: `NEXT_PUBLIC_API_URL=http://192.168.64.2:18000`, `NEXT_PUBLIC_AUTH_URL=http://192.168.64.2:19000`.
`.env` 값을 바꾸면 `secrets.sh` 재실행 후 `kubectl -n redocean-dev rollout restart deploy`.

## 백엔드 PC — 설치(1회, sudo)

```bash
# traefik(80/443)·servicelb는 끈다 — 전 포트 루프백 원칙(0.0.0.0 금지). 접근은 hostPort로만.
curl -sfL https://get.k3s.io | sudo sh -s - --disable traefik,servicelb --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml     # ~/.bashrc
```

평시 배포: `./deploy.sh`(window 브랜치 pull → `load-image.sh latest` → `kubectl apply -k k8s/overlays/prod` → rollout).

## 백엔드 PC — 컷오버(1회, 사용자 입회)

1. `scripts/backup_db.sh` 수동 1회. `docker ps`·`docker volume ls` 스냅샷. 롤백 기준 커밋 기록(`git rev-parse --short HEAD`).
2. `git pull origin window` → `k8s/secrets.sh redocean /home/host/.cloudflared/4b03c4a0-3030-4710-9d74-592c7860acbf.json` → `k8s/load-image.sh latest`.
3. DB 계층 포트 열기(데이터 무관): `docker compose -f docker-compose.prod.yaml up -d pgvector redis`, `docker compose --profile graph up -d neo4j`,
   리포 밖 `/home/host/projects/n8n/docker-compose.yaml`에 `172.17.0.1:5678:5678` 바인딩 + `extra_hosts: host.docker.internal:host-gateway` 후 `up -d`.
   `ss -ltn | grep 172.17.0.1` → 5432·6379·7687·5678·5434.
4. `kubectl apply --dry-run=server -k k8s/overlays/prod` 통과 확인. 여기까지 무중단.
5. **다운타임 시작** — `docker stop redoceanmap-backend-1 redoceanmap-auth-1 redoceanmap-cloudflared-1`(8000/9000 hostPort 충돌 방지).
6. `kubectl apply -k k8s/overlays/prod` → 파드 Ready → `curl 127.0.0.1:8000/health`, `curl 172.17.0.1:8000/health`(도커→파드 경로).
7. cloudflared 파드 Ready → `api.`·`auth.`·`n8n.`·`blog.redoceanmap.com` 확인 → 로그인·대화·지도 스모크. **다운타임 종료.**
8. n8n UI: 워크플로 HTTP Request URL `http://backend:8000` → `http://host.docker.internal:8000`(3곳). uptime-kuma 모니터 2개 → `host.docker.internal`.
9. crontab에서 도커 기반 5줄 삭제(project_graph·check_freshness·collect_business_permits·collect_commercial_trades·collect_seoul_quarter).
   `kubectl -n redocean get cronjob` 5개 확인, `create job --from=cronjob/check-freshness …`로 1회 실행. `check_llm_health.py` 수동 실행 확인.
10. `docker rm redoceanmap-backend-1 redoceanmap-auth-1 redoceanmap-cloudflared-1`, 구 스택 blog-static `stop`+`rm`. **`--remove-orphans` 금지**(neo4j 삭제).
11. 24시간 뒤 CronJob 성공 이력·uptime-kuma·04:00 백업 로그 확인.

## 롤백

```bash
kubectl delete -k k8s/overlays/prod
git checkout <컷오버 직전 커밋> -- docker-compose.prod.yaml
docker compose -f docker-compose.prod.yaml up -d      # backend·auth·cloudflared 컨테이너판 복귀
```
DB 볼륨은 어느 쪽에서도 손대지 않는다. 172.17.0.1 바인딩 추가는 남아 있어도 무해.

## 운영 명령

```bash
kubectl -n redocean logs deploy/backend --since=1h
kubectl -n redocean create job --from=cronjob/<이름> <이름>-manual-$(date +%s); kubectl -n redocean logs job/<이름>-manual-…
k8s/secrets.sh redocean <cloudflared.json> && kubectl -n redocean rollout restart deploy   # .env 변경 반영
```

## 정리

```bash
kubectl delete -k k8s/overlays/dev-mac        # 맥 개발 스택
colima delete                                 # 맥 VM 통째(도커 볼륨 포함 — 백업 후)
/usr/local/bin/k3s-uninstall.sh               # 백엔드 PC k3s 제거
```
