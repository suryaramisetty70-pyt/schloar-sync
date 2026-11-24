# ScholarSync

ScholarSync includes a research dashboard and the restored declarative CrewAI specialist assistant in `src/multi_agent_ai_system/flow.json`.

## Install

```bash
uv sync --locked
```

## Run

```bash
uv run python -m uvicorn scholarsync.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. See [setup and deployment](scholarsync/README.md) for Render environment variables and testing. Live generation requires your own valid API key.
