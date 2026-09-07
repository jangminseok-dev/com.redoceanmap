# k8s — 쿠버네티스(k3s) 스택

도커 컴포즈를 k3s로 옮기는 작업의 매니페스트. 2026-09-07 결정: **k3s · 개발 스택 먼저**.
실운영 구 스택(`/home/host/projects/redoceanmap/`, 도커 컴포즈)은 그대로 두고 병행한다 —
실DB(:5432)·cron 15건·cloudflared는 2단계에서 옮긴다. 그때까지 도커 엔진은 남긴다(빌드·실운영용).

| 디렉토리 | 내용 |
| --- | --- |
| `dev/` | `docker-compose.yaml` 기본 프로파일 대응 — backend·auth·pgvector·redis·n8n (kustomize) |
| `dev/optional/` | `--profile graph` 대응 — neo4j. 필요할 때만 apply |

## 설치 (1회, sudo 필요)

```bash
# traefik(80/443)·servicelb는 끈다 — 전 포트 루프백 원칙(0.0.0.0 금지). 접근은 hostPort 127.0.0.1로만.
curl -sfL https://get.k3s.io | sudo sh -s - --disable traefik,servicelb --write-kubeconfig-mode 644
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml     # ~/.bashrc에 넣어 둔다
kubectl get nodes                                # Ready 확인
```

## 기동

```bash
k8s/dev/secrets.sh          # .env → redocean-env, .env.auth → redocean-auth-env(auth 전용)
k8s/dev/load-image.sh       # docker build → k3s containerd 반입(~4GB, 수 분)
kubectl apply -k k8s/dev
kubectl -n redocean-dev get pods -w
```

| 서비스 | 호스트 포트(127.0.0.1) | 실운영 도커 |
| --- | --- | --- |
| backend | 18000 | 8000 |
| auth | 19000 | 9000 |
| pgvector(개발 DB, 빈 DB에서 alembic) | 15432 | 5432 |
| redis | 16379 | 6379 |
| n8n | 15678 | 5678 |
| neo4j(선택) | 17474 / 17687 | 7474 / 7687 |

- 프론트 연결: `www/.env.local`의 `NEXT_PUBLIC_API_URL=http://127.0.0.1:18000`, `NEXT_PUBLIC_AUTH_URL=http://127.0.0.1:19000`.
- 코드는 `minseok/`를 hostPath로 마운트해 `--reload` 핫리로드가 된다. requirements 변경 때만 `load-image.sh` 재실행.
- market 전용 DB(:5434)와 Ollama(:11434)는 `host.docker.internal → 172.17.0.1`(hostAliases)로 붙는다.
  즉 개발 backend도 **실제 market DB를 읽고 쓴다**(개발용 market DB는 없다). 도커 엔진 제거 시 이 IP는 노드 IP로 바꿔야 한다.
- `.env` 값을 바꾸면 `secrets.sh` 재실행 후 `kubectl -n redocean-dev rollout restart deploy`.

## 정리

```bash
kubectl delete -k k8s/dev                        # PVC(데이터)는 남는다
kubectl -n redocean-dev delete pvc --all         # 데이터까지 지울 때 — 개발 DB뿐이지만 확인하고 실행
/usr/local/bin/k3s-uninstall.sh                  # k3s 자체 제거
```
