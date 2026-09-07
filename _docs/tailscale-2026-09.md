# Tailscale 도입 절차 — 맥 ↔ 백엔드 PC를 같은 LAN 없이 잇기 (2026-09-07 작성)

## 0. 현황(실측)과 방침

| 항목 | 실측 |
| --- | --- |
| 맥 | Tailscale 1.102.3 설치·로그인 완료(`jang971121@`, IP `100.76.233.68`, 테일넷 `tail7cccce.ts.net` — `tail4ea1e9`는 공유 노드 `ubantu-kim` 쪽 이름) |
| 백엔드 PC | Windows 10 22H2 + WSL2(Ubuntu 26.04, systemd). Tailscale은 Windows·WSL 어디에도 없음 |
| 현재 LAN 접속 | 맥 `~/.ssh/config`의 `Host host` → `192.168.0.85:22`. Windows portproxy가 `0.0.0.0:22 → 192.168.20.72:22`(WSL NAT IP, 하드코딩)로 넘김 |
| WSL 네트워킹 | NAT 모드(미러 모드는 Windows 11 전용). `/dev/net/tun` 있음 |
| 서비스 바인딩 | sshd `0.0.0.0:22`, k3s API `*:6443`, DB·Redis는 `127.0.0.1` |

**방침: Tailscale을 Windows가 아니라 WSL2 안에 설치한다.**
- 테일넷이 WSL(sshd·k3s가 있는 곳)에 직접 닿는다. portproxy·WSL IP 변동과 무관해진다.
- DB(5432)·k3s API(6443)는 지금처럼 `ssh -L` 터널로만 쓴다. 테일넷에 포트를 새로 열지 않는다.
- Windows 쪽 Tailscale은 깔지 않는다(둘 다 깔면 같은 PC가 노드 2개로 잡혀 혼란).
- 무료 Personal 플랜(사용자 3명·기기 100대) 범위다.

## 1. 백엔드 PC(WSL2)에 tailscaled 설치 — 사용자 터미널에서(sudo 대화식)

```bash
ssh -t host 'curl -fsSL https://tailscale.com/install.sh | sh'
ssh -t host 'sudo tailscale up --hostname redocean-pc --accept-dns=false'
```
- 두 번째 명령이 로그인 URL을 출력한다 → 맥 브라우저에서 열어 **`jang971121@` 계정으로 승인**(맥과 같은 테일넷이어야 한다).
- `--hostname redocean-pc`: WSL 호스트명이 `host`라 그대로 두면 노드 이름이 `host`가 된다. MagicDNS 이름이 `redocean-pc.tail7cccce.ts.net`이 되게 지정.
- `--accept-dns=false`: WSL은 `/etc/resolv.conf`를 자동 생성하고 k3s CoreDNS도 그 파일을 읽는다. MagicDNS가 이 파일을 건드리면 재부팅·재생성 때 꼬인다. PC 쪽은 맥을 이름으로 찾을 일이 없으니 끈다(맥 쪽 MagicDNS는 그대로).
- 확인:
```bash
ssh host 'tailscale ip -4; tailscale status | head -3; systemctl is-enabled tailscaled'
```
`100.x.y.z` 한 줄, `enabled`. (실측 2026-09-07: `redocean-pc` = `100.91.144.44`)

**키 만료 해제(필수).** 테일넷 기본값은 노드 키 180일 만료라 반년 뒤 ssh가 조용히 끊긴다. https://login.tailscale.com/admin/machines → `redocean-pc` 우측 `…` → **Disable key expiry**.

## 2. 맥 `~/.ssh/config` 교체

```
Host host
  HostName redocean-pc          # MagicDNS — 테일넷 어디서든
  Port 22
  User host
  IdentityFile ~/.ssh/id_ed25519

Host host-lan                   # 테일넷 장애 시 예비(같은 공유기일 때만)
  HostName 192.168.0.85
  Port 22
  User host
  IdentityFile ~/.ssh/id_ed25519
```
MagicDNS 짧은 이름이 안 풀리면 `HostName 100.x.y.z`(1단계에서 받은 IP)로 쓴다. VS Code Remote-SSH·`ssh -L`·이 저장소의 `ssh host …` 명령은 전부 이 항목을 타므로 다른 수정은 없다.

## 3. 검증

```bash
ssh host 'hostname; tailscale status | head -1'            # ① 접속
ssh -L 5432:127.0.0.1:5432 host -N &                        # ② DB 터널(재부팅 전까지)
psql -h 127.0.0.1 -p 5432 -U redocean -d redoceanmap -c 'select count(*) from price_bars'
```
③ 다른 네트워크에서: 맥을 휴대폰 핫스팟에 붙이고 ①을 다시 실행. 성공하면 목표 달성.
④ (선택) 맥에서 `kubectl`로 운영 클러스터 보기:
```bash
ssh host 'cat /etc/rancher/k3s/k3s.yaml' | sed 's/name: default/name: backend-pc/; s/cluster: default/cluster: backend-pc/; s/user: default/user: backend-pc/; s/current-context: default/current-context: backend-pc/' > ~/.kube/backend-pc.yaml
ssh -L 6443:127.0.0.1:6443 host -N &
KUBECONFIG=~/.kube/backend-pc.yaml kubectl -n redocean get pods
```
(`server: https://127.0.0.1:6443`이 그대로라 터널을 통해 붙는다. `~/.kube/config`에 합치면 colima 컨텍스트와 이름이 겹치지 않게 위 sed로 이름을 바꿔 뒀다.)

## 4. 보안 정리(선택, 권장)

- **LAN 노출 축소**: Tailscale이 자리 잡으면 Windows portproxy `0.0.0.0:22`와 대응 방화벽 규칙은 지워도 된다(LAN의 다른 기기에서 sshd가 보이지 않게). 지우면 `host-lan` 예비 경로도 사라지므로 ①③이 안정된 뒤에.
  ```powershell
  netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=22
  ```
- **ACL**: 맥 `tailscale status`에 다른 사용자(`kcs8815@`)의 노드 `ubantu-kim`이 보인다. 기본 ACL은 테일넷 내 전원 상호 접속 허용이라 그 기기에서도 백엔드 PC sshd에 닿는다(키 인증은 여전히 필요). 내 기기끼리만 허용하려면 admin → Access controls에서
  ```json
  {"grants": [{"src": ["autogroup:member"], "dst": ["autogroup:self"], "ip": ["*"]}]}
  ```
  로 좁힌다. 그 노드가 공유 노드(shared)면 해당 사용자에게 공유를 끊는 편이 단순하다.

## 5. 롤백

```bash
ssh -t host 'sudo tailscale down && sudo systemctl disable --now tailscaled'
```
맥 `~/.ssh/config`의 `Host host` HostName을 `192.168.0.85`로 되돌린다. 완전 제거는 `sudo apt remove tailscale`.

## 6. 남는 한계

- WSL2가 떠 있어야 tailscaled도 산다. Windows 재부팅 후 WSL 자동 기동은 지금 k3s·DB와 같은 전제(현행 유지).
- 테일넷 IP는 노드가 살아 있는 한 고정이지만, 노드를 지우고 다시 가입하면 바뀐다. MagicDNS 이름을 쓰면 무관.
