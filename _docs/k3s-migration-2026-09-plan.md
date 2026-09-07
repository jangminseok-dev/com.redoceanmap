# k3s 전환(앱만 k3s) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** backend·auth·cloudflared·blog-static·도커 기반 cron 5건을 k3s로 옮기고, DB·Redis·Neo4j·n8n·uptime-kuma는 도커 compose에 남긴 채 양쪽을 172.17.0.1로 잇는다. 맥은 colima(docker+k3s)로 백엔드 PC와 같은 토폴로지를 갖는다.

**Architecture:** `k8s/base`(앱 Deployment + 외부 서비스 EndpointSlice) 위에 `overlays/dev-mac`·`overlays/prod`를 얹는 kustomize 구조. 파드→도커는 셀렉터 없는 Service+EndpointSlice(172.17.0.1), 도커→파드는 hostPort(127.0.0.1 + 172.17.0.1). 배포는 docker build → k3s containerd 반입 → `kubectl apply -k` → rollout restart.

**Tech Stack:** k3s v1.36(백엔드 PC, WSL2) · colima(맥, docker 런타임 + k3s) · kubectl 내장 kustomize · docker compose(DB 계층) · bash

**Spec:** `_docs/k3s-migration-2026-09.md`

## Global Constraints

- 전 포트 루프백 원칙: hostPort의 hostIP는 `127.0.0.1` 또는 `172.17.0.1`만. `0.0.0.0` 금지.
- 백엔드 이미지는 `imagePullPolicy: Never`(로컬 반입만). 태그: 개발 `:dev`, 운영 `:latest`.
- 네임스페이스: 개발 `redocean-dev`, 운영 `redocean`.
- JWT 개인키 Secret `redocean-auth-env`는 auth 파드에만 붙인다. backend·CronJob에 절대 붙이지 않는다.
- 연결 문자열 호스트명은 변경 없음: `pgvector:5432`, `redis:6379`, `neo4j:7687`, `n8n:5678`.
- `docker compose … --remove-orphans` 금지(기존 규칙 — neo4j 삭제 위험).
- 실DB·도커 볼륨을 건드리는 명령은 사용자 입회(Task 10)에서만 실행한다. 맥 세션에서는 백엔드 PC를 **읽기만** 한다.
- 커밋은 각 태스크 끝에 **사용자 확인 후** 한다(프로젝트 규칙). 메시지는 `type(scope): 요약` 한국어.
- 문서·주석은 한국어. 기존 파일 스타일을 따르고 무관한 줄은 건드리지 않는다.
- 백엔드 검증은 MCP 도구(`run_backend_tests`, `run_import_linter`) 또는 `docker run … pytest`(변경 없음).

---

## 파일 구조

| 경로 | 책임 |
| --- | --- |
| `k8s/base/kustomization.yaml` | base 리소스 목록 + 비밀 아닌 런타임 env ConfigMap 생성 |
| `k8s/base/backend.yaml` | backend Deployment + Service |
| `k8s/base/auth.yaml` | auth Deployment + Service |
| `k8s/base/external-services.yaml` | pgvector·redis·neo4j·n8n Service + EndpointSlice(172.17.0.1) |
| `k8s/overlays/dev-mac/` | ns redocean-dev, hostPath, --reload, 포트 18000/19000, Ollama→맥 호스트, market DB 없음 |
| `k8s/overlays/prod/` | ns redocean, 포트 8000/9000 이중 hostIP, LOG_FORMAT=json, cloudflared, blog-static, cronjobs/ |
| `k8s/overlays/prod/cronjobs/` | CronJob 5건 |
| `k8s/secrets.sh` | .env/.env.auth(/cloudflared) → Secret. 네임스페이스 인자 |
| `k8s/load-image.sh` | docker build → (k3s 바이너리 있으면) ctr import. 태그 인자 |
| `k8s/README.md` | 설치·기동·컷오버·롤백 정본 |
| `deploy.sh` | 백엔드 PC 1커맨드 배포(k3s판) |
| `docker-compose.yaml` / `docker-compose.prod.yaml` | DB 계층만 남긴 compose |
| `minseok/scripts/check_llm_health.py` | `docker logs` → `kubectl logs` |
| `minseok/apps/hub/_docs/n8n_*_workflow.json` | `backend:8000` → `host.docker.internal:8000` |
| 삭제: `k8s/dev/` 전체 | base/overlay로 대체 |

---

### Task 1: 맥 colima 전환 + 접근 경로 스파이크

**Files:**
- 없음(맥 환경 작업). 결과는 Task 9의 `k8s/README.md`에 기록한다.

**Interfaces:**
- Produces: 맥에 `docker`(colima 컨텍스트)·`kubectl`(colima 컨텍스트) 동작. 결정값 2개 — ① 맥에서 파드 hostPort에 닿는 주소(`127.0.0.1` 또는 colima VM IP), ② 파드에서 맥 Ollama에 닿는 호스트명(`host.lima.internal`). 이 값이 Task 4의 `OLLAMA_HOST`와 `www/.env.local`에 들어간다.

- [ ] **Step 1: Docker Desktop 볼륨 2개를 tar로 내린다(Docker Desktop이 켜진 상태에서)**

```bash
mkdir -p ~/redoceanmap-volumes
for v in comredoceanmap_pgvector_data comredoceanmap_redis_data; do
  docker run --rm -v "$v":/v -v ~/redoceanmap-volumes:/backup alpine \
    tar czf "/backup/$v.tgz" -C /v .
done
ls -la ~/redoceanmap-volumes
```
Expected: `.tgz` 2개. pgvector 쪽이 수백 MB.

- [ ] **Step 2: Docker Desktop 종료 + 자동 시작 해제**

Docker Desktop 메뉴 → Quit. Settings의 "Start Docker Desktop when you sign in" 해제. **삭제하지 않는다**(다른 프로젝트 볼륨 보존).
Run: `docker info 2>&1 | head -1` → Expected: 데몬 연결 실패 메시지(꺼졌음).

- [ ] **Step 3: colima·docker CLI·compose 설치**

```bash
brew install colima docker docker-compose
mkdir -p ~/.docker
cat ~/.docker/config.json 2>/dev/null
```
`~/.docker/config.json`에 compose 플러그인 경로를 넣는다(없으면 새로 만든다, 있으면 키만 추가):
```json
{ "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"] }
```
Run: `docker compose version` → Expected: `Docker Compose version v2.x`

- [ ] **Step 4: colima 기동(docker 런타임 + k3s)**

```bash
colima start --runtime docker --kubernetes --cpu 4 --memory 6 --disk 60 --network-address
docker context use colima
kubectl config use-context colima
kubectl get nodes
docker info --format '{{.ServerVersion}}'
colima ls -j | python3 -c 'import json,sys; print(json.load(sys.stdin)["ip_address"])'
```
Expected: 노드 `colima` Ready. 마지막 줄이 VM IP(예: `192.168.106.2`) — 메모해 둔다.

- [ ] **Step 5: 볼륨 복원**

```bash
for v in comredoceanmap_pgvector_data comredoceanmap_redis_data; do
  docker volume create "$v"
  docker run --rm -v "$v":/v -v ~/redoceanmap-volumes:/backup alpine \
    tar xzf "/backup/$v.tgz" -C /v
done
docker volume ls | grep comredoceanmap
```
Expected: 볼륨 2개.

- [ ] **Step 6: 스파이크 ① — hostPort 접근 주소**

```bash
kubectl run spike --image=nginx:alpine --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"spike","image":"nginx:alpine","ports":[{"containerPort":80,"hostPort":18999,"hostIP":"127.0.0.1"}]}]}}'
kubectl wait --for=condition=Ready pod/spike --timeout=60s
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:18999/        # (a)
VMIP=$(colima ls -j | python3 -c 'import json,sys; print(json.load(sys.stdin)["ip_address"])')
curl -s -o /dev/null -w '%{http_code}\n' http://$VMIP:18999/            # (b)
```
판정: (a)가 200이면 **주소 = 127.0.0.1**. (a) 실패·(b) 200이면 **주소 = VM IP**(hostIP를 `0.0.0.0`으로 바꾸지 않는다 — VM 안이라 LAN 노출이 아니지만 원칙 유지; 대신 (b)도 실패하면 hostIP를 VM IP로 다시 시험: overrides의 `"hostIP":"<VMIP>"`). 둘 다 실패면 `kubectl port-forward pod/spike 18999:80`으로 우회하고 README에 기록.

- [ ] **Step 7: 스파이크 ② — 파드 → 맥 Ollama**

