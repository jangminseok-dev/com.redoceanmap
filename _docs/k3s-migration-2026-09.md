# k3s 전환 설계 — 앱은 k3s, 상태는 도커 (2026-09-07)

1단계(`k8s/dev`, 커밋 31d8b98)의 후속. **경로 주의**: 2026-09-07 폴더 재배치로 `k8s/`→`infra/k8s/`, compose 2종·`deploy.sh`→`infra/`로 옮겨졌다(이 문서·계획서의 경로는 재배치 전 기준, 정본 절차는 `infra/k8s/README.md`). 이 문서가 2단계의 정본이며, 구현 계획은 이 문서에서 파생한다.

## 1. 결정 사항 (2026-09-07 사용자 확정)

| 항목 | 결정 | 근거 |
| --- | --- | --- |
| 무엇을 k3s로 | **backend · auth · cloudflared · blog-static · 도커 기반 cron 5건** | "컴퓨트 먼저, 상태는 나중" |
| DB(pgvector·market) · Redis · Neo4j | **도커 compose에 그대로** | DB는 추후 Supabase 계열 클라우드로 간다. k3s에 넣으면 이관을 두 번 한다 |
| 도커 엔진 | **남긴다**(DB·이미지 빌드). 제거는 Supabase 전환 때 | |
| n8n · uptime-kuma | 도커에 그대로 | 상태 보유, 변경 최소 |
| 맥 | **colima(docker 런타임 + k3s)** 로 Docker Desktop 교체. 볼륨은 redoceanmap 것만 이관 | 백엔드 PC와 같은 토폴로지·같은 IP 패턴 |
| 실행 | 매니페스트·스크립트·절차서는 맥에서 작성·검증. 실DB가 걸린 백엔드 PC 컷오버는 사용자 입회 실행 | |

### 비목표
- DB·Redis·Neo4j·n8n의 클러스터 이관. 도커 엔진 제거. HA·다중 노드. Helm 도입.
- 프론트(www, Vercel)·cron 중 호스트 venv 10건·백업 스크립트(`docker exec pgvector`)는 변경하지 않는다.

## 2. 토폴로지

```
백엔드 PC (WSL2, 노드 IP 192.168.20.72, docker0 172.17.0.1)

  도커 compose ─────────────────────┐    k3s (ns redocean) ──────────────────────────┐
  pgvector  127.0.0.1:5432          │    backend  hostPort 8000 @127.0.0.1 + @172.17.0.1│
            +172.17.0.1:5432 (추가) │◀───auth     hostPort 9000 @127.0.0.1 + @172.17.0.1│
  redis     +172.17.0.1:6379 (추가) │    cloudflared ──▶ backend:8000 / auth:9000 (Service)│
  neo4j     +172.17.0.1:7687 (추가) │                ──▶ 172.17.0.1:5678 (n8n, 도커)      │
  market-pg  172.17.0.1:5434 (기존) │                ──▶ blog-static:80 (Service)         │
  n8n       +172.17.0.1:5678 (추가) │───▶ host.docker.internal:8000 (워크플로 4곳)        │
  uptime-kuma ─▶ host.docker.internal:8000/9000 (모니터 2개)                             │
```

경계를 넘는 통신은 **양방향 모두 172.17.0.1**로 통일한다. market DB가 이미 쓰는 방식이며 도커가 남는 한 이 IP는 고정이다.

- **파드 → 도커**: k3s 안에 `pgvector`·`redis`·`neo4j` 이름의 **셀렉터 없는 Service + EndpointSlice**(172.17.0.1). 앱의 `@pgvector:5432`·`redis://redis:6379`·`NEO4J_URI=bolt://neo4j:7687` 연결 문자열은 변경 0. Supabase 전환 = EndpointSlice 교체.
  ExternalName은 CNAME 방식이라 IP에 쓸 수 없다.
- **도커 → 파드**: backend·auth hostPort를 172.17.0.1에도 연다. n8n·uptime-kuma compose에 `extra_hosts: host.docker.internal:host-gateway`.
- market DB와 Ollama는 1단계와 같이 `hostAliases: host.docker.internal → 172.17.0.1`.

## 3. 저장소 구조

