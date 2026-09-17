from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from mail.app.ports.output.moderation_port import ModerationPort

logger = logging.getLogger(__name__)

# 학습 산출물: scripts/train_moderation_v1.py → models/moderation/kcelectra-unsmile-v1
_MODEL_DIR = Path(__file__).resolve().parents[4].parent / "models" / "moderation" / "kcelectra-unsmile-v1"

_pipeline = None  # 프로세스 전역 1회 로드 (110M 모델)


def _load():
    global _pipeline
    if _pipeline is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(_MODEL_DIR)
        model = AutoModelForSequenceClassification.from_pretrained(_MODEL_DIR)
        model.eval()
        labels = json.loads((_MODEL_DIR / "labels.json").read_text())

        def predict(text: str) -> dict[str, float]:
            enc = tokenizer(text, truncation=True, max_length=128, return_tensors="pt")
            with torch.no_grad():
                probs = model(**enc).logits.sigmoid()[0]
            return {label: round(float(p), 4) for label, p in zip(labels, probs)}

        _pipeline = predict
        logger.info("[moderation] KcELECTRA v1 로드 완료: %s", _MODEL_DIR)
    return _pipeline


class KcElectraModerationAdapter(ModerationPort):
    """KcELECTRA-base + Unsmile 파인튜닝 v1 — 라벨 10종 멀티라벨 점수.

    CPU 추론(밀리초 단위, 110M). 무거운 로드는 첫 호출 때 1회.
    """

    async def moderate(self, text: str) -> dict[str, float]:
        # 모델 산출물이 없으면(학습 전·이미지 미포함) 검열을 건너뛰고 빈 점수 — 메일 수신 자체가 500으로 죽었다
        # (2026-09-17 운영 로그: /automation/mail 매 호출 OSError). 빈 점수는 watcher가 "미검사 통과"로 기록한다.
        if not (_MODEL_DIR / "labels.json").exists():
            logger.warning("[moderation] 모델 없음 — 검열 생략: %s (scripts/train_moderation_v1.py로 학습)", _MODEL_DIR)
            return {}
        predict = await asyncio.to_thread(_load)
        return await asyncio.to_thread(predict, text)