```bash
kubectl run ocheck --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s --max-time 5 http://host.lima.internal:11434/
```
Expected: `Ollama is running`. 실패하면 맥 Ollama가 127.0.0.1에만 묶인 것(실측 확인됨). 해제:
```bash
launchctl setenv OLLAMA_HOST 0.0.0.0
# 메뉴바 Ollama Quit → 재실행 후
lsof -nP -iTCP:11434 -sTCP:LISTEN
```
Expected: `*:11434`. 다시 위 curl → `Ollama is running`.

- [ ] **Step 8: 스파이크 정리**

```bash
kubectl delete pod spike --ignore-not-found
```
결정값 2개(hostPort 주소, Ollama 호스트명)를 다음 태스크에 넘긴다. 커밋 대상 없음.

---

### Task 2: compose를 DB 계층만 남기도록 축소

**Files:**
- Modify: `docker-compose.yaml` (backend·auth 삭제, 172.17.0.1 바인딩)
- Modify: `docker-compose.prod.yaml` (backend·auth·cloudflared 삭제, 172.17.0.1 바인딩, uptime-kuma extra_hosts, external 볼륨·네트워크 정리)

**Interfaces:**
- Produces: 도커 서비스 `pgvector`(5432)·`redis`(6379)·`neo4j`(7687)·`n8n`(5678)이 `172.17.0.1`에도 리스닝. Task 3의 EndpointSlice가 이 주소를 가리킨다.

- [ ] **Step 1: 검증 명령 먼저 확인(현재 통과)**

Run: `docker compose -f docker-compose.yaml config --services && docker compose -f docker-compose.prod.yaml config --services`
Expected: 두 목록 모두 `backend`·`auth` 포함(변경 전 기준선).

- [ ] **Step 2: `docker-compose.yaml` 수정**

`backend:`·`auth:` 서비스 블록 전체 삭제. 나머지 서비스에 바인딩 추가:
```yaml
  n8n:
    image: docker.n8n.io/n8nio/n8n
    ports:
      - "127.0.0.1:5678:5678"
      - "172.17.0.1:5678:5678"   # k3s 파드(backend → n8n 웹훅, cloudflared)용 — 도커 브리지 게이트웨이
```
```yaml
  redis:
    ports:
      - "127.0.0.1:6379:6379"
      - "172.17.0.1:6379:6379"   # k3s 파드용
```
```yaml
  pgvector:
    ports:
      - "127.0.0.1:5432:5432"
      - "172.17.0.1:5432:5432"   # k3s 파드용 — market compose와 같은 방식
```
```yaml
  neo4j:
    ports:
      - "127.0.0.1:7474:7474"
      - "127.0.0.1:7687:7687"
      - "172.17.0.1:7687:7687"   # k3s 파드(bolt)용
```
파일 상단에 한 줄 주석 추가: `# 앱(backend·auth)은 k3s로 갔다(k8s/). 이 파일은 DB 계층(상태)만 띄운다 — _docs/k3s-migration-2026-09.md`

- [ ] **Step 3: `docker-compose.prod.yaml` 수정**

- 머리말 주석의 "dev와의 차이"·"전환 절차" 문단은 두고, 맨 위에 추가: `# 2026-09 k3s 전환 — backend·auth·cloudflared는 k8s/overlays/prod로 갔다. 여기는 DB 계층 + uptime-kuma만.`
- `backend:`·`auth:`·`cloudflared:` 서비스 블록 삭제. `networks: n8n:` 블록 삭제(cloudflared만 쓰던 것).
- `redis`·`pgvector`에 dev와 같은 `172.17.0.1` 바인딩 추가(주석 포함).
- `uptime-kuma`에 추가:
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"   # 모니터 대상이 k3s 파드(hostPort 172.17.0.1)로 옮겨감
```
- `volumes:`의 `redis_data`·`pgvector_data` external 선언은 그대로(데이터 승계).

- [ ] **Step 4: 검증**

Run: `docker compose -f docker-compose.yaml config --services; docker compose -f docker-compose.prod.yaml config --services`
Expected: dev → `n8n redis pgvector neo4j pgadmin`, prod → `redis pgvector uptime-kuma`. `backend`·`auth`·`cloudflared` 없음.
Run: `docker compose -f docker-compose.prod.yaml config | grep -A3 'published: "5432"'`
Expected: `host_ip: 127.0.0.1`과 `host_ip: 172.17.0.1` 두 항목.

- [ ] **Step 5: 맥에서 DB 계층 기동 + 접속 확인**

```bash
docker compose up -d pgvector redis
docker compose ps
docker exec comredoceanmap-pgvector-1 psql -U "$(grep ^POSTGRES_USER= .env | cut -d= -f2)" -d "$(grep ^POSTGRES_DB= .env | cut -d= -f2)" -c 'select count(*) from alembic_version'
```
Expected: 컨테이너 2개 Up, 쿼리가 1행 반환(복원된 볼륨).

- [ ] **Step 6: 커밋(사용자 확인 후)**

```bash
git add docker-compose.yaml docker-compose.prod.yaml
git commit -m "chore(compose): 앱 서비스 제거·DB 계층만 유지 — k3s 파드용 172.17.0.1 바인딩"
```

---

### Task 3: `k8s/base` — 앱 Deployment + 외부 서비스

**Files:**
- Create: `k8s/base/kustomization.yaml`, `k8s/base/backend.yaml`, `k8s/base/auth.yaml`, `k8s/base/external-services.yaml`
- Delete: `k8s/dev/` 전체(`kustomization.yaml`·`namespace.yaml`·`backend.yaml`·`auth.yaml`·`pgvector.yaml`·`redis.yaml`·`n8n.yaml`·`optional/neo4j.yaml`·`secrets.sh`·`load-image.sh`) — 스크립트 2개는 Task 7에서 `k8s/`로 옮겨 다시 만든다

**Interfaces:**
- Consumes: Secret `redocean-env`(루트 .env 전체, 키 `POSTGRES_USER`·`POSTGRES_PASSWORD`·`POSTGRES_DB`·`MARKET_DATABASE_URL_DOCKER` 포함), Secret `redocean-auth-env`(.env.auth) — Task 7의 `secrets.sh`가 만든다.
- Produces: Deployment `backend`·`auth`, Service `backend:8000`·`auth:9000`·`pgvector:5432`·`redis:6379`·`neo4j:7687`·`n8n:5678`, ConfigMap `redocean-runtime`(키 `OLLAMA_HOST`·`REDIS_URL`·`N8N_EMAIL_WEBHOOK_URL`·`AWS_DEFAULT_REGION`·`VISION_S3_BUCKET`·`REDIS_URL_MOBILE`). 컨테이너 이름 `backend`·`auth`, 볼륨 없음(overlay가 붙인다).

- [ ] **Step 1: 기존 dev 디렉토리 제거**

```bash
git rm -r k8s/dev
mkdir -p k8s/base
```

- [ ] **Step 2: `k8s/base/kustomization.yaml`**

```yaml
# 앱 계층 base — backend·auth + 도커에 남은 상태 계층(pgvector·redis·neo4j·n8n)으로의 경로.
# 네임스페이스·포트·코드 마운트·이미지 태그는 overlays/가 정한다. 설계: _docs/k3s-migration-2026-09.md
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - external-services.yaml
  - backend.yaml
  - auth.yaml
configMapGenerator:
  # 비밀이 아닌 런타임 값 — compose의 environment: 블록에서 옮겨왔다. 비밀은 Secret(redocean-env).
  - name: redocean-runtime
    literals:
      - OLLAMA_HOST=http://host.docker.internal:11434
      - REDIS_URL=redis://redis:6379/0
      - REDIS_URL_MOBILE=redis://redis:6379/1
      - N8N_EMAIL_WEBHOOK_URL=http://n8n:5678/webhook/redocean-email
      - AWS_DEFAULT_REGION=ap-northeast-2
      - VISION_S3_BUCKET=redoceanmap.com-752767405178-ap-northeast-2-an
generatorOptions:
  disableNameSuffixHash: true   # overlay가 이름으로 참조·병합한다
```

- [ ] **Step 3: `k8s/base/external-services.yaml`**

```yaml
# 도커 compose에 남은 상태 계층으로 가는 길 — 셀렉터 없는 Service + EndpointSlice(도커 브리지 게이트웨이).
# Service 이름 = compose 서비스 이름이라 앱의 연결 문자열(@pgvector:5432 등)이 그대로 동작한다.
# ExternalName은 CNAME 방식이라 IP에 쓸 수 없다. Supabase 전환 시 이 파일만 교체한다.
apiVersion: v1
kind: Service
metadata:
  name: pgvector
spec:
  ports:
    - port: 5432
---
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: pgvector-1
  labels:
    kubernetes.io/service-name: pgvector
addressType: IPv4
ports:
  - port: 5432
    protocol: TCP
