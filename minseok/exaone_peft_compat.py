"""EXAONE-3.5 AWQ 체크포인트에 peft(LoRA)를 붙이기 위한 호환 패치.

QLoRA 스타일 학습(4bit 고정 베이스 + fp16 LoRA 어댑터)을 현재 환경
(transformers 5.x 네이티브 AWQ gemm_triton 백엔드 + peft 0.19)에서 쓰려면
두 가지 패치가 필요하다. `get_peft_model` 호출 **전에**
`apply_exaone_peft_patches(model)`을 한 번 호출한다.

    from exaone_peft_compat import apply_exaone_peft_patches
    model = AutoModelForCausalLM.from_pretrained(..., quantization_config=AwqConfig(bits=4, backend="gemm_triton"))
    apply_exaone_peft_patches(model)
    model = get_peft_model(model, lora_config)
"""


def apply_exaone_peft_patches(model) -> None:
    # 1) EXAONE trust_remote_code 코드가 transformers 5.x 임베딩 접근자 규약 미구현
    #    → peft가 tied-weight 검사에서 NotImplementedError를 낸다.
    for module in model.modules():
        if type(module).__name__ == "ExaoneModel":
            cls = type(module)
            cls.get_input_embeddings = lambda self: self.wte
            cls.set_input_embeddings = lambda self, value: setattr(self, "wte", value)
            break

    # 2) peft 0.19.x의 AWQ 디스패처는 미출시 gptqmodel의 `AwqGEMMQuantLinear`를
    #    기대하지만 gptqmodel 7.1.0에는 없다 → 공통 베이스 AWQuantLinear로 별칭을
    #    걸어 gemm_triton 레이어(AwqGEMMTritonLinear)도 인식되게 한다.
    #    (AwqGemmTritonFn.backward가 grad_input을 계산하므로 LoRA 학습 가능)
    import gptqmodel.nn_modules.qlinear.gemm_awq as gemm_awq
    from gptqmodel.nn_modules.qlinear import AWQuantLinear

    if not hasattr(gemm_awq, "AwqGEMMQuantLinear"):
        gemm_awq.AwqGEMMQuantLinear = AWQuantLinear
