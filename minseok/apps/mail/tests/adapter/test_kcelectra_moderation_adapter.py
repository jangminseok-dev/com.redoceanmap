from mail.adapter.outbound.ai import kcelectra_moderation_adapter as adapter


async def test_모델_산출물이_없으면_빈_점수로_열화한다(monkeypatch, tmp_path):
    # 2026-09-17 운영: 모델 미학습 상태에서 메일 수신이 매 호출 OSError(500)였다
    monkeypatch.setattr(adapter, "_MODEL_DIR", tmp_path / "missing")
    assert await adapter.KcElectraModerationAdapter().moderate("안녕하세요") == {}