endpoints:
  - addresses: ["172.17.0.1"]
    conditions:
      ready: true
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  ports:
    - port: 6379
---
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: redis-1
  labels:
    kubernetes.io/service-name: redis
addressType: IPv4
ports:
  - port: 6379
    protocol: TCP
endpoints:
  - addresses: ["172.17.0.1"]
    conditions:
      ready: true
---
apiVersion: v1
kind: Service
metadata:
  name: neo4j
spec:
  ports:
    - port: 7687
---
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: neo4j-1
  labels:
    kubernetes.io/service-name: neo4j
addressType: IPv4
ports:
  - port: 7687
    protocol: TCP
endpoints:
  - addresses: ["172.17.0.1"]
    conditions:
      ready: true
---
apiVersion: v1
kind: Service
metadata:
  name: n8n
spec:
  ports:
    - port: 5678
---
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: n8n-1
  labels:
    kubernetes.io/service-name: n8n
addressType: IPv4
ports:
  - port: 5678
    protocol: TCP
endpoints:
  - addresses: ["172.17.0.1"]
    conditions:
      ready: true
```

- [ ] **Step 4: `k8s/base/backend.yaml`**

```yaml
# backend — 마이그레이션(alembic)은 backend 단독 소유(auth와 이중 실행 경합 방지). replicas 1 · Recreate 고정.
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: backend
  ports:
    - port: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      # market DB(:5434)·Ollama(:11434)는 호스트에 있다 — 도커 브리지 게이트웨이로. 도커가 남는 한 이 IP는 고정.
      hostAliases:
        - ip: 172.17.0.1
          hostnames: ["host.docker.internal"]
      containers:
        - name: backend
          image: minseok97/redoceanmap-backend:latest
          imagePullPolicy: Never   # load-image.sh로 반입한 로컬 이미지만(허브 pull 금지)
          command: ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
          envFrom:
            - secretRef:
                name: redocean-env        # 루트 .env 전체(비밀)
            - configMapRef:
                name: redocean-runtime    # 비밀 아닌 런타임 값
          env:
            # $(VAR)는 envFrom으로 들어온 값으로 전개된다(kubelet이 envFrom을 먼저 처리)
            - name: DATABASE_URL
              value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@pgvector:5432/$(POSTGRES_DB)
            - name: MARKET_DATABASE_URL          # market 전용 DB(:5434) — 호스트 도커
              value: $(MARKET_DATABASE_URL_DOCKER)
          ports:
            - containerPort: 8000
              hostPort: 8000
              hostIP: 127.0.0.1
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15    # alembic + 앱 기동 여유
            periodSeconds: 10
```

- [ ] **Step 5: `k8s/base/auth.yaml`**

```yaml
# auth — backend와 같은 이미지·다른 엔트리포인트. JWT 개인키(.env.auth → redocean-auth-env)는 이 파드에만(발급 경계).
apiVersion: v1
kind: Service
metadata:
  name: auth
spec:
  selector:
    app: auth
  ports:
    - port: 9000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth
spec:
  replicas: 1
  selector:
    matchLabels:
      app: auth
  template:
    metadata:
      labels:
        app: auth
    spec:
      containers:
        - name: auth
          image: minseok97/redoceanmap-backend:latest
          imagePullPolicy: Never
          # 마이그레이션은 backend 소유 — 여기서는 돌리지 않는다
          command: ["uvicorn", "auth_main:app", "--host", "0.0.0.0", "--port", "9000"]
          envFrom:
            - secretRef:
                name: redocean-env
            - secretRef:
                name: redocean-auth-env   # auth 전용 — JWT_PRIVATE_KEY_B64
            - configMapRef:
                name: redocean-runtime
          env:
            - name: DATABASE_URL
              value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@pgvector:5432/$(POSTGRES_DB)
          ports:
            - containerPort: 9000
              hostPort: 9000
              hostIP: 127.0.0.1
          readinessProbe:
            httpGet:
              path: /health
              port: 9000
            initialDelaySeconds: 10
            periodSeconds: 10
```

- [ ] **Step 6: 정적 검증**

Run: `kubectl kustomize k8s/base | grep -E '^kind:|^  name:' | paste - - | sort | uniq -c`
Expected: Deployment 2, Service 6, EndpointSlice 4, ConfigMap 1. 오류 없음.
Run: `kubectl kustomize k8s/base | kubectl apply --dry-run=server -f - -n default`
Expected: 13개 리소스 `created (server dry run)`. (EndpointSlice의 Service 포트 이름 불일치 등은 여기서 잡힌다.)

- [ ] **Step 7: 커밋(사용자 확인 후)**

```bash
git add -A k8s/
git commit -m "feat(k8s): base — backend·auth Deployment + 도커 상태 계층 EndpointSlice(pgvector·redis·neo4j·n8n)"
```

---

### Task 4: `overlays/dev-mac` + 맥 실기동 스모크

**Files:**
- Create: `k8s/overlays/dev-mac/kustomization.yaml`, `k8s/overlays/dev-mac/namespace.yaml`, `k8s/overlays/dev-mac/backend-patch.yaml`, `k8s/overlays/dev-mac/auth-patch.yaml`
- Create(임시, 이 태스크 안에서만): `k8s/secrets.sh`·`k8s/load-image.sh`는 Task 7에서 만든다. 이 태스크는 그 두 스크립트의 **최종본**을 먼저 만들어 쓴다 — Task 7의 Step 1·2 코드를 그대로 여기서 작성하고, Task 7에서는 `deploy.sh`만 남긴다. (순서상 스크립트가 먼저 필요하기 때문이다.)

**Interfaces:**
- Consumes: Task 1의 결정값(hostPort 주소, Ollama 호스트명 `host.lima.internal`), Task 3의 base.
- Produces: `kubectl apply -k k8s/overlays/dev-mac`로 맥에서 backend(18000)·auth(19000) 기동.

- [ ] **Step 1: `k8s/secrets.sh`(Task 7 Step 1의 코드와 동일 — 여기서 작성)**

```bash
#!/usr/bin/env bash
# 루트 .env / .env.auth → k3s Secret. 값은 디스크에 남기지 않고 kubectl로만 넘긴다.
#   redocean-env       ← .env      (backend·auth·CronJob 공용)
#   redocean-auth-env  ← .env.auth (auth 전용 — JWT 개인키 발급 경계, backend에는 절대 붙이지 않는다)
#   cloudflared-credentials ← 터널 자격증명 JSON (운영, 3번째 인자를 줄 때만)
# 사용: k8s/secrets.sh <namespace> [cloudflared-credentials.json 경로]
#   개발(맥):     k8s/secrets.sh redocean-dev
#   운영(백엔드 PC): k8s/secrets.sh redocean /home/host/.cloudflared/4b03c4a0-3030-4710-9d74-592c7860acbf.json
# 재실행 = 갱신(apply). 값을 바꾼 뒤엔 파드 재시작: kubectl -n <ns> rollout restart deploy
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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
```
`chmod +x k8s/secrets.sh`. (1단계의 NEO4J_AUTH 파생 주입은 neo4j가 도커에 남으므로 삭제.)

- [ ] **Step 2: `k8s/load-image.sh`(Task 7 Step 2의 코드와 동일 — 여기서 작성)**

```bash
#!/usr/bin/env bash
# 백엔드 이미지를 docker로 빌드해 k3s에 넣는다.
#   백엔드 PC(k3s 네이티브, containerd): docker build → docker save | k3s ctr images import
#   맥(colima docker 런타임): k3s가 cri-dockerd로 도커 이미지를 직접 보므로 build만 하면 끝
# 사용: k8s/load-image.sh <tag> [namespace]
#   맥:       k8s/load-image.sh dev redocean-dev
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
```
`chmod +x k8s/load-image.sh`.

- [ ] **Step 3: overlay 파일 4개**

`k8s/overlays/dev-mac/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: redocean-dev
```

`k8s/overlays/dev-mac/kustomization.yaml`:
```yaml
# 맥 개발 스택(colima docker+k3s). DB 계층은 같은 VM의 도커 compose(루트 docker-compose.yaml).
# 기동: k8s/secrets.sh redocean-dev && k8s/load-image.sh dev && kubectl apply -k k8s/overlays/dev-mac
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: redocean-dev
resources:
  - namespace.yaml
  - ../../base
images:
  - name: minseok97/redoceanmap-backend
    newTag: dev            # 운영 :latest와 분리 — 재빌드가 운영 태그를 덮지 않게
configMapGenerator:
  - name: redocean-runtime
    behavior: merge
    literals:
      - OLLAMA_HOST=http://host.lima.internal:11434   # Ollama는 맥 호스트에서 돈다(VM 밖) — Task 1 스파이크 ②
      - WATCHFILES_FORCE_POLLING=true                 # virtiofs 마운트는 inotify가 안 온다 — --reload를 폴링으로
