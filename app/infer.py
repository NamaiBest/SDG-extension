"""
Hybrid inference helper inspired by a persona-first chat design.

Behavior:
1) Route query as general or remedy-focused.
2) Use local LoRA only when explicitly enabled.
3) Fall back to Ollama, then OpenAI, then Gemini.
"""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from google import genai as google_genai
except ImportError:
    google_genai = None

try:
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError:
    PeftModel = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    pipeline = None


PERSONAS: Dict[str, Dict[str, str]] = {
    "knowledge": {
        "prompt_template": (
            "You are a practical, trustworthy assistant. "
            "Answer directly, keep useful detail, and avoid overclaiming."
        ),
        "response_style": (
            "Use concise paragraphs. Add short bullet points only when they improve clarity."
        ),
    },
    "wellness": {
        "prompt_template": (
            "You are a wellness-focused assistant. Prioritize safe self-care guidance and clear red flags."
        ),
        "response_style": (
            "Prefer simple steps and mention when professional care is appropriate."
        ),
    },
}


def _normalize_text(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z]+", text.lower())


def is_remedy_query(query: str) -> bool:
    keywords = {
        "home remedy",
        "remedy",
        "natural cure",
        "ayurveda",
        "herbal",
        "ginger",
        "turmeric",
        "honey",
        "cough",
        "sore throat",
        "cold",
        "acidity",
        "indigestion",
        "headache",
        "fever",
        "sinus",
    }
    q = query.lower()
    return any(k in q for k in keywords)


def load_remedy_rows(dataset_path: str) -> List[Dict[str, str]]:
    data = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    return [row for row in data if isinstance(row, dict)]


def retrieve_remedy_context(query: str, rows: List[Dict[str, str]], top_k: int = 3) -> str:
    q_tokens = set(_normalize_text(query))
    if not q_tokens:
        return ""

    scored = []
    for row in rows:
        problem = str(row.get("problem", ""))
        symptoms = str(row.get("symptoms", ""))
        remedy = str(row.get("remedy", ""))
        haystack = f"{problem} {symptoms}"
        tokens = set(_normalize_text(haystack))
        overlap = len(q_tokens.intersection(tokens))
        if overlap > 0:
            scored.append((overlap, problem, remedy))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    if not top:
        return ""

    blocks = []
    for idx, (_, problem, remedy) in enumerate(top, start=1):
        trimmed = " ".join(remedy.split())[:450]
        blocks.append(f"Example {idx}\nProblem: {problem}\nRemedy: {trimmed}")
    return "\n\n".join(blocks)


def build_prompt(
    query: str,
    persona: str,
    route: str,
    remedy_context: str,
) -> str:
    persona_data = PERSONAS.get(persona, PERSONAS["knowledge"])
    mode_hint = (
        "If this is a home-remedy question, answer with safe, practical steps and a short caution."
        if route == "remedy"
        else "Answer as a general assistant. Do not force home-remedy advice unless user asks for it."
    )

    prompt_parts = [
        persona_data["prompt_template"],
        f"Response style: {persona_data['response_style']}",
        mode_hint,
    ]

    if remedy_context:
        prompt_parts.append("Reference remedy context (use only if relevant):\n" + remedy_context)

    prompt_parts.append(f"User question: {query}\n\nAssistant:")
    return "\n\n".join(prompt_parts)


def load_local_pipeline(base_model: str, adapter_dir: str):
    if not all([AutoModelForCausalLM, AutoTokenizer, PeftModel, pipeline]):
        raise ImportError("transformers/peft not installed. Run `pip install -r requirements.txt`.")

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto")
    model = PeftModel.from_pretrained(base, adapter_dir)

    return pipeline(
        task="text-generation",
        model=model,
        tokenizer=tokenizer,
        device_map="auto",
    )


def answer_with_local(pipe, prompt: str, max_new_tokens: int = 220) -> Optional[str]:
    outputs = pipe(
        prompt,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        temperature=0.3,
        top_p=0.85,
        repetition_penalty=1.2,
        no_repeat_ngram_size=4,
        return_full_text=False,
    )
    if not outputs:
        return None
    return outputs[0]["generated_text"].strip()


def answer_with_ollama(model: str, prompt: str, host: str) -> Optional[str]:
    url = f"{host}/api/generate"
    resp = requests.post(url, json={"model": model, "prompt": prompt}, timeout=90, stream=True)
    resp.raise_for_status()
    text_chunks = []
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = line.decode("utf-8")
        if chunk.strip() == "{}":
            continue
        try:
            payload = json.loads(chunk)
        except Exception:
            continue
        if "response" in payload:
            text_chunks.append(payload["response"])
    joined = "".join(text_chunks).strip()
    return joined or None


