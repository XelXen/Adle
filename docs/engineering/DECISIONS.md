# Decision index

Short index of decisions currently in force. Each links to its Architecture Decision Record in
`docs/decisions/`. ADRs are immutable once accepted: to change a decision, add a new ADR that
supersedes the old one and update this index.

| ADR | Decision in one line |
|---|---|
| [001](../decisions/ADR-001-stack-and-pins.md) | Electron 45, React 19, Vite 8, **TypeScript 6**, **ESLint 9**, Python 3.12, FastAPI, **httpx2**; npm workspaces; everything pinned. |
| [002](../decisions/ADR-002-core-process-and-bridge.md) | The Python core is a child process handed its token over stdin; the renderer reaches it only through an allowlisted main-process bridge. |
| [003](../decisions/ADR-003-adle-protocol-no-dev-server.md) | One `adle://` protocol for development and production; no dev server, so one CSP and one set of origins. |
| [004](../decisions/ADR-004-scene-isolation.md) | Scenes run in a sandboxed iframe on a fresh `adle://<id>.player` origin per frame; `unsafe-eval` is confined there. |
| [005](../decisions/ADR-005-generated-contracts.md) | TypeScript types and the renderer's operation allowlist are generated from the FastAPI app and checked for drift. |
| [006](../decisions/ADR-006-design-tokens-and-theme.md) | Sprout tokens adjusted for AA contrast; theme applied through `nativeTheme` and `prefers-color-scheme` only. |
| [007](../decisions/ADR-007-persistence-and-ingestion.md) | SQLite with transactional, backed-up migrations; FTS5 search; local parsers run in a `subprocess` worker with JSON I/O (never `multiprocessing`); paths only from the main process. |
| [008](../decisions/ADR-008-window-shown-immediately.md) | The main window is created visible, on the canvas colour; nothing waits for `ready-to-show`, which occasionally never came. |
| [009](../decisions/ADR-009-curriculum-and-learner-model.md) | The concept graph is validated on every write; knowledge is an append-only record folded through BKT into four qualitative states; no score ever leaves the core. |
| [010](../decisions/ADR-010-lesson-ir-and-playback.md) | The Lesson IR is defined once in the core and published as JSON Schema; lessons enter through one validating gateway and their scenes are re-checked on every read; answer keys never leave the core; the lesson player takes its clock from the narrator. |

## Smaller standing choices (no ADR)

- **Routing:** a small in-house router that keeps the route in `history.state`. A routing library
  is unnecessary for a handful of screens with no URLs.
- **Data loading in the renderer:** `useResource(key, load)`; no client-side cache library.
- **Icons:** `lucide-react` (ISC), imported per icon.
- **UI font:** Inter Variable (OFL-1.1), bundled from `@fontsource-variable/inter`.
- **Licence field:** `UNLICENSED` (private) until the owner chooses a licence.
