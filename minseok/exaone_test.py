import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, AwqConfig

MODEL_DIR = "/home/host/projects/com.redoceanmap/EXAONE-3.5-7.8B-Instruct-AWQ"

print("loading tokenizer...", flush=True)
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)

print("loading model...", flush=True)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    dtype=torch.float16,
    device_map="cuda",
    trust_remote_code=True,
    quantization_config=AwqConfig(bits=4, backend="gemm_triton"),
)
print("model loaded", flush=True)
print(f"VRAM allocated: {torch.cuda.memory_allocated()/1024**3:.2f} GiB", flush=True)

messages = [
    {"role": "system", "content": "You are EXAONE model from LG AI Research, a helpful assistant."},
    {"role": "user", "content": "안녕! 한 문장으로 자기소개 해줘."},
]
inputs = tokenizer.apply_chat_template(
    messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
)
input_ids = inputs["input_ids"] if not isinstance(inputs, torch.Tensor) else inputs
input_ids = input_ids.to("cuda")

out = model.generate(input_ids, max_new_tokens=64, do_sample=False)
print("=== OUTPUT ===", flush=True)
print(tokenizer.decode(out[0][input_ids.shape[1]:], skip_special_tokens=True), flush=True)
print(f"peak VRAM: {torch.cuda.max_memory_allocated()/1024**3:.2f} GiB", flush=True)