def answer_with_gemini(prompt: str, key_path: str, model: str) -> Optional[str]:
    key_file = Path(key_path)
    if not key_file.exists():
        raise FileNotFoundError(f"Gemini key file missing at {key_file}")
    api_key = key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError("Gemini key file is empty.")

    if google_genai is not None:
        client = google_genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return (response.text or "").strip()

    try:
        import google.generativeai as legacy_genai
    except ImportError:
        legacy_genai = None

    if legacy_genai is not None:
        legacy_genai.configure(api_key=api_key)
        client = legacy_genai.GenerativeModel(model)
        response = client.generate_content(prompt)
        return (response.text or "").strip()

    raise ImportError("No Gemini SDK installed. Install dependencies from requirements.txt.")


def answer_with_openai(prompt: str, key_path: str, model: str) -> Optional[str]:
    if OpenAI is None:
        raise ImportError("openai not installed. Run `pip install -r requirements.txt`.")

    key_file = Path(key_path)
    if not key_file.exists():
        raise FileNotFoundError(f"OpenAI key file missing at {key_file}")
    api_key = key_file.read_text(encoding="utf-8").strip()
    if not api_key:
        raise ValueError("OpenAI key file is empty.")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=prompt,
        temperature=0.3,
    )
    return (response.output_text or "").strip() or None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="User query/problem to answer")
    parser.add_argument("--dataset_path", default="raw_data/merged_dataset.json", help="Path to remedies dataset")
    parser.add_argument("--adapter_dir", default="outputs/remedy-llama-lora", help="Path to LoRA adapter directory")
    parser.add_argument("--base_model", default="TinyLlama/TinyLlama-1.1B-Chat-v1.0", help="Base model used during training")
    parser.add_argument("--ollama_model", default="llama3", help="Ollama model name for fallback")
    parser.add_argument("--ollama_host", default="http://localhost:11434", help="Ollama host")
    parser.add_argument("--openai_model", default="gpt-4o-mini", help="OpenAI model name")
    parser.add_argument("--openai_key_path", default="openai_api_key.txt", help="File holding OpenAI API key")
    parser.add_argument("--gemini_model", default="gemini-1.5-pro-latest", help="Gemini model name")
    parser.add_argument("--gemini_key_path", default="gemini_api_key.txt", help="File holding Gemini API key")
    parser.add_argument("--persona", default="knowledge", choices=["knowledge", "wellness"], help="Response persona")
    parser.add_argument("--mode", default="auto", choices=["auto", "general", "remedy"], help="Routing mode")
    parser.add_argument("--use_local_adapter", action="store_true", help="Enable local LoRA model for remedy route")
    parser.add_argument("--skip_local", action="store_true", help="Bypass local HF LoRA")
    parser.add_argument("--skip_ollama", action="store_true", help="Bypass Ollama fallback")
    args = parser.parse_args()

    if args.mode == "auto":
        route = "remedy" if is_remedy_query(args.query) else "general"
    else:
        route = args.mode

    remedy_rows = []
    if route == "remedy":
        try:
            remedy_rows = load_remedy_rows(args.dataset_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[router] failed to load remedy dataset: {exc}")

    remedy_context = retrieve_remedy_context(args.query, remedy_rows, top_k=3) if remedy_rows else ""
    prompt = build_prompt(args.query, persona=args.persona, route=route, remedy_context=remedy_context)

    should_try_local = (route == "remedy") and args.use_local_adapter and (not args.skip_local)

    response = None
    response_source = "none"

    if should_try_local:
        try:
            pipe = load_local_pipeline(args.base_model, args.adapter_dir)
            response = answer_with_local(pipe, prompt)
            if response:
                response_source = "local_adapter"
        except Exception as exc:  # noqa: BLE001
            print(f"[local] failed: {exc}")

    if response is None and not args.skip_ollama:
        try:
            response = answer_with_ollama(args.ollama_model, prompt, args.ollama_host)
            if response:
                response_source = "ollama"
        except Exception as exc:  # noqa: BLE001
            print(f"[ollama] failed: {exc}")

    if response is None:
        try:
            response = answer_with_openai(prompt, args.openai_key_path, args.openai_model)
            if response:
                response_source = "openai"
        except Exception as exc:  # noqa: BLE001
            print(f"[openai] failed: {exc}")

    if response is None:
        try:
            response = answer_with_gemini(prompt, args.gemini_key_path, args.gemini_model)
            if response:
                response_source = "gemini"
        except Exception as exc:  # noqa: BLE001
            print(f"[gemini] failed: {exc}")

    if response is None:
        print("No response produced.")
        return

    print(f"=== ANSWER ({route}) ===")
    print(f"SOURCE: {response_source}")
    print(response)


if __name__ == "__main__":
    main()
