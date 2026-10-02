"""Measure a complete interview using real 4-bit Apertus on Apple Metal.

Install mlx-lm into a macOS Python environment, then run this script with
PYTHONPATH=src/backend. Download the model with huggingface_hub first.
The HTTP transport adapts real MLX inference to the app's OpenAI client.
No simulated responses or network inference are used.
"""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

import httpx
import mlx.core as mx
from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from zusage.engine import core
from zusage.engine.brain import ApertusBrain
from zusage.eval.scripted import answer_for, load_bank
from zusage.knowledge import load_knowledge
from zusage.llm.client import ChatClient


def run(model_path, data_dir, language):
    assert mx.is_available(mx.gpu), "This benchmark requires Apple Metal"
    mx.set_default_device(mx.gpu)
    mx.set_memory_limit(12 * 1024**3)
    mx.set_cache_limit(1024**3)
    started = time.perf_counter()
    model, tokenizer = load(model_path, tokenizer_config={"trust_remote_code": False, "fix_mistral_regex": True})
    calls = []

    def infer(request):
        payload = json.loads(request.content)
        prompt = tokenizer.apply_chat_template(
            payload["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        tick = time.perf_counter()
        reply = generate(model, tokenizer, prompt=prompt, max_tokens=payload["max_tokens"],
                         sampler=make_sampler(temp=0), verbose=False)
        elapsed = time.perf_counter() - tick
        calls.append({"seconds": round(elapsed, 2), "tokens_out": len(tokenizer.encode(reply)),
                      "peak_metal_gib": round(mx.get_peak_memory() / 1024**3, 3)})
        print(json.dumps({"call": len(calls), **calls[-1]}), flush=True)
        return httpx.Response(200, json={"choices": [{"message": {"content": reply}}],
                              "usage": {"prompt_tokens": len(tokenizer.encode(prompt)),
                                        "completion_tokens": len(tokenizer.encode(reply))}})

    class MetalTransport(httpx.BaseTransport):
        def handle_request(self, request):
            return infer(request)

    brain = ApertusBrain(ChatClient("http://local-metal/v1", "", "apertus-v1.5-8b-4bit",
                                   transport=MetalTransport(), max_retries=0))
    kb = load_knowledge(data_dir)
    bank = load_bank(data_dir)
    state = core.start(kb, brain, {"language": language, "occupation_id": "fage_efz",
                                 "persona_id": "warm", "mode": "training", "length": "quick",
                                 "candidate": {"first_name": "Lea", "hobbies": ["volleyball"]}})
    for _ in range(18):
        if state["done"]:
            break
        question = state["current"]
        answer = answer_for(bank, question["qid"], question["phase"], language, "strong")
        if question["phase"] == "candidate_questions":
            answer = "No, thank you, that is all." if language == "en" else "Nein, danke, das war alles."
        state = core.step(kb, brain, state, answer)
    assert state["done"], "The full interview did not finish"
    state = core.finish(kb, brain, state)
    report = state["report"]
    degraded = sum(bool(turn["assessment"].get("degraded")) for turn in state["turns"])
    result = {"model": "tokimoa/apertus-v1.5-8b-mlx-4bit", "quantization_bits": 4,
              "hardware": platform.machine(), "gpu": mx.device_info()["device_name"],
              "physical_unified_ram_gib": round(mx.device_info()["memory_size"] / 1024**3, 3), "accelerator": "Apple Metal, unified memory",
              "language": language, "answers": report["answers"], "model_calls": len(calls),
              "calls_per_answer": report["llm_calls_per_answer"], "degraded_turns": degraded,
              "peak_metal_gib": round(mx.get_peak_memory() / 1024**3, 3),
              "process_peak_rss_gib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**3, 3),
              "elapsed_seconds": round(time.perf_counter() - started, 2), "calls": calls,
              "report_headline": report["narrative"]["headline"],
              "memory_gate_pass": mx.get_peak_memory() < 12 * 1024**3,
              "call_budget_pass": report["llm_calls_per_answer"] < 5}
    assert result["memory_gate_pass"] and result["call_budget_pass"]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--data", default="data")
    parser.add_argument("--language", choices=["en", "de"], default="en")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run(args.model, args.data, args.language)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