```
k8s/
  base/
    kustomization.yaml
    backend.yaml            Deployment(replicas 1, Recreate, alembic 선실행) + Service :8000
    auth.yaml               Deployment + Service :9000 (개인키 Secret은 여기만)
    external-services.yaml  pgvector·redis·neo4j Service + EndpointSlice(172.17.0.1)
  overlays/
    dev-mac/                ns redocean-dev · hostPath /Users/jangminseok/Project/com.redoceanmap/minseok
                            · --reload · hostPort 18000/19000 · Ollama → 맥 호스트 IP(host.lima.internal)
    prod/                   ns redocean · 이미지에 구운 코드 · hostPort 8000/9000(127.0.0.1+172.17.0.1)
      cloudflared.yaml      Deployment + ConfigMap(config) — 자격증명은 Secret(secrets.sh가 만든다)
      blog-static.yaml      nginx:alpine Deployment + Service, hostPath blog_site(ro)
      cronjobs/             5건 (§5)
  secrets.sh                네임스페이스 인자화. prod에서는 cloudflared 자격증명 Secret도 만든다
  load-image.sh             docker build → (백엔드 PC) k3s ctr import. 태그 인자화(:dev / :latest)
  README.md                 설치·기동·컷오버·롤백
```

- 기존 `k8s/dev/{pgvector,redis,n8n,optional/neo4j}.yaml`은 **삭제**한다(DB는 도커 결정과 충돌). `k8s/dev`는 `base` + `overlays/dev-mac`로 재편.
- 백엔드 PC 개발 스택(1단계 대상)은 만들지 않는다. 백엔드 PC = 운영, 맥 = 개발.

### 배포 (`deploy.sh` 교체)
```
git pull origin window
docker build --build-arg GIT_SHA/BUILT_AT -t minseok97/redoceanmap-backend:latest minseok/
docker save … | sudo k3s ctr images import -
kubectl apply -k k8s/overlays/prod
kubectl -n redocean rollout restart deploy backend auth   # :latest 재반입은 재시작해야 반영
kubectl -n redocean rollout status deploy backend auth
```
"배포 = 재빌드"라는 현행 의미와 `/health`의 `version.commit` 대조는 유지. 롤백은 도커 이미지 저장소의 직전 이미지 ID를 재태그·재반입.

## 4. 도커 쪽 변경

| 파일 | 변경 |
| --- | --- |
| `docker-compose.prod.yaml` | backend·auth·cloudflared **삭제**. pgvector·redis에 `172.17.0.1:<port>` 바인딩 추가(127.0.0.1 유지). uptime-kuma에 `extra_hosts`. 이 파일이 롤백 지점(git 이전 버전 → `up -d`) |
| `docker-compose.yaml`(dev) | backend·auth 삭제. pgvector·redis·neo4j에 172.17.0.1 바인딩. 맥 colima에서도 같은 파일 |
| `minseok/apps/market/docker-compose.yml` | 무변경(이미 172.17.0.1 바인딩) |
| n8n compose(리포 밖 `/home/host/projects/n8n/`) | `172.17.0.1:5678` 바인딩 + `extra_hosts`. 절차서에만 기록 |
| 구 스택 `/home/host/projects/redoceanmap/`의 blog-static | k3s로 대체 후 `down`. 구 스택 마지막 잔재 |

## 5. cron

도커를 쓰는 6건만 바뀐다. 호스트 venv 10건과 `backup_db.sh`(`docker exec pgvector`)는 그대로.

| 현재 crontab | 이후 |
| --- | --- |
| `docker exec backend python scripts/project_graph.py` (02:15) | CronJob `project-graph` |
| `docker run … check_freshness.py --expect-commit $(git rev-parse)` (09:00) | CronJob `check-freshness` — 리포 hostPath 마운트, `.git/HEAD`→ref 파일에서 커밋 읽기(이미지에 git 없음) |
| `docker run … collect_business_permits.py` (화 05:00) | CronJob `collect-business-permits` |
| `docker exec … collect_commercial_trades.py` (매월 3일 04:30) | CronJob `collect-commercial-trades` |
| `docker run … collect_seoul_quarter.py` (수 05:30) | CronJob `collect-seoul-quarter` |
| `check_llm_health.py`의 `docker logs backend` | `kubectl logs --since=24h deploy/backend -n redocean` (호스트 venv cron 유지) |

CronJob 공통: 이미지 `:latest`(imagePullPolicy Never), `envFrom: redocean-env`, `hostAliases` 172.17.0.1, `concurrencyPolicy: Forbid`, 로그는 `kubectl logs job/…`(기존 `~/*.log` 파일은 사라진다 — `successfulJobsHistoryLimit`로 최근 3회 보관).

## 6. 맥 환경

