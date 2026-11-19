# ADR-001: Stack and pinned versions

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Adle is a local-first desktop app (PLAN.md §5). The plan names a preferred stack; this record fixes
the exact versions and the choices the plan left open, after checking what is current and mutually
compatible on the npm registry and PyPI on the date above.

## Decision

| Area | Choice | Why this and not the newest |
|---|---|---|
| Runtime | Node 24.3.0 (`.node-version`), Python 3.12 (`.python-version`) | Python 3.12 has wheels for every dependency; 3.14/3.15 are too new for that guarantee. |
| Desktop | Electron 45.4.1 (Chromium 156, Node 24.22) | Current stable. |
| UI | React 19.3.1, Vite 8.3.8 | Current stable. |
| Language | **TypeScript 6.0.3** | `typescript-eslint` 8.73 supports `<6.1`. TypeScript 7 (the native compiler) is not yet supported by the lint tooling. |
| Lint | **ESLint 9.39.5**, typescript-eslint 8.73.0, react-hooks 7.1.1, jsx-a11y 6.10.2 | `eslint-plugin-jsx-a11y` supports ESLint ≤ 9. Accessibility linting is worth more than ESLint 10. |
| Tests | Vitest 5.1.1 (jsdom 31), Playwright 1.65.1, axe-core 4.14 | Current stable. |
| Core | FastAPI 0.165, Pydantic 2.14, SQLAlchemy 2.1, Alembic 1.20, uvicorn 0.54 | Current stable. |
| HTTP client | **httpx2 2.16** | Starlette 1.10 deprecates `httpx` for its test client in favour of `httpx2` (from the pydantic organisation). One client for tests and for provider calls. |
| Documents | pypdf 7.1 (BSD), python-docx 1.2 (MIT), markdown-it-py 4.3 (MIT) | Pure Python or wheels; no AGPL parser. |
| Visuals | `@wanimjs/wanim` **0.1.3** | The only release line; pinned exactly because it is an early preview. |
| Python tooling | uv 0.11, ruff 0.17, mypy 2.4 (strict), pytest 9.2 | — |

Package management:

- **npm workspaces** (`apps/*`, `packages/*`), not pnpm: no extra tool to install, and no symlinked
  `node_modules` to work around when packaging Electron.
- Workspace packages are **source-only** TypeScript (`exports` point at `src/*.ts`). Vite, esbuild,
  and Vitest consume them directly, so there is no per-package build step.
- Every JavaScript dependency is pinned to an exact version; `package-lock.json` and `uv.lock` are
  committed.
- All desktop dependencies are `devDependencies`: the main process, preload, renderer, and player
  are bundled, so nothing is resolved from `node_modules` at run time.
- npm's install-script approval is on. `esbuild`'s postinstall is denied (`allowScripts`); it is an
  optimisation the JavaScript API does not need. Electron 45 has no install script: the binary is
  fetched by `npx install-electron` (`npm run setup`) and verified against bundled checksums.

Deferred:

- **Packager** (Electron Builder vs Forge) is chosen in the M8 packaging spike. It is not installed
  yet; `electron-builder` 26.18 currently pulls a `minimatch` version with a moderate advisory.
- **Local TTS engine and embeddings model** are evaluated in M5 and M2 respectively.

## Consequences

- TypeScript 7 and ESLint 10 are upgrades to revisit when `typescript-eslint` and
  `eslint-plugin-jsx-a11y` support them.
- `npm audit` reports 0 vulnerabilities across all dependencies at the time of writing.
