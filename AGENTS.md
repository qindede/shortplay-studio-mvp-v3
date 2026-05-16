# AGENTS.md

This file gives coding agents the working rules for this repository.

## Project Overview

幕燃 MVP v3 is a short-drama content production workspace with a separated admin console.

- Frontend: SvelteKit, Svelte 5, TypeScript, Vite, pnpm
- Backend: FastAPI, Pydantic, Uvicorn
- Data store: JSON files under `backend/data`
- Uploads: local files under `backend/uploads`
- Main user workspace: `/`
- Admin console: `/admin`

Keep the product split clear:

- User workspace owns projects, episodes, scripts, shots, assets, video generation, account usage, and password changes.
- Admin console owns platform operations, users, point adjustments, point ledgers, user status, roles, and password resets.

## Common Commands

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
pnpm install
pnpm dev
pnpm check
pnpm build
```

Default local URLs:

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/api/health`
- Admin console: `http://localhost:5173/admin`

Default accounts documented by the project:

- User: `demo / demo123`
- Admin: `admin / admin123`

## Repository Map

- `backend/app/main.py`: FastAPI app setup, CORS, router registration, uploads mount.
- `backend/app/routers/`: API route modules grouped by domain.
- `backend/app/schemas.py`: API data shapes.
- `backend/app/db_store.py`: PostgreSQL persistence layer (SQLAlchemy ORM).
- `backend/app/storage_adapter.py`: thin facade over db_store with consistent error handling.
- `backend/app/services.py`: business logic shared by routers.
- `backend/app/security.py`: auth and current-user helpers.
- `frontend/src/lib/api.ts`: frontend API client and shared TypeScript types.
- `frontend/src/routes/+page.svelte`: main user workspace route.
- `frontend/src/routes/admin/+page.svelte`: admin console route.
- `frontend/src/lib/components/workspace/`: reusable workspace UI components and page panels.
- `frontend/src/routes/api/[...path]/+server.ts`: frontend proxy for backend API calls.
- `frontend/src/routes/uploads/[...path]/+server.ts`: frontend proxy for uploaded files.

## Coding Rules

Follow KISS: keep code simple, direct, efficient, and easy to maintain.

- Prefer the smallest change that solves the real problem.
- Use existing project patterns before adding new abstractions.
- Keep logic close to the feature that owns it unless reuse is already clear.
- Avoid premature generalization, speculative configuration, and framework churn.
- Do not add dependencies for problems that the current stack or standard library can solve cleanly.
- Keep functions focused and readable. Split only when it improves comprehension or reuse.
- Prefer explicit data flow over hidden global state.
- Preserve existing API shapes unless the task explicitly requires a contract change.
- Keep frontend state updates predictable and local to the relevant route/component.
- Keep backend validation in Pydantic schemas and domain checks in services or routers.
- Use structured parsing and typed objects instead of ad hoc string manipulation where practical.
- Add comments only for non-obvious decisions, edge cases, or business rules.

## Frontend Guidelines

- Use SvelteKit and Svelte idioms already present in `frontend/src`.
- Keep TypeScript types in sync with backend schemas and responses.
- Route API calls through `frontend/src/lib/api.ts`; avoid scattering raw `fetch` calls through components.
- Reuse workspace components under `frontend/src/lib/components/workspace`.
- Keep user workspace and admin console concerns separated.
- Use `lucide-svelte` icons when adding icon buttons or controls.
- Avoid oversized landing-page patterns; this app is an operational workspace.
- Keep UI dense, scannable, and task-focused.
- Make controls resilient on small screens and avoid text overflow.

## Backend Guidelines

- Use FastAPI routers by domain.
- Keep request and response models in `schemas.py` when they are shared or part of the API contract.
- Keep persistence changes compatible with the JSON store unless the task explicitly migrates storage.
- Do not write uploaded files outside `backend/uploads`.
- Validate ownership and permissions before returning or mutating user-owned resources.
- Keep admin-only operations behind the existing admin checks.
- Return clear HTTP errors with appropriate status codes.

## Data And File Safety

- Treat `backend/data/db.json` as development data. Avoid destructive rewrites unless asked.
- Do not delete or replace files in `backend/uploads` unless the task explicitly requires it.
- Avoid committing generated caches such as `.svelte-kit`, `node_modules`, `.venv`, or build output.
- Preserve existing user edits in the worktree. Do not reset or revert unrelated changes.
- Use UTF-8 for new text files. Be careful with existing mojibake or encoded Chinese strings; do not rewrite large text blocks only to change encoding unless requested.

## API And Integration Rules

- When backend endpoints change, update `frontend/src/lib/api.ts` and affected UI types in the same change.
- Keep `/api` and `/uploads` proxy behavior in mind when changing backend URLs.
- Avoid hard-coding new production hosts in components.
- Keep authentication token handling centralized in the existing API client helpers.
- Test both normal user and admin flows when touching shared auth, users, points, or roles.

## Verification

Run the narrowest useful checks for the change:

- Frontend type and Svelte checks: `cd frontend && pnpm check`
- Frontend production build: `cd frontend && pnpm build`
- Backend smoke check: `cd backend && uvicorn app.main:app --reload --port 8000`, then request `/api/health`

For full-stack changes, start both servers and verify the affected flow in the browser:

- Login/register
- User workspace flow affected by the change
- Admin flow affected by the change
- File upload or media preview, if touched
- Points ledger and account balance, if touched

## Documentation Updates

Update docs when behavior, setup, API contracts, or admin/user responsibilities change.

Keep documentation practical:

- State what changed.
- Show the command or endpoint when useful.
- Avoid long explanations that duplicate the code.
- Prefer concise Chinese for product-facing project notes and concise English for agent-facing implementation rules unless a task asks otherwise.
