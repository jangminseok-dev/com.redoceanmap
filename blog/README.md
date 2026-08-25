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

## 공개 호스팅 계획 — blog.redoceanmap.com (백엔드 PC 작업)

블로그는 아직 로컬 전용이다. 공개는 **백엔드 PC의 기존 인프라 재사용**으로 한다
(비용 0원 · CI 불필요). 절차:

1. **빌드는 개발 기기에서** — 백엔드 PC에 Ruby를 깔지 않는다.
   `cd blog && bundle exec jekyll build` 후 `_site/`를 백엔드 PC로 복사(rsync/scp).
   받는 위치 예: 실운영 스택 디렉토리(`/home/host/projects/redoceanmap/`) 아래 `blog_site/`.
2. **정적 서빙 컨테이너** — 실운영 compose(리포 밖)에 추가:
   ```yaml
   blog-static:
     image: nginx:alpine
     volumes:
       - ./blog_site:/usr/share/nginx/html:ro
     # 포트 발행 불필요 — cloudflared가 같은 도커 네트워크에서 접근
   ```
3. **cloudflared 라우트** — 운영 중인 **컨테이너판** cloudflared 설정에 ingress 추가
   (호스트 systemd판은 롤백 예비 — 건드리지 않는다):
   `blog.redoceanmap.com → http://blog-static:80`
   + Cloudflare 대시보드에서 `blog` CNAME(터널) 레코드 추가.
4. **확인** — `https://blog.redoceanmap.com` 접속, 5페이지·이미지 렌더 확인.
5. **이후** — www `/about`에 "개발 기록 보기 →" 링크 카드 추가(별도 작업, main push 시 Vercel 배포).

갱신 흐름: 블로그 수정 → 로컬 빌드 → `_site/` 재복사. (자동화가 필요해지면 cron이 아니라
수동 스크립트 한 줄로 유지 — 과설계 방지.)

## 민감정보 규칙

이 블로그는 외부 공개를 전제로 쓴다. 포스트·페이지에 다음을 **절대 적지 않는다**:

- API 키·토큰·비밀번호 등 `.env*`에 있는 모든 값
- DB 계정명·접속 문자열, 서버 IP·도메인 내부 경로, ssh 별칭
- 운영 포트 구성·방화벽 등 인프라 세부 (기술 스택 이름 수준까지만 허용)
- 개인정보(본인 외 실명·연락처 등)

스크린샷을 넣을 때도 터미널·브라우저에 위 값이 비치지 않는지 확인한다.