generatorOptions:
  disableNameSuffixHash: true
patches:
  - path: backend-patch.yaml
  - path: auth-patch.yaml
```

`k8s/overlays/dev-mac/backend-patch.yaml`(strategic merge — `env`는 name, `ports`는 containerPort로 병합된다):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  template:
    spec:
      containers:
        - name: backend
          command: ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"]
          env:
            - name: ENV
              value: development
            - name: MARKET_DATABASE_URL   # 맥에는 market 전용 DB가 없다 — 메인 DB 폴백(기존 맥 개발 동작과 동일)
              $patch: delete
          ports:
            - containerPort: 8000
              hostPort: 18000            # 백엔드 PC 운영(8000)과 구분되는 1만 번대
              hostIP: 127.0.0.1
          volumeMounts:
            - name: src
              mountPath: /app
      volumes:
        - name: src
          hostPath:
            path: /Users/jangminseok/Project/com.redoceanmap/minseok   # colima가 $HOME을 VM에 같은 경로로 마운트
            type: Directory
```

`k8s/overlays/dev-mac/auth-patch.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth
spec:
  template:
    spec:
      containers:
        - name: auth
          command: ["uvicorn", "auth_main:app", "--host", "0.0.0.0", "--port", "9000", "--reload"]
          env:
            - name: ENV
              value: development
          ports:
            - containerPort: 9000
              hostPort: 19000
              hostIP: 127.0.0.1
          volumeMounts:
            - name: src
              mountPath: /app
      volumes:
        - name: src
          hostPath:
            path: /Users/jangminseok/Project/com.redoceanmap/minseok
            type: Directory
```
Task 1 스파이크 ①의 결론이 "VM IP"였다면 두 패치의 `hostIP`를 `127.0.0.1` 대신 그 VM IP로 쓰고 주석에 이유를 적는다.

- [ ] **Step 4: 정적 검증**

Run: `kubectl kustomize k8s/overlays/dev-mac > /tmp/dev-mac.yaml && grep -c 'namespace: redocean-dev' /tmp/dev-mac.yaml && grep -n 'MARKET_DATABASE_URL\|hostPort\|newTag\|:dev' /tmp/dev-mac.yaml`
Expected: namespace 13회. `MARKET_DATABASE_URL` **0건**(삭제 패치 적용). hostPort 18000·19000. 이미지 `:dev`.

- [ ] **Step 5: 맥 실기동**

```bash
k8s/secrets.sh redocean-dev
k8s/load-image.sh dev
kubectl apply -k k8s/overlays/dev-mac
kubectl -n redocean-dev get pods -w     # backend·auth 1/1 Running까지 (alembic 포함 ~1분)
```
Expected: 파드 2개 Ready. 실패 시 `kubectl -n redocean-dev logs deploy/backend`.

- [ ] **Step 6: 경로 3종 실측**

```bash
ADDR=127.0.0.1   # Task 1 결정값
curl -s http://$ADDR:18000/health | head -c 300; echo
curl -s http://$ADDR:19000/health | head -c 300; echo
kubectl -n redocean-dev exec deploy/backend -- sh -c 'echo "$DATABASE_URL" | sed "s#:[^:@]*@#:<pw>@#"'
kubectl -n redocean-dev exec deploy/backend -- python -c "import redis,os; print(redis.from_url(os.environ['REDIS_URL']).ping())"
kubectl -n redocean-dev exec deploy/backend -- python -c "import urllib.request,os; print(urllib.request.urlopen(os.environ['OLLAMA_HOST']).read()[:20])"
```
Expected: `/health` 2개 200 JSON. DATABASE_URL이 `@pgvector:5432/`로 **전개**되어 있음(`$(POSTGRES_USER)` 문자열이 남아 있으면 envFrom 전개 실패 — 그 경우 `env:`에 `POSTGRES_USER`·`POSTGRES_PASSWORD`·`POSTGRES_DB`를 `valueFrom.secretKeyRef`로 명시하고 재검증). Redis `True`. Ollama `b'Ollama is running'`.

- [ ] **Step 7: 프론트 스모크**

`www/.env.local`(untracked)의 `NEXT_PUBLIC_API_URL=http://<ADDR>:18000`, `NEXT_PUBLIC_AUTH_URL=http://<ADDR>:19000`로 맞춘 뒤 `cd www && pnpm run dev`. 브라우저에서 로그인 → 대화 1턴 → `/market` 지도 로드.
Expected: 3개 동작. 대화는 EXAONE 응답(호스트 Ollama 경유).

- [ ] **Step 8: 핫리로드 확인**

`minseok/main.py`에 공백 한 줄 추가·저장 → `kubectl -n redocean-dev logs deploy/backend --tail=5`에 `Reloading...`. 확인 후 변경 되돌리기(`git checkout minseok/main.py`).

- [ ] **Step 9: 커밋(사용자 확인 후)**

```bash
git add k8s/overlays/dev-mac k8s/secrets.sh k8s/load-image.sh
git commit -m "feat(k8s): dev-mac overlay + secrets/load-image 스크립트 — colima 위 개발 스택 기동 검증"
```

---

### Task 5: `overlays/prod` — 앱 + cloudflared + blog-static

**Files:**
- Create: `k8s/overlays/prod/kustomization.yaml`, `namespace.yaml`, `backend-patch.yaml`, `auth-patch.yaml`, `hostport-docker-bridge.json`, `cloudflared.yaml`, `blog-static.yaml`

**Interfaces:**
- Consumes: base(Task 3), Secret `cloudflared-credentials`(키 `credentials.json`, Task 4의 `secrets.sh` 3번째 인자), 백엔드 PC 경로 `/home/host/projects/redoceanmap/blog_site`.
- Produces: ns `redocean`에 backend(8000@127.0.0.1+172.17.0.1)·auth(9000 동일)·cloudflared·blog-static. Task 6의 cronjobs/가 이 kustomization에 붙는다.

- [ ] **Step 1: namespace·kustomization**

`k8s/overlays/prod/namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: redocean
```
`k8s/overlays/prod/kustomization.yaml`:
```yaml
# 백엔드 PC 운영. 코드는 이미지에 구워져 있다(배포 = 재빌드, deploy.sh). DB 계층은 docker-compose.prod.yaml.
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: redocean
resources:
  - namespace.yaml
  - ../../base
  - cloudflared.yaml
  - blog-static.yaml
  - cronjobs
patches:
  - path: backend-patch.yaml
  - path: auth-patch.yaml
  # 도커 컨테이너(n8n·uptime-kuma)가 host.docker.internal:8000/9000으로 파드에 닿도록 브리지 게이트웨이에도 hostPort를 연다.
  # strategic merge는 ports를 containerPort로 병합해 같은 8000을 두 개 못 만든다 — JSON patch로 추가.
  - path: hostport-docker-bridge.json
    target:
      kind: Deployment
      name: backend
  - path: hostport-docker-bridge-auth.json
    target:
      kind: Deployment
      name: auth
```
(`cronjobs` 디렉토리는 Task 6에서 만든다. 이 태스크의 검증은 임시로 그 줄을 빼고 돌린 뒤 Task 6에서 복원한다 — 또는 빈 `cronjobs/kustomization.yaml`(`resources: []`)을 먼저 만든다. **빈 kustomization을 먼저 만든다.**)

`k8s/overlays/prod/cronjobs/kustomization.yaml`(임시):
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources: []
```

- [ ] **Step 2: 앱 패치**

`k8s/overlays/prod/backend-patch.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
spec:
  template:
    spec:
      containers:
        - name: backend
          env:
            - name: ENV
              value: production
            - name: LOG_FORMAT      # 구조화 로깅(③-M4) — kubectl logs에서 필드 검색
              value: json
```
`k8s/overlays/prod/auth-patch.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth
spec:
  template:
    spec:
      containers:
        - name: auth
          env:
            - name: ENV
              value: production
            - name: LOG_FORMAT
              value: json
```
`k8s/overlays/prod/hostport-docker-bridge.json`:
```json
[
  { "op": "add", "path": "/spec/template/spec/containers/0/ports/-",
    "value": { "containerPort": 8000, "hostPort": 8000, "hostIP": "172.17.0.1" } }
]
```
`k8s/overlays/prod/hostport-docker-bridge-auth.json`:
```json
[
  { "op": "add", "path": "/spec/template/spec/containers/0/ports/-",
    "value": { "containerPort": 9000, "hostPort": 9000, "hostIP": "172.17.0.1" } }
]
```

- [ ] **Step 3: `k8s/overlays/prod/cloudflared.yaml`**

```yaml
# 공개 접점. 구 config-docker.yml의 ingress를 옮겼다 — backend·auth·blog-static은 k3s Service, n8n은 도커(EndpointSlice 경유).
# 자격증명은 Secret cloudflared-credentials(secrets.sh 3번째 인자). 호스트 ~/.cloudflared/config.yml(systemd 롤백 예비)은 건드리지 않는다.
apiVersion: v1
kind: ConfigMap
metadata:
  name: cloudflared-config
