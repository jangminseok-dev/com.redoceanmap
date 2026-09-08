---
layout: page
title: 개발 기록
nav_title: 개발 기록
permalink: /posts/
---

<div class="cn-grid">

<div class="cn-card cn-bg-dark cn-statement cn-wide">
  <p class="cn-label">개발 기록</p>
  <h2>마일스톤 하나를 끝낼 때마다<br>무엇을 · 왜 · 어떻게 · 아쉬운 점을 남깁니다</h2>
  <p>최신 글이 위에 옵니다. 기각한 실험도 결과이므로 그대로 적습니다.</p>
</div>

{% for post in site.posts %}
<a class="cn-card cn-bg-plain cn-postcard cn-wide" href="{{ post.url | relative_url }}">
  <p class="cn-postcard__meta">{{ post.date | date: "%Y.%m.%d" }} · {{ post.categories | first | default: "review" }}</p>
  <h2 class="cn-postcard__title">{{ post.title | escape }}</h2>
  <p class="cn-postcard__excerpt">{{ post.excerpt | strip_html | strip_newlines | truncate: 170 }}</p>
  <span class="cn-postcard__more">읽기 →</span>
</a>
{% endfor %}

</div>
