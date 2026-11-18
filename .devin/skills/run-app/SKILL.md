---
name: run-app
description: Start (or restart) the portfolio app — FastAPI backend on :8000 and React frontend on :5173
triggers:
  - user
allowed-tools:
  - exec
  - read
---

Start or restart the portfolio app (both services).

Run the helper script — it kills anything already listening on ports
8000/5173, relaunches both servers in the background, and waits until
they respond:

```bash
bash .devin/skills/run-app/run.sh
```

If it exits non-zero, read the relevant log in
`.devin/skills/run-app/logs/` (backend.log or frontend.log), diagnose,
fix, and re-run.

Once both are up, open a browser preview for http://localhost:5173
(name: "Portfolio App") so the user can see it, and report the status.