data:
  config.yml: |
    tunnel: 4b03c4a0-3030-4710-9d74-592c7860acbf
    credentials-file: /etc/cloudflared/creds/credentials.json
    ingress:
      - hostname: api.redoceanmap.com
        service: http://backend:8000
      - hostname: n8n.redoceanmap.com
        service: http://n8n:5678
      - hostname: auth.redoceanmap.com
        service: http://auth:9000
      - hostname: blog.redoceanmap.com
        service: http://blog-static:80
      - service: http_status:404
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudflared
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cloudflared
  template:
    metadata:
      labels:
        app: cloudflared
    spec:
      containers:
        - name: cloudflared
          image: cloudflare/cloudflared:latest   # compose와 동일(부동 태그 — 터널 클라이언트는 최신 유지가 관례)
          args: ["tunnel", "--config", "/etc/cloudflared/config.yml", "--no-autoupdate", "run"]
          volumeMounts:
            - name: config
              mountPath: /etc/cloudflared/config.yml
              subPath: config.yml
            - name: creds
              mountPath: /etc/cloudflared/creds
              readOnly: true
          livenessProbe:
            httpGet:
              path: /ready
              port: 2000
            initialDelaySeconds: 20
            periodSeconds: 30
      volumes:
        - name: config
          configMap:
            name: cloudflared-config
        - name: creds
          secret:
            secretName: cloudflared-credentials
```
(`/ready`는 cloudflared 기본 metrics 포트가 켜져 있을 때만 응답한다. `args`에 `--metrics 0.0.0.0:2000`을 `run` 앞에 추가한다: `["tunnel", "--config", "/etc/cloudflared/config.yml", "--no-autoupdate", "--metrics", "0.0.0.0:2000", "run"]`. 파드 안 포트라 LAN 노출 아님.)

- [ ] **Step 4: `k8s/overlays/prod/blog-static.yaml`**

```yaml
# 블로그 정적 서빙 — 구 스택(/home/host/projects/redoceanmap)의 blog-static(nginx:alpine)을 대체. 갱신은 blog/README.md의 rsync 절차.
apiVersion: v1
kind: Service
metadata:
  name: blog-static
spec:
  selector:
    app: blog-static
  ports:
    - port: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: blog-static
spec:
  replicas: 1
  selector:
    matchLabels:
      app: blog-static
  template:
    metadata:
      labels:
        app: blog-static
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
          volumeMounts:
            - name: site
              mountPath: /usr/share/nginx/html
              readOnly: true
      volumes:
        - name: site
          hostPath:
            path: /home/host/projects/redoceanmap/blog_site   # 기존 rsync 대상 그대로(옮기지 않는다)
            type: Directory
```

- [ ] **Step 5: 정적 검증(맥)**

Run: `kubectl kustomize k8s/overlays/prod > /tmp/prod.yaml && grep -n 'hostIP\|hostPort' /tmp/prod.yaml`
Expected: backend에 `8000/127.0.0.1`과 `8000/172.17.0.1`, auth에 `9000` 두 쌍.
Run: `kubectl apply --dry-run=server -k k8s/overlays/prod`
Expected: 전부 `created (server dry run)`. 중복 containerPort를 API가 거부하면(에러 문구에 `ports` 포함) 대안: JSON patch를 `replace`로 바꿔 hostIP `172.17.0.1` **하나만** 두고, 백엔드 PC 로컬 접근은 `curl 172.17.0.1:8000`으로 문서화(README·컷오버 절차의 `127.0.0.1:8000` 표기를 같이 고친다).

- [ ] **Step 6: 커밋(사용자 확인 후)**

```bash
git add k8s/overlays/prod
git commit -m "feat(k8s): prod overlay — backend·auth 이중 hostPort, cloudflared·blog-static 파드화"
```

---

### Task 6: CronJob 5건

**Files:**
- Create: `k8s/overlays/prod/cronjobs/kustomization.yaml`(Task 5의 임시본 교체), `project-graph.yaml`, `check-freshness.yaml`, `collect-business-permits.yaml`, `collect-commercial-trades.yaml`, `collect-seoul-quarter.yaml`

**Interfaces:**
- Consumes: Secret `redocean-env`, ConfigMap `redocean-runtime`, 이미지 `:latest`, 백엔드 PC 리포 `/home/host/projects/com.redoceanmap`.
- Produces: ns `redocean`의 CronJob 5개(이름 = 파일명). Task 10에서 crontab 5줄을 이것으로 대체.

- [ ] **Step 1: kustomization**

```yaml
# crontab의 도커 기반 5건을 옮겼다. 스케줄·환경은 crontab과 동일. 호스트 venv cron 10건·backup_db.sh는 crontab에 그대로.
# 수동 실행: kubectl -n redocean create job --from=cronjob/<이름> <이름>-manual-$(date +%s)
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - project-graph.yaml
  - check-freshness.yaml
  - collect-business-permits.yaml
  - collect-commercial-trades.yaml
  - collect-seoul-quarter.yaml
```

- [ ] **Step 2: `project-graph.yaml`(구 `docker exec redoceanmap-backend-1 python scripts/project_graph.py`, 02:15)**

```yaml
# PG(market) → Neo4j 그래프 투영. 상권 뉴스 수집(01:30) 뒤 · 뉴스 라벨링(02:30) 앞. 전량 MERGE 멱등.
apiVersion: batch/v1
kind: CronJob
metadata:
  name: project-graph
spec:
  schedule: "15 2 * * *"
  timeZone: Asia/Seoul
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 0
      template:
        spec:
          restartPolicy: Never
          hostAliases:
            - ip: 172.17.0.1
              hostnames: ["host.docker.internal"]
          containers:
            - name: job
              image: minseok97/redoceanmap-backend:latest
              imagePullPolicy: Never
              workingDir: /app
              command: ["python", "scripts/project_graph.py"]
              envFrom:
                - secretRef:
                    name: redocean-env
                - configMapRef:
                    name: redocean-runtime
              env:
                - name: DATABASE_URL
                  value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@pgvector:5432/$(POSTGRES_DB)
                - name: MARKET_DATABASE_URL
                  value: $(MARKET_DATABASE_URL_DOCKER)
```

- [ ] **Step 3: `collect-commercial-trades.yaml`(구 `docker exec … collect_commercial_trades.py`, 매월 3일 04:30)**

위 project-graph.yaml과 동일 구조로, 바뀌는 곳만:
```yaml
metadata:
  name: collect-commercial-trades
spec:
  schedule: "30 4 3 * *"
  ...
              command: ["python", "scripts/collect_commercial_trades.py"]
```
(주석: `# 상업용 부동산 실거래 수집 — 최근 3개월. 인허가(화)·분기(수)와 요일 분산.`)

- [ ] **Step 4: `collect-business-permits.yaml`(구 `docker run --network host -v repo:/work -w /work/minseok …`, 화 05:00)**

리포 코드를 hostPath로 실행하던 형태를 유지한다(이미지 코드가 아니라 체크아웃 코드):
```yaml
# 인허가 업소 수집 — 주 1회(개업·폐업은 분기 팩트보다 느리게 변한다). 683 요청·약 10분.
apiVersion: batch/v1
kind: CronJob
metadata:
  name: collect-business-permits
spec:
  schedule: "0 5 * * 2"
  timeZone: Asia/Seoul
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 0
      template:
        spec:
          restartPolicy: Never
          hostAliases:
            - ip: 172.17.0.1
              hostnames: ["host.docker.internal"]
          containers:
            - name: job
              image: minseok97/redoceanmap-backend:latest
              imagePullPolicy: Never
              workingDir: /work/minseok
              command: ["python", "scripts/collect_business_permits.py"]
              envFrom:
                - secretRef:
                    name: redocean-env
                - configMapRef:
                    name: redocean-runtime
              env:
                - name: DATABASE_URL
                  value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@pgvector:5432/$(POSTGRES_DB)
                - name: MARKET_DATABASE_URL
                  value: $(MARKET_DATABASE_URL_DOCKER)
              volumeMounts:
                - name: repo
                  mountPath: /work
                  readOnly: true
          volumes:
            - name: repo
              hostPath:
                path: /home/host/projects/com.redoceanmap
                type: Directory
```

- [ ] **Step 5: `collect-seoul-quarter.yaml`(구 `docker run … -w /work -e PYTHONPATH=/work/minseok:/work/minseok/apps --env-file .env … python minseok/scripts/collect_seoul_quarter.py`, 수 05:30)**

