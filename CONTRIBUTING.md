# Contributing

This repository is built and maintained largely by coding agents, with people reviewing. The same
rules apply to both. Start with `AGENTS.md`.

## Set up

```bash
npm run setup
```

Installs JavaScript dependencies (`npm ci`), the pinned Electron binary, and the Python environment
(`uv sync`). You need Node ≥ 22.12 and [uv](https://docs.astral.sh/uv/).

## Daily loop

1. Pick the next item in `docs/engineering/PROJECT_STATE.md`.
2. `npm run dev` to run the app while you work.
3. Write the change **with its tests**.
4. `npm run check` (fast gates). For anything a learner can see, or anything touching the main
   process, the bridge, or the player, also `npm run e2e`, then open the app and try it.
5. Update the docs the change affects.
6. Commit.

## Branches and commits

- Work on `dev` in small commits, or on a short-lived branch `type/short-description` off it.
  `main` is what the owner has merged.
- [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(scope): …`, `fix(scope): …`, `test(scope): …`, `docs(scope): …`, `refactor(scope): …`,
  `chore(scope): …`. Scopes in use: `desktop`, `renderer`, `player`, `core`, `generation`,
  `lessons`, `learning`, `design`, `design-system`, `protocol`, `contracts`, `scenes`, `skill`,
  `plan`, `repo`.
- One coherent change per commit. Subject in the imperative, under about 72 characters. The body
  says why, and how it was verified if that is not obvious.
- Commit only when the gates for what you touched pass. If something is knowingly incomplete, say
  so in the body and in `PROJECT_STATE.md`.
- Never rewrite or force-push shared history. Never amend someone else's commit.

**Never commit:** secrets or `.env` files, API keys (even fake-looking real ones), databases, user
documents, learner data, voice models, caches, or build output. `.gitignore` covers the usual
places; review `git status` and `git diff --staged` anyway.

## Code standards

- **TypeScript:** strict, with `noUncheckedIndexedAccess`. ESLint and Prettier must be clean.
  `import type` for types. No `any` without a comment explaining why.
- **Python:** ruff and mypy strict must be clean. Full type annotations.
- Small modules with one job. Domain logic does not import Electron, HTTP, the database driver,
  or a provider SDK.
- Validate at every boundary (IPC, HTTP, postMessage, model output, files). Types are not
  validation.
- Handle errors explicitly. No bare `except`, no swallowed promise rejections, no continuing with
  state you know is wrong.
- Comments explain decisions, invariants, and security boundaries. They do not narrate code.
- No TODOs, placeholder controls, or mock data in a shipped path. Fixtures live in test or
  `fixtures/` directories and are labelled.
- Add a dependency only when it earns its place: check maintenance, licence (no GPL/AGPL), size,
  and native build cost. Pin it exactly. Record notable ones in an ADR.
- Every fixed bug gets a regression test.

## Generated files

Never edit by hand; regenerate and commit the result.

| Files | Command | When |
|---|---|---|
| `packages/contracts/schemas/openapi.json`, `src/generated/*` | `npm run contracts` | A core route or model changed |
| `services/core/adle_core/generation/data/wanim_names.json` | `npm run wanim-names` | `@wanimjs/wanim` was upgraded |
| `services/core/adle_core/generation/data/scene_guide.md` and its examples | `npm run scene-guide` | The scene skill or one of its examples changed |
| `docs/engineering/THIRD_PARTY.md` | `npm run licenses` | A dependency was added, removed, or upgraded |
| `apps/desktop/assets/icons/*` | `npm run icons` | The mark changed |

`npm run check` fails if any of the first four is stale. It also fails if something that
looks like a credential, a database, or a saved copy of a learner's data is about to be
committed (`npm run secrets:check`).

## Decisions

A choice that a future maintainer might reasonably question gets an ADR:
`docs/decisions/ADR-NNN-short-title.md` with Context, Decision, Alternatives, Consequences, and a
row in `docs/engineering/DECISIONS.md`. Accepted ADRs are not edited; supersede them.

## Before you ask for review

- [ ] `npm run check` passes; `npm run e2e` passes if UI, main, bridge, or player changed.
- [ ] New behaviour has tests; a fixed bug has a regression test.
- [ ] Loading, empty, error, and disabled states exist where relevant.
- [ ] Keyboard and screen-reader behaviour considered; axe still clean.
- [ ] No new raw colours, spacing, or one-off components.
- [ ] No secrets, user data, or build output in the diff.
- [ ] Docs updated: `PROJECT_STATE.md`, and whichever of `AGENTS.md`, `TESTING.md`, `SECURITY.md`,
      `DESIGN_SYSTEM.md`, `CHANGELOG.md`, ADRs apply.
- [ ] Test results reported as PASS / FAIL / NOT RUN / BLOCKED, from actually running them.
