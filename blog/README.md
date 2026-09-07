# blog/ — 프로젝트 문서·리뷰 블로그

Jekyll 4.4 기반. 백엔드·프론트와 독립이며, 이 디렉토리 안의 파일만 사이트로 빌드된다.

```bash
cd blog
bundle install                          # 최초 1회
bundle exec jekyll serve --port 4100    # http://127.0.0.1:4100 (4000은 타 프로젝트와 충돌)
```

- 포스트: `_posts/YYYY-MM-DD-제목.markdown` — 리뷰 형식(무엇을 / 왜 / 어떻게 / 아쉬운 점)
- 빌드 산출물 `_site/`·`.jekyll-cache/`는 gitignore 처리됨 — 커밋 금지

## 카드뉴스 형식 (전 페이지 공통)

페이지 = 큰 둥근 카드들의 그리드다. 스타일은 `assets/main.scss`, 스크린샷 카드는 `_includes/card.html`.

```markdown
<div class="cn-grid">

<div class="cn-card cn-bg-dark cn-statement cn-wide">   <!-- 문구 카드 -->
  <p class="cn-label">라벨</p>
  <h2>큰 문구</h2>
  <p>설명 한 줄</p>
</div>

{% include card.html img="/assets/img/market-map.jpg" bg="sage"
   title="상권 워크스페이스" desc="지도에서 고르고 채팅으로 묻는다" %}

<div class="cn-card cn-bg-plain cn-body" markdown="1">   <!-- 텍스트/표 카드 -->
## 소제목
마크다운 내용 (`markdown="1"` 필수)
</div>

</div>
```

- 카드 배경: `cn-bg-warm`(기본) · `cn-bg-sage` · `cn-bg-dark` · `cn-bg-plain`(읽기용 흰 카드)
- 전체 폭 카드: `cn-wide` / include에는 `wide=true`
- card.html 파라미터: `img`(필수) · `title`(필수) · `desc` · `alt` · `bg`(warm/sage/dark)
- 이미지는 `assets/img/`에 두고, 캡션은 기능 나열이 아니라 **"어떤 문제를 어떤 기술로 풀었는지"** 1문장
- 이 블로그는 취업 포트폴리오 목적 — 스크린샷도 아래 민감정보 규칙을 통과해야 한다

## 공개 호스팅 — https://blog.redoceanmap.com (2026-08-28 적용 완료)

백엔드 PC의 기존 인프라를 재사용한다(비용 0원 · CI 없음). 구성:

- **빌드는 개발 기기에서** — 백엔드 PC에 Ruby를 깔지 않는다.
- **정적 서빙** — k3s `blog-static` 파드(`infra/k8s/overlays/prod/blog-static.yaml`, nginx:alpine)가
  `/home/host/projects/redoceanmap/blog_site/`를 읽기 전용 hostPath로 물고 있다. 포트 발행 없음 — cloudflared 파드가 Service로 직결.
- **라우팅** — k3s cloudflared 파드(`infra/k8s/overlays/prod/cloudflared.yaml`) ingress에 `blog.redoceanmap.com` 규칙이 있다
  (호스트 systemd판은 롤백 예비 — 건드리지 않는다). DNS CNAME도 터널에 연결되어 있다.

### 갱신 절차 (내용을 고칠 때마다)

```bash
cd blog && bundle exec jekyll build
rsync -az --delete _site/ <백엔드PC>:/home/host/projects/redoceanmap/blog_site/
```

nginx는 볼륨을 그대로 읽으므로 컨테이너 재시작이 필요 없다. 반영 확인:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://blog.redoceanmap.com/
```

### www와의 관계

`redoceanmap.com/about`은 **철거했다**(2026-08-28). 서비스 소개 내용은 이 블로그의
`about.markdown`으로 이관했고, www 쪽은 `/about` → `https://blog.redoceanmap.com/about/`
리다이렉트(`www/next.config.ts`)와 푸터·더보기 시트의 외부 링크만 남는다.
법이 요구하는 연락처는 `/privacy` 8항·`/terms` 5항에 그대로 있다.

## 민감정보 규칙

이 블로그는 외부 공개를 전제로 쓴다. 포스트·페이지에 다음을 **절대 적지 않는다**:

- API 키·토큰·비밀번호 등 `.env*`에 있는 모든 값
- DB 계정명·접속 문자열, 서버 IP·도메인 내부 경로, ssh 별칭
- 운영 포트 구성·방화벽 등 인프라 세부 (기술 스택 이름 수준까지만 허용)
- 개인정보(본인 외 실명·연락처 등)

스크린샷을 넣을 때도 터미널·브라우저에 위 값이 비치지 않는지 확인한다.