Step 4와 동일 구조, 바뀌는 곳:
```yaml
metadata:
  name: collect-seoul-quarter
spec:
  schedule: "30 5 * * 3"
  ...
              workingDir: /work
              command: ["python", "minseok/scripts/collect_seoul_quarter.py"]
              env:
                - name: PYTHONPATH
                  value: /work/minseok:/work/minseok/apps
                - name: DATABASE_URL
                  value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@pgvector:5432/$(POSTGRES_DB)
                - name: MARKET_DATABASE_URL
                  value: $(MARKET_DATABASE_URL_DOCKER)
```
(주석: `# 상권 신규 분기 자동 적재(③-M5) — 주 1회 폴링, 신규 없으면 no-op. 미공개 분기 INFO-200은 정상.`)

- [ ] **Step 6: `check-freshness.yaml`(구 `docker run … -w /work/minseok … check_freshness.py --expect-commit "$(git rev-parse --short HEAD)"`, 09:00)**

이미지에 git이 없으므로 `.git`에서 HEAD 커밋을 셸로 읽는다(브랜치 ref 또는 packed-refs, detached HEAD도 처리). `GIT_SHA`(이미지에 구운 값)와 비교하는 로직은 스크립트 안에 있다.
```yaml
# 수집 신선도 감시 + 배포 드리프트(실행 중 GIT_SHA vs 체크아웃 HEAD). 이메일 알림(ALERT_EMAIL).
# 리포 코드를 마운트해 실행 — 이미지가 낡아도 감시 코드는 최신이어야 한다(crontab 시절과 동일).
apiVersion: batch/v1
kind: CronJob
metadata:
  name: check-freshness
spec:
  schedule: "0 9 * * *"
  timeZone: Asia/Seoul
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 0
      template:
        spec:
          restartPolicy: Never
          hostAliases:
            - ip: 172.17.0.1
              hostnames: ["host.docker.internal"]
          containers:
            - name: job
              image: minseok97/redoceanmap-backend:latest
              imagePullPolicy: Never
              workingDir: /work/minseok
              command:
                - sh
                - -c
                - |
                  set -e
                  head=$(cat /work/.git/HEAD)
                  case "$head" in
                    ref:*) ref=${head#ref: }
                           commit=$(cat "/work/.git/$ref" 2>/dev/null || grep " $ref\$" /work/.git/packed-refs | cut -c1-40) ;;
                    *)     commit=$head ;;
                  esac
                  exec python scripts/check_freshness.py --expect-commit "$(printf %s "$commit" | cut -c1-7)"
              envFrom:
                - secretRef:
                    name: redocean-env
                - configMapRef:
                    name: redocean-runtime
              env:
                - name: DATABASE_URL
                  value: postgresql://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@pgvector:5432/$(POSTGRES_DB)
                - name: MARKET_DATABASE_URL
                  value: $(MARKET_DATABASE_URL_DOCKER)
              volumeMounts:
                - name: repo
                  mountPath: /work
                  readOnly: true
          volumes:
            - name: repo
              hostPath:
                path: /home/host/projects/com.redoceanmap
                type: Directory
```

- [ ] **Step 7: 검증(맥)**

Run: `kubectl kustomize k8s/overlays/prod | grep -E '^kind: CronJob' | wc -l; kubectl kustomize k8s/overlays/prod | grep -E 'schedule:'`
Expected: 5. 스케줄 5개가 crontab 원문과 일치(`15 2 * * *`, `0 9 * * *`, `0 5 * * 2`, `30 4 3 * *`, `30 5 * * 3`).
Run: `kubectl apply --dry-run=server -k k8s/overlays/prod`
Expected: 전부 통과(CronJob의 `timeZone` 포함).
셸 조각 단독 검증(맥 리포에서):
```bash
head=$(cat .git/HEAD); ref=${head#ref: }; commit=$(cat ".git/$ref" 2>/dev/null || grep " $ref\$" .git/packed-refs | cut -c1-40); printf %s "$commit" | cut -c1-7; git rev-parse --short HEAD
```
Expected: 두 줄이 같다.

- [ ] **Step 8: 커밋(사용자 확인 후)**

```bash
git add k8s/overlays/prod/cronjobs
git commit -m "feat(k8s): 도커 기반 cron 5건을 CronJob으로 — 스케줄·환경 동일, 배포 드리프트 감시는 .git에서 HEAD 판독"
```

---

### Task 7: `deploy.sh`(k3s판)

**Files:**
- Modify: `deploy.sh` (전면 교체)
- (Task 4에서 이미 만든 `k8s/secrets.sh`·`k8s/load-image.sh`는 여기서 손대지 않는다)

**Interfaces:**
- Consumes: `k8s/load-image.sh latest redocean`, `k8s/overlays/prod`.
- Produces: 백엔드 PC에서 `./deploy.sh` 1커맨드 배포.

- [ ] **Step 1: `deploy.sh` 교체**

```bash
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
```

- [ ] **Step 2: 검증**

Run: `bash -n deploy.sh && bash -n k8s/secrets.sh && bash -n k8s/load-image.sh`
Expected: 출력 없음(문법 통과). 실행은 백엔드 PC 컷오버(Task 10)에서.

- [ ] **Step 3: 커밋(사용자 확인 후)**

```bash
git add deploy.sh
git commit -m "chore(deploy): compose 재빌드 → k3s 반입·apply·rollout으로 교체"
```

---

### Task 8: 도커 이름 참조 정리 — `check_llm_health.py`, n8n 워크플로 JSON, 스크립트 docstring

**Files:**
- Modify: `minseok/scripts/check_llm_health.py:143-148`
- Modify: `minseok/apps/hub/_docs/n8n_bookmark_alert_workflow.json`(1곳), `minseok/apps/hub/_docs/n8n_realtime_alert_workflow.json`(2곳)
- Modify: docstring의 실행 예시 — `minseok/scripts/check_freshness.py:18-23`, `collect_commercial_trades.py:12-17`, `collect_business_permits.py:18`, `collect_seoul_quarter.py:27-31`, `project_graph.py`(실행 예시가 있으면)

- [ ] **Step 1: `check_llm_health.py`**

기존:
```python
_WARN_MARK = "컨텍스트 창"
_BACKEND_CONTAINER = "redoceanmap-backend-1"


def runtime_context_warnings() -> list[str]:
    logs = _cmd(["docker", "logs", "--since", "24h", _BACKEND_CONTAINER])
```
변경:
```python
_WARN_MARK = "컨텍스트 창"
# backend는 k3s 파드(ns redocean). 이 스크립트는 호스트 venv cron에서 돌아 KUBECONFIG가 없으므로 경로를 명시한다.
_KUBECONFIG = "/etc/rancher/k3s/k3s.yaml"
_BACKEND_DEPLOY = "deploy/backend"


def runtime_context_warnings() -> list[str]:
    logs = _cmd([
        "kubectl", "--kubeconfig", _KUBECONFIG, "-n", "redocean",
        "logs", "--since=24h", _BACKEND_DEPLOY,
    ])
```
Run: `docker run --rm -v "$PWD":/work -w /work minseok97/redoceanmap-backend:dev python -m py_compile minseok/scripts/check_llm_health.py && echo ok`
Expected: `ok`. 실동작은 Task 10 Step 9.

- [ ] **Step 2: n8n 워크플로 JSON**

```bash
grep -n 'backend:8000' minseok/apps/hub/_docs/n8n_*.json
sed -i '' 's#http://backend:8000#http://host.docker.internal:8000#g' \
  minseok/apps/hub/_docs/n8n_bookmark_alert_workflow.json \
  minseok/apps/hub/_docs/n8n_realtime_alert_workflow.json
grep -c 'host.docker.internal:8000' minseok/apps/hub/_docs/n8n_bookmark_alert_workflow.json minseok/apps/hub/_docs/n8n_realtime_alert_workflow.json
python3 -m json.tool minseok/apps/hub/_docs/n8n_bookmark_alert_workflow.json > /dev/null && python3 -m json.tool minseok/apps/hub/_docs/n8n_realtime_alert_workflow.json > /dev/null && echo json-ok
```
Expected: 앞 grep 3건 → sed 뒤 `backend:8000` 0건, 카운트 1·2, `json-ok`. (n8n 인스턴스의 실제 워크플로는 Task 10 Step 8에서 UI로 수정.)

- [ ] **Step 3: 스크립트 docstring의 실행 예시**

