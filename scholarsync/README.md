# ScholarSync Intelligence Studio

Academic multi-agent dashboard with four research specialists and a lightweight hosted executor of the restored CrewAI specialist declarations (93 agent configurations; 28 specialist workflows). The hosted executor avoids starting a memory-intensive CrewAI process for each message. No fake agent results are generated. Hosted specialist chat is text-only, with external tools and write actions disabled.

The default home page is the Aria cinematic interface, adapted from the supplied frontend. It has four locally hosted animation clips, optional browser voice, server-backed conversations, real research jobs, searchable agent configurations, recent execution telemetry, document-text questions, and local numeric summaries. The original Studio and Mission Control remain available at /studio. The uploaded prototype's arbitrary server-file reader and placeholder statistics are not exposed; the coding workspace accepts pasted code and links to the public repository.

## Local setup

Run from the repository root with Python 3.10+:

```sh
uv sync --locked
export AI_API_KEY='your-provider-key'
export AI_MODEL='your-model-name'
uv run python -m uvicorn scholarsync.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. On Windows PowerShell use `$env:AI_API_KEY='...'` and `$env:AI_MODEL='...'`. An optional `AI_BASE_URL` can point to a compatible chat-completions endpoint (defaults to OpenAI). Keep credentials on the server only.

The app can open locally without an AI key, but launches are disabled until configuration is supplied. The dashboard shows actual agent status through server-sent events and stores run history in SQLite. `SCHOLARSYNC_DB` optionally specifies the database path. Use one server worker. The service is designed for single-user use. Do not commit the database or keys.

## Render preview deployment

Connect this repository as a Blueprint using the root `render.yaml`. Set `AI_API_KEY`, `SCHOLARSYNC_USERNAME` and `SCHOLARSYNC_PASSWORD` in Render's private environment settings. The default research model is `gpt-4.1-mini`. Set `AI_BASE_URL` if you use a compatible alternative provider for the research dashboard; specialist chat requires OpenAI. The workspace requires sign-in on Render over HTTPS; it is not meant for multiple independent users. Use strong unique credentials. A free Render instance has ephemeral storage, so run history may be lost on restart or redeploy. CrewAI may also exceed low-memory instance limits; check service logs and capacity before choosing a paid plan.

The service analyzes user-supplied material; it does not retrieve sources or verify citations. Once deployed, sign in, use Verify provider (now performs a tiny generation request), and then run both a research workflow and a specialist question to establish live generation. No private key is included in the repo. Optional fallback: set `GROQ_API_KEY` and `GROQ_MODEL` to a model your Groq account supports; the fallback is tried if the primary provider fails. Never reuse exposed keys. Run local tests with `uv run python -m unittest scholarsync.test_app scholarsync.test_provider -v`.
