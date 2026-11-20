# ScholarSync Intelligence Studio

Standalone academic multi-agent dashboard. This implementation is separate from the original CrewAI scaffold because its source flow was not present in the repository. Four specialized LLM calls perform planning, parallel evidence analysis and critique, and final writing. No fake agent results are generated.

## Local setup

Run from the repository root with Python 3.10+:

```sh
pip install -r scholarsync/requirements.txt
export AI_API_KEY='your-provider-key'
export AI_MODEL='your-model-name'
uvicorn scholarsync.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. On Windows PowerShell use `$env:AI_API_KEY='...'` and `$env:AI_MODEL='...'`. An optional `AI_BASE_URL` can point to a compatible chat-completions endpoint (defaults to OpenAI). Keep credentials on the server only.

The app can open locally without an AI key, but launches are disabled until configuration is supplied. The dashboard shows actual agent status through server-sent events and stores run history in SQLite. `SCHOLARSYNC_DB` optionally specifies the database path. Use one server worker. The service is designed for single-user use. Do not commit the database or keys.

## Render preview deployment

Connect this repository as a Blueprint using the root `render.yaml`. Choose a free web service and set the four prompted variables: `AI_API_KEY`, `AI_MODEL`, `SCHOLARSYNC_USERNAME` and `SCHOLARSYNC_PASSWORD`. Set `AI_BASE_URL` if you use a compatible alternative provider. The workspace requires sign-in on Render over HTTPS; it is not meant for multiple independent users. Use strong unique credentials. A free Render instance has ephemeral storage, so run history may be lost on restart or redeploy. For permanent history, arrange durable database storage before production use.

The service analyzes user-supplied material; it does not retrieve sources or verify citations. Existing original CrewAI modules can be integrated when the missing source is available.