```
brew install colima docker docker-compose kubectl
colima start --runtime docker --kubernetes --cpu 4 --memory 8 --disk 60 --network-address
```
- docker 런타임 + k3s가 **한 VM**에 있어 `docker0=172.17.0.1` 패턴이 백엔드 PC와 같다. k3s는 cri-dockerd로 도커 이미지를 직접 보므로 **맥에서는 ctr import가 불필요**(`load-image.sh`가 분기).
- MCP 테스트 러너(`docker run … pytest/lint-imports`)는 colima의 docker로 그대로 동작. 변경 없음.
- 볼륨 이관: Docker Desktop의 `comredoceanmap_pgvector_data`·`comredoceanmap_redis_data`를 tar로 내려 colima에 복원. 다른 프로젝트 볼륨은 Docker Desktop에 남긴다. **두 런타임 동시 기동 금지**(5432 충돌).
- Ollama는 맥 호스트에서 돈다. 파드에서는 `host.lima.internal`(192.168.5.2)로 닿는다 — dev-mac overlay의 `OLLAMA_HOST`.
- ⚠️ **hostPort는 Lima 포트 포워딩에 잡히지 않을 수 있다**(iptables DNAT이라 리스닝 소켓이 없다). `--network-address`로 받은 VM IP로 `http://<vm-ip>:18000` 접근을 1차로 쓰고, 안 되면 `kubectl port-forward`. 구현 첫 단계에서 스파이크로 확정한다.

## 7. 컷오버 절차 (백엔드 PC, 사용자 입회)

1. `scripts/backup_db.sh` 수동 1회. `docker volume ls`·`docker ps` 스냅샷 기록.
2. `git pull origin window`(이 작업 반영본). `k8s/secrets.sh prod`(.env·.env.auth·cloudflared 자격증명).
3. `load-image.sh latest` → containerd 반입 확인.
4. DB 쪽 포트 열기: `docker compose -f docker-compose.prod.yaml up -d pgvector redis`(재생성, 데이터 무관) · n8n compose 수정 후 `up -d` · neo4j(`--profile graph`) 재기동. `ss -ltn`으로 172.17.0.1 바인딩 확인.
5. **다운타임 시작** — `docker compose -f docker-compose.prod.yaml stop backend auth cloudflared`. 도커 backend·auth가 8000/9000을 쥐고 있어 파드 hostPort와 충돌하므로 먼저 내린다. 공개 도메인은 cloudflared 파드가 뜰 때까지 끊긴다(수 분).
6. `kubectl apply -k k8s/overlays/prod` → backend·auth Ready → `curl 127.0.0.1:8000/health`·`curl 172.17.0.1:8000/health`(도커 → 파드 경로 실측).
7. cloudflared 파드 Ready → `https://api.redoceanmap.com/health`·`auth.`·`n8n.`·`blog.` 4개 도메인 확인 → 로그인·대화·지도 스모크. **다운타임 종료.**
8. n8n 워크플로 URL 4곳 `http://backend:8000` → `http://host.docker.internal:8000`(UI에서 수정, 리포의 JSON도 갱신). uptime-kuma 모니터 2개 수정.
9. crontab 5줄 삭제, `check_llm_health.py` 갱신. `kubectl get cronjob`으로 5건 등록 확인. 다음 09:00 `check-freshness` 잡 성공 확인.
10. `docker compose … up -d --remove-orphans`는 **금지**(neo4j 삭제 위험, 기존 규칙). 대신 `docker rm redoceanmap-backend-1 redoceanmap-auth-1 redoceanmap-cloudflared-1`. 구 스택 blog-static `down`.

**롤백**(어느 단계든): `kubectl delete -k k8s/overlays/prod` → `git checkout <이전> -- docker-compose.prod.yaml` → `up -d`. DB 볼륨은 손대지 않았으므로 데이터 영향 없음. 172.17.0.1 바인딩 추가는 롤백해도 무해.

## 8. 검증 기준

| 단계 | 기준 |
| --- | --- |
| 맥 정적 | `kubectl kustomize k8s/overlays/{dev-mac,prod}` 성공 · `kubectl apply --dry-run=server` 통과 |
| 맥 동적 | colima 위 dev-mac 기동 → `/health` 200 · 로그인 → 대화 → 지도 스모크 · 파드에서 `psql -h pgvector`·`redis-cli -h redis` 성공 |
| 백엔드 PC | §7의 6·8 · 24시간 뒤 CronJob 5건 성공 이력 · `check_freshness` 이메일 정상 |
| 회귀 | 백엔드 pytest·lint-imports(MCP 도구, 변경 없음) · `pnpm run typecheck` |

## 9. 리스크·미결

- Lima 포트 포워딩과 hostPort(§6) — 스파이크로 해소.
- WSL2에서 k3s의 hostPort(portmap)와 도커 iptables 공존 — 1단계에서 k3s 설치 후 도커가 계속 돌고 있어 큰 문제는 없으나, hostIP 172.17.0.1 DNAT은 컷오버 5단계에서 실측한다.
- CronJob 로그가 `~/*.log`에서 `kubectl logs`로 바뀐다. 사용자가 로그 파일에 의존하는 습관이 있으면 hostPath 로그 마운트를 추가한다(요청 시).
- Supabase 전환 시 남는 일: EndpointSlice → ExternalName(호스트명) 교체, market DB 처리, 도커 엔진 제거(빌드를 nerdctl/buildkit로).
