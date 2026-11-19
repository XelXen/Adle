# ADR-005: The API contract is generated from the core, never hand-copied

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Three places must agree on the core's API: the FastAPI routes, the main-process allowlist that
decides what the renderer may call, and the renderer's TypeScript types. Hand-maintained copies
drift, and a drifted allowlist is a security bug.

## Decision

- The FastAPI application is the single source of truth. Every route has an explicit
  `operation_id` (`area.action`) and named Pydantic request and response models.
- `npm run contracts` (`scripts/generate-contracts.mjs`) asks the real app object for its OpenAPI
  document and writes, into `packages/contracts`:
  - `schemas/openapi.json` — the raw contract;
  - `src/generated/models.ts` — a TypeScript type per schema (`json-schema-to-typescript`);
  - `src/generated/operations.ts` — `OPERATIONS` (id → method, path, `internal`) and
    `OperationTypes` (id → path, query, body, result).
- A route marked `openapi_extra={"x-adle-internal": True}` becomes `internal: true`. The bridge
  refuses internal operations from the renderer; only the main process calls them (for example the
  credential hand-off).
- `npm run contracts:check` fails if the generated files differ from what the code would produce.
  It runs in `npm run check` and in CI.
- Generated files are committed and never edited by hand.

The same pattern is used for the scene name allowlist (`npm run wanim-names`,
`services/core/adle_core/generation/data/wanim_names.json`), derived from the pinned Wanim bundle.

## Alternatives considered

- **`openapi-typescript`.** Requires TypeScript 5 as a peer; the workspace uses TypeScript 6. The
  local generator is about 250 lines and has no such constraint.
- **Hand-written TypeScript types.** Rejected: see Context.
- **JSON Schema as the source, Pydantic generated from it.** Pydantic models carry validators and
  documentation that a schema-first flow would lose.

## Consequences

- Adding an endpoint is: write the route, run `npm run contracts`, use `callCore('area.action')`.
  The renderer cannot call a route that was not deliberately exposed.
- Lesson IR and other large structured types (M4) will be exported the same way, with precompiled
  validators where the renderer needs runtime checks, because its CSP forbids `eval`-based ones.