각 파일에서 `docker exec redoceanmap-backend-1 python scripts/X.py` / `docker run … minseok97/redoceanmap-backend:latest python …X.py` 줄을 아래 형태로 바꾼다(주변 설명 문장은 그대로):
```
    kubectl -n redocean create job --from=cronjob/<cronjob-이름> <cronjob-이름>-manual-$(date +%s)
    # 즉시 실행(옵션이 필요하면 CronJob의 command를 그대로 kubectl run으로): k8s/overlays/prod/cronjobs/<파일>.yaml
```
대응: check_freshness → `check-freshness`, collect_commercial_trades → `collect-commercial-trades`, collect_business_permits → `collect-business-permits`, collect_seoul_quarter → `collect-seoul-quarter`, project_graph → `project-graph`. crontab 예시 줄(`30 4 3 * * docker exec …`)은 `# 스케줄은 k8s/overlays/prod/cronjobs/<파일>.yaml`로 바꾼다.
Run: `grep -rn 'docker exec redoceanmap-backend-1\|docker run .*redoceanmap-backend:latest' minseok/scripts/*.py`
Expected: 0건. (`calibrate_game_symbols.py`·`collect_disclosures.py`·`dump_chat_eval_snapshot.py`는 수동 실행용 `docker run` 예시라 **그대로 둔다** — 맥 도커로 여전히 유효.)

- [ ] **Step 4: 회귀**

MCP `run_backend_tests`(skip_integration=true) + `run_import_linter`.
Expected: 통과(변경이 스크립트·문서뿐이라 기존과 동일).

- [ ] **Step 5: 커밋(사용자 확인 후)**

```bash
git add minseok/scripts/check_llm_health.py minseok/scripts/check_freshness.py minseok/scripts/collect_commercial_trades.py minseok/scripts/collect_business_permits.py minseok/scripts/collect_seoul_quarter.py minseok/scripts/project_graph.py minseok/apps/hub/_docs/n8n_bookmark_alert_workflow.json minseok/apps/hub/_docs/n8n_realtime_alert_workflow.json
git commit -m "fix(scripts,hub): 도커 컨테이너 이름 참조 제거 — kubectl logs·CronJob 실행 예시·n8n 웹훅 대상 host.docker.internal"
```

---

### Task 9: 문서 — `k8s/README.md`, `CLAUDE.md`, `README.md`, `blog/README.md`, `.env.example`

**Files:**
- Modify: `k8s/README.md`(전면 교체), `CLAUDE.md:130-175`(명령어 절)·`CLAUDE.md` 주의사항의 "도커 스택이 2벌 공존한다" 항목, `README.md:66-82`(실행 절), `blog/README.md:44-56`, `.env.example`(MARKET_DATABASE_URL_DOCKER 주석)

- [ ] **Step 1: `k8s/README.md` 전면 교체**

내용(절 구성 고정):
1. 한 줄 요약 + 설계 문서 링크(`_docs/k3s-migration-2026-09.md`).
2. **토폴로지 표**: 도커(pgvector·market-pgvector·redis·neo4j·n8n·uptime-kuma) / k3s(backend·auth·cloudflared·blog-static·CronJob 5). 경계 IP 172.17.0.1 설명 2줄.
3. **디렉토리 표**: `base/`·`overlays/dev-mac/`·`overlays/prod/`·`overlays/prod/cronjobs/`·`secrets.sh`·`load-image.sh`.
4. **맥 설치**(Task 1의 명령 그대로: brew install, config.json, colima start 플래그, docker context/kubectl context) + Task 1 스파이크 결과(hostPort 접근 주소, Ollama `launchctl setenv OLLAMA_HOST 0.0.0.0` 필요 여부) + Docker Desktop 병행 금지.
5. **맥 기동**: `docker compose up -d pgvector redis` → `k8s/secrets.sh redocean-dev` → `k8s/load-image.sh dev` → `kubectl apply -k k8s/overlays/dev-mac` → `www/.env.local` 포트. 포트 표(18000/19000/5432/6379).
6. **백엔드 PC 설치**(1단계 README의 k3s 설치 명령 유지) + **배포** `./deploy.sh`.
7. **컷오버 절차** — 스펙 §7의 10단계를 명령어 단위로(Task 10 Step 1~10과 동일 내용).
8. **롤백** — `kubectl delete -k k8s/overlays/prod` → `git checkout <컷오버 직전 커밋> -- docker-compose.prod.yaml` → `docker compose -f docker-compose.prod.yaml up -d` → cloudflared 컨테이너판 복귀 확인. DB 볼륨 무접촉.
9. **운영 명령**: 로그 `kubectl -n redocean logs deploy/backend --since=1h`, CronJob 수동 실행, Secret 갱신 후 `rollout restart`.
10. **정리**: `kubectl delete -k …`, `k3s-uninstall.sh`, `colima delete`.

- [ ] **Step 2: `CLAUDE.md` 명령어 절**

`docker compose up -d` 블록의 주석을 "DB 계층만(pgvector·redis·n8n; neo4j·pgadmin은 profile)"로 고치고, 1단계가 넣은 3줄(`# 쿠버네티스(k3s) 개발 스택 …`, `kubectl apply -k k8s/dev`)을 아래로 교체:
```bash
# 앱(backend·auth)은 k3s — 맥은 colima(docker+k3s). 설치·기동·컷오버·롤백은 k8s/README.md
k8s/secrets.sh redocean-dev && k8s/load-image.sh dev && kubectl apply -k k8s/overlays/dev-mac
# backend:18000 · auth:19000 (127.0.0.1) · 코드 hostPath 핫리로드
```
"마이그레이션은 `docker compose up` 시 backend 컨테이너가 …" 줄 → "마이그레이션은 backend 파드가 기동 시 `alembic upgrade head`로 자동 적용한다(auth는 돌리지 않는다)."
주의사항의 "**도커 스택이 2벌 공존한다.**" 항목 → "**도커는 DB 계층, k3s는 앱.** 백엔드 PC 운영 DB(`redoceanmap-pgvector-1` :5432, `market-pgvector` :5434)는 도커 compose 소유. 앱은 `kubectl -n redocean`. 이 저장소 compose도 :5432를 바인딩하므로 맥에서는 colima 컨텍스트에서만 올린다. 볼륨 삭제·`down -v`·스키마 파괴 명령은 사용자 확인 없이 실행하지 않는다."
CLAUDE.md는 200줄 권고를 넘어 있다 — 늘리지 않는다(교체만).

- [ ] **Step 3: `README.md` 실행 절**

```bash
docker compose up -d pgvector redis                       # DB 계층(도커)
kubectl apply -k k8s/overlays/dev-mac                     # 앱(k3s) — 사전: k8s/secrets.sh redocean-dev, k8s/load-image.sh dev
cd www && pnpm run dev                                    # 프론트(:3000) — NEXT_PUBLIC_API_URL=http://127.0.0.1:18000
```
스택 표의 "인프라" 행: `온프레미스(앱 k3s · DB 도커 compose, 루프백 바인딩) · cloudflared 터널 · 일일 백업 cron`. 검증 절(docker run … pytest)은 그대로.

- [ ] **Step 4: `blog/README.md` 공개 호스팅 절**

"실운영 compose(리포 밖)의 `blog-static` 서비스(nginx:alpine)" → "k3s `blog-static` 파드(`k8s/overlays/prod/blog-static.yaml`, nginx:alpine)가 `/home/host/projects/redoceanmap/blog_site/`를 읽기 전용 hostPath로 물고 있다. cloudflared 파드 ingress에 `blog.redoceanmap.com` 규칙." rsync 대상 `<백엔드PC>:/home/host/projects/redoceanmap/blog_site/`로 명시. "컨테이너판 cloudflared" 문구 → "k3s cloudflared 파드".

- [ ] **Step 5: `.env.example`**

`MARKET_DATABASE_URL_DOCKER` 주석의 "컨테이너에서는" → "k3s 파드·CronJob에서는(host.docker.internal → 172.17.0.1)". 키 추가·삭제 없음.

- [ ] **Step 6: 검증**

Run: `grep -rn 'k8s/dev\b' CLAUDE.md README.md k8s/ blog/README.md`
Expected: 0건(옛 경로 없음).
Run: `grep -n 'docker compose up' CLAUDE.md README.md`
Expected: DB 계층 설명이 붙은 줄만.

- [ ] **Step 7: 커밋(사용자 확인 후)**

```bash
git add k8s/README.md CLAUDE.md README.md blog/README.md .env.example
git commit -m "docs: k3s 전환 반영 — k8s/README 정본(설치·컷오버·롤백), CLAUDE/README 명령어, blog 호스팅"
```

---

### Task 10: 백엔드 PC 컷오버(사용자 입회 — 이 태스크는 사용자가 백엔드 PC에서 실행하거나, 사용자 허락 하에 `ssh host`로 실행한다)

