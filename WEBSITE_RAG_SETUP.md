# Website Integration Guide (RAG + OpenAI + Gemini Fallback)

This project now supports a hybrid RAG-style flow for website use:

1. Route query as `general` or `remedy`.
2. Retrieve top remedy context from `raw_data/merged_dataset.json` for remedy-like queries.
3. Try backend models in this order:
   - `ollama` (local)
   - `openai` (cloud)
   - `gemini` (fallback)

The response includes a source label so you can show/debug where the answer came from.

## Key Files

- Inference engine: `app/infer.py`
- Remedy dataset: `raw_data/merged_dataset.json`
- OpenAI key file: `openai_api_key.txt` (gitignored)
- Gemini key file: `gemini_api_key.txt` (gitignored)

## Install

```bash
cd SDG-extension
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Test CLI First

General query:

```bash
./.venv/bin/python app/infer.py \
  --query "plan a focused study schedule for 3 days" \
  --mode auto
```

Remedy query:

```bash
./.venv/bin/python app/infer.py \
  --query "home remedy for mild sore throat" \
  --mode auto
```

The output format is:

```text
=== ANSWER (general|remedy) ===
SOURCE: ollama|openai|gemini|local_adapter
...answer...
```

## Backend API Pattern for Website

Create a small API server that shells into this inference module or reuses its functions directly.

Minimal route design:

- `POST /api/chat`
- Request body:

```json
{
  "query": "home remedy for bloating",
  "mode": "auto",
  "persona": "knowledge"
}
```

- Response body:

```json
{
  "route": "remedy",
  "source": "openai",
  "answer": "..."
}
```

## Frontend Integration

In your website, call the backend endpoint and render:

- assistant text (`answer`)
- optional badge (`source`)
- optional route (`route`) for debugging

Example fetch:

```javascript
const res = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query, mode: 'auto', persona: 'knowledge' })
});

const data = await res.json();
console.log(data.source, data.answer);
```

## Notes

- Keep API key files server-side only.
- Do not expose key files to frontend bundles.
- If OpenAI is available, it will be used before Gemini fallback.
- Local adapter is optional and only used if `--use_local_adapter` is enabled.
