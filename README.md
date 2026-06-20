# Soft-Empower Coding Study

This complete setup gives a participant a coding interface and an LLM helper that chooses one of three options:

1. `concept_suggestion`
2. `code_suggestion`
3. `direct_code`

When the LLM chooses `direct_code`, the frontend automatically writes the returned code into the Monaco editor.

The app tracks counts and percentages for each option per participant and problem.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/study
```

## Important

Put your real OpenRouter key in `.env`:

```text
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

The frontend file is cache-busted in `index.html`, so the browser should load the new `app.js`. If you still see the old UI, hard refresh with `Cmd + Shift + R` or `Ctrl + Shift + R`.