**Files:** 없음(운영 작업). 리포 밖 파일 2개를 고친다: `/home/host/projects/n8n/docker-compose.yaml`, crontab.

**사전 조건:** Task 2~9가 window 브랜치에 push되어 있다. 백엔드 PC `git status` clean.

- [ ] **Step 1: 안전망**

```bash
cd /home/host/projects/com.redoceanmap && git status --short && git log --oneline -1
minseok/scripts/backup_db.sh                     # 수동 1회, 마지막 줄 "검증 완료" 확인
docker ps --format '{{.Names}}\t{{.Ports}}' > ~/cutover-before.txt; docker volume ls >> ~/cutover-before.txt
git rev-parse --short HEAD > ~/cutover-rollback-commit.txt   # 롤백 시 compose 복원 기준 (pull 전 커밋)
```

- [ ] **Step 2: 코드·Secret·이미지**

```bash
git pull origin window
k8s/secrets.sh redocean /home/host/.cloudflared/4b03c4a0-3030-4710-9d74-592c7860acbf.json
k8s/load-image.sh latest
sudo k3s ctr images ls -q | grep redoceanmap-backend:latest
```
Expected: secrets ok 3개, import ok.

- [ ] **Step 3: DB 계층 포트 열기(데이터 무관 — 컨테이너 재생성만)**

```bash
docker compose -f docker-compose.prod.yaml up -d pgvector redis          # 172.17.0.1 바인딩 추가
docker compose --profile graph up -d neo4j                                # 7687 브리지 바인딩
```
`/home/host/projects/n8n/docker-compose.yaml`의 n8n 서비스에 추가 후 `docker compose up -d`:
```yaml
    ports:
      - "127.0.0.1:5678:5678"
      - "172.17.0.1:5678:5678"    # k3s cloudflared·backend 파드용
    extra_hosts:
      - "host.docker.internal:host-gateway"   # 워크플로가 backend 파드(hostPort 172.17.0.1:8000)를 부른다
```
검증: `ss -ltn | grep 172.17.0.1` → 5432·6379·7687·5678·5434 다섯 포트.

- [ ] **Step 4: 사전 dry-run**

```bash
kubectl apply --dry-run=server -k k8s/overlays/prod
```
Expected: 오류 없음. 여기까지는 서비스 무중단.

- [ ] **Step 5: 다운타임 시작 — 도커 앱 정지**

```bash
docker compose -f docker-compose.prod.yaml stop backend auth cloudflared
```
(`docker compose` 프로젝트 정의에서 이미 빠진 서비스라 `stop`이 "no such service"를 내면 `docker stop redoceanmap-backend-1 redoceanmap-auth-1 redoceanmap-cloudflared-1`.)

- [ ] **Step 6: apply + 파드 확인**

```bash
kubectl apply -k k8s/overlays/prod
kubectl -n redocean get pods -w        # backend·auth·cloudflared·blog-static Running/Ready
curl -s 127.0.0.1:8000/health | python3 -m json.tool | grep -E '"status"|commit'
curl -s 172.17.0.1:8000/health -o /dev/null -w '%{http_code}\n'     # 도커 → 파드 경로
curl -s 127.0.0.1:9000/health -o /dev/null -w '%{http_code}\n'
kubectl -n redocean exec deploy/backend -- python -c "import redis,os; print(redis.from_url(os.environ['REDIS_URL']).ping())"
```
Expected: 200·200·200, commit = `git rev-parse --short HEAD`, Redis True. `/health`의 의존성 항목(DB·market DB)이 ok.

- [ ] **Step 7: 다운타임 종료 — 공개 도메인**

```bash
for h in api auth n8n blog; do printf '%s ' $h; curl -s -o /dev/null -w '%{http_code}\n' https://$h.redoceanmap.com/$( [ $h = api ] || [ $h = auth ] && echo health ); done
kubectl -n redocean logs deploy/cloudflared --tail=20      # "Registered tunnel connection" 확인
```
Expected: api 200 · auth 200 · n8n 200(또는 로그인 리다이렉트 3xx) · blog 200. 브라우저에서 redoceanmap.com 로그인 → 대화 1턴 → 지도.

- [ ] **Step 8: n8n·uptime-kuma 대상 수정**

- n8n UI(https://n8n.redoceanmap.com): 워크플로 "북마크 알림"·"실시간 알림"의 HTTP Request 노드 URL `http://backend:8000/…` → `http://host.docker.internal:8000/…`(3곳). 각 워크플로 "Test workflow"로 200 확인.
- uptime-kuma(ssh 포워딩 `http://127.0.0.1:3001`): 모니터 `http://backend:8000/health` → `http://host.docker.internal:8000/health`, `http://auth:9000/health` → `http://host.docker.internal:9000/health`. 상태 Up 확인.

- [ ] **Step 9: crontab·LLM 건강검진**

`crontab -e`에서 다음 5줄(및 그 직전 설명 주석) 삭제: `15 2 * * * docker exec …project_graph.py`, `0 9 * * * docker run …check_freshness.py`, `0 5 * * 2 docker run …collect_business_permits.py`, `30 4 3 * * docker exec …collect_commercial_trades.py`, `30 5 * * 3 docker run …collect_seoul_quarter.py`.
```bash
crontab -l | grep -c docker                       # Expected: 0 (backup_db.sh는 내부에서 docker exec — crontab 줄에는 docker 없음)
kubectl -n redocean get cronjob                   # 5개
kubectl -n redocean create job --from=cronjob/check-freshness check-freshness-manual-$(date +%s)
kubectl -n redocean wait --for=condition=complete job -l job-name --timeout=300s 2>/dev/null; kubectl -n redocean logs -l job-name --tail=30
cd minseok && ../venv/bin/python scripts/check_llm_health.py && tail -3 ~/check_llm_health.log
```
Expected: check-freshness 잡 완료, 로그에 "배포 커밋 불일치" 없음. check_llm_health가 kubectl 로그를 읽어 정상 종료(오류 없음).

- [ ] **Step 10: 도커 잔재 정리(`--remove-orphans` 금지)**

```bash
docker rm redoceanmap-backend-1 redoceanmap-auth-1 redoceanmap-cloudflared-1
docker compose -f /home/host/projects/redoceanmap/docker-compose.yaml stop blog-static && docker rm redoceanmap-blog-static-1
docker ps --format '{{.Names}}\t{{.Ports}}'
```
Expected: pgvector·market-pgvector·redis·neo4j·n8n·uptime-kuma 6개만. 구 스택 디렉토리는 삭제하지 않는다(blog_site가 그 안에 있다).

- [ ] **Step 11: 24시간 관찰 후 마감**

다음날 `kubectl -n redocean get jobs`에서 `project-graph`·`check-freshness` 성공, uptime-kuma Up 지속, `~/backup_db.log` 04:00 정상. 이후 `git push origin window` + `mac`·`main` 동기화는 사용자 요청 시.

---

## Self-Review

**Spec coverage**
- §1 결정(앱만 k3s, DB 도커, colima, 실행 분리) → Task 1·2·3·10. ✔
- §2 토폴로지(EndpointSlice 4종, hostPort 이중, extra_hosts, hostAliases) → Task 3·5·2·10 Step 3. ✔
- §3 구조(base/overlays/cronjobs/secrets/load-image/README, dev 삭제, deploy.sh) → Task 3·4·5·6·7·9. ✔
- §4 compose 변경(prod·dev·n8n 리포 밖·구 스택 blog-static) → Task 2·10. ✔
- §5 cron 6건 → Task 6(5건)·8(check_llm_health). ✔
- §6 맥(colima 플래그, 볼륨 이관, Ollama, hostPort 리스크) → Task 1·4. ✔
- §7 컷오버 10단계 → Task 10 Step 1~10(순서 동일). ✔
- §8 검증 기준 → Task 3·4·5·6 정적/동적, Task 8 Step 4 회귀, Task 10 Step 6~11. ✔
- §9 리스크: Lima hostPort(Task 1 Step 6), WSL2 DNAT(Task 10 Step 6 `172.17.0.1:8000` 실측), CronJob 로그(README 운영 명령). ✔

**Placeholder scan**: "TBD/TODO/적절히/나중에" 없음. Task 5 Step 3의 metrics 플래그는 본문에 최종 args를 명시했다.

**Type/name consistency**: Secret `redocean-env`·`redocean-auth-env`·`cloudflared-credentials`(키 `credentials.json`), ConfigMap `redocean-runtime`, 네임스페이스 `redocean-dev`/`redocean`, 이미지 태그 `dev`/`latest`, CronJob 이름 5개(Task 6 ↔ Task 8 docstring ↔ Task 10) 일치. `secrets.sh <ns> [cred]`·`load-image.sh <tag> [ns]` 시그니처가 Task 4·7·9·10에서 동일.
