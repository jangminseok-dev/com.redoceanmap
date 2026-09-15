"""뉴스 라벨러 태그 — 모델 태그에서 만든다(`gemma4:e4b-it-qat` → `gemma4-e4b-it-qat`).

쓰는 쪽(scripts/label_news.py)과 읽는 쪽(stock news_pg_repository의 DEFAULT_LABELER)이 같은 규칙을
써야 모델 교체 때 라벨이 어긋나지 않는다(2026-09-15 EXAONE → Gemma 교체에서 분리 정의였던 것을 합침).
ollama 등 무거운 의존이 없어야 한다 — 라벨링 스크립트는 requests만 있는 루트 venv에서 돈다.
"""


def labeler_tag(model_tag: str) -> str:
    return model_tag.strip().replace(":", "-")[:40]  # news_labels.labeler varchar(40)
