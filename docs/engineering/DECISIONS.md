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
| [011](../decisions/ADR-011-brand-mark-and-colour.md) | The mark is the owner's "ad" monogram, drawn as vectors and verified against the artwork; the brand colour is its teal; success keeps a green of its own; app icons are rendered from the vectors by Electron. |
| [012](../decisions/ADR-012-provider-quota-and-generation.md) | One module sends, one decides the quota, one records; no sampling parameters; a model writes a forgiving draft that is compiled into the Lesson IR, so ids and citations cannot be invented; a fixed, small number of requests per job; a proposal adds nothing until the learner picks. |
| [013](../decisions/ADR-013-narration-aloud.md) | Narration is read by voices installed on the computer (local voices only), behind the narrator interface; words are highlighted only when the engine reports them; silent captions are always available. No bundled engine and no cloud voice in the first release. |
| [014](../decisions/ADR-014-adaptation.md) | A pattern of wrong answers is a hypothesis computed from the record (tentative, supported, rejected, resolved) that the learner can set aside; a slip counts as partly right; a repeat counts in full only after a gap; lessons carry questions kept for review; the next step is chosen by readable rules, always with a reason, never the same lesson again after it did not help. No model grading and no model-proposed hypotheses. |
| [015](../decisions/ADR-015-units-of-work.md) | A unit of work that may write takes SQLite's write lock when it begins and waits its turn; one that only reads runs on connections that cannot write and never waits. Fixes "database is locked" when a job committed between a request's first read and first write. |
| [016](../decisions/ADR-016-copy-restore-and-delete.md) | A copy of the data is one self-contained file written through an internal operation; restoring happens while the core starts, on a working copy first, keeping what it replaces; deleting everything is done by the main process with the core held stopped; every path and confirmation comes from the operating system. |
| [017](../decisions/ADR-017-session-summary.md) | A session is a sitting computed from the record (the latest run of activity with no pause over 45 minutes); it reports right answers as counts, names lighter evidence, never grants "demonstrated", and is shown on the Learn tab under the suggested next step. |
| [018](../decisions/ADR-018-when-the-app-fails.md) | No crash reporting of any kind; a local log of the app's own failures that never holds learner content; a crashed or hung page, an uncaught error in the main process, and a core that dies each get a plain message and a way on, decided by pure functions. |
| [019](../decisions/ADR-019-packaging.md) | Packed with `@electron/packager` into a folder; the core ships as a private Python (not a frozen executable) started cut off from the computer it is on; fuses set; one build for release and the same build with the debugger reachable for the end-to-end suite. No installer, signature, or updater yet. |
| [020](../decisions/ADR-020-provider-notices.md) | A successful answer that the provider wrote itself in the model's place (an account notice) is recognised, ends the job after one request, and is shown to the learner in the provider's own words, quoted, cleaned, and as plain text. |

## Smaller standing choices (no ADR)

- **Routing:** a small in-house router that keeps the route in `history.state`. A routing library
  is unnecessary for a handful of screens with no URLs.
- **Data loading in the renderer:** `useResource(key, load)`; no client-side cache library.
- **Icons:** `lucide-react` (ISC), imported per icon.
- **UI font:** Inter Variable (OFL-1.1), bundled from `@fontsource-variable/inter`.
- **Licence field:** `UNLICENSED` (private) until the owner chooses a licence.
