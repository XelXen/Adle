# Security

How Adle protects a learner's data and machine, what it assumes, and where the boundaries are.
Every claim below names the code that implements it and the test that checks it. If you change
one, change the other in the same commit.

## What is being protected

| Asset | Where it lives | Main risk |
|---|---|---|
| Course materials, answers, learning history | The core's data directory on disk | Leaving the device |
| The AI provider key | OS secure storage; core memory while running | Disclosure to the UI, logs, disk, or a scene |
| The learner's machine | — | Code execution, file access, or network access by untrusted content |

Untrusted inputs: imported documents, model output (lesson data **and scene code**), and anything
the renderer receives from the scene player.

Out of scope: an attacker who already runs code as the same OS user, or who has physical access to
an unlocked session. Such an attacker can read the data directory directly.

## Process boundaries

Full diagram: `docs/architecture/overview.md`.

### Renderer (`adle://app`)

| Guarantee | Implementation | Verified by |
|---|---|---|
| No Node, no `require`, no `process` | `contextIsolation`, `sandbox`, `nodeIntegration: false` in `electron/main/window.ts` | `security-boundaries.test.ts` (window options); `e2e/security.spec.ts` (globals) |
| Only the documented bridge | `electron/preload/index.ts` exposes fixed functions; no `ipcRenderer`, no channel names | `e2e/security.spec.ts` asserts the exact surface |
| No network | CSP `connect-src 'self'`; session `onBeforeRequest` cancels every non-`adle:` request | `e2e/security.spec.ts` (https and loopback both blocked) |
| No inline or evaluated script | CSP `script-src 'self'` sent as a response header | `e2e/security.spec.ts` (inline script does not run) |
| Cannot navigate away or open windows | `will-navigate`, `will-frame-navigate`, `setWindowOpenHandler` in `security.ts` | `e2e/security.spec.ts` |
| No device permissions | Permission request, check, and device handlers all deny | `security.ts` |
| Only fixed external links can be opened | `EXTERNAL_LINKS` allowlist; ids, not URLs, cross the bridge | `e2e/security.spec.ts` |

### Main process

- IPC handlers accept calls only from the top-level `adle://app` frame (`isTrustedSender`), and
  treat every argument as untrusted (`parseInvokeRequest`, `validateApiKey`, `parseUiStatePatch`).
- Core operations are looked up in a table generated from the core itself. Unknown and
  `internal` operations are refused; parameters are shape- and size-checked.
  (`security-boundaries.test.ts`, `e2e/security.spec.ts`)
- Static files are served only from inside the build directories (`resolveStaticPath`), with a
  fixed MIME table. (`security-boundaries.test.ts`)

### Core (Python, loopback)

| Guarantee | Implementation | Verified by |
|---|---|---|
| Loopback only, OS-assigned port | `__main__.py` binds `127.0.0.1:0` | `tests/integration/test_process_lifecycle.py` |
| Every route needs the per-launch token | App-wide dependency `require_launch_token`, constant-time comparison | `tests/unit/test_api_boundary.py` |
| Token never in argv, environment, or logs | Delivered over stdin | `core.test.ts` (fake core checks argv and env); `test_process_lifecycle.py` (stderr) |
| No orphaned backend | Core exits on stdin EOF | `test_process_lifecycle.py`; `core.test.ts` |
| DNS rebinding closed | `TrustedHostMiddleware` | `test_api_boundary.py` |
| No CORS, no interactive docs | Not configured; `docs_url=None` | `test_api_boundary.py` |
| Errors do not echo input | `_summarise_validation_errors` | `test_api_boundary.py` |

Loopback traffic is unencrypted HTTP. See "Out of scope".

## The provider key

1. Entered in Settings and sent once over IPC to the main process.
2. Validated (`validateApiKey`: printable ASCII, 8–512 characters, no whitespace or control
   characters, which also rules out header injection).
3. Encrypted with Electron `safeStorage` (Windows DPAPI, macOS Keychain, Linux libsecret/KWallet)
   and written to `credentials.bin` in the profile.
4. Pushed to the core over the authenticated loopback route `provider.set_credential`, which is
   internal: the renderer cannot call it.
5. Held by the core in memory only (`CredentialVault`). Never in the database, a file, or a log;
   a redaction filter on every log handler is the backstop.

The renderer only ever receives `{ stored, hint }`, where `hint` is the last four characters.

On Linux without a keyring Electron would fall back to a hard-coded password (`basic_text`).
Adle treats that as "no secure storage" and refuses to save the key (`createSecureEncryptor`).

Verified by `e2e/provider-key.spec.ts`: after saving, the key is absent from the DOM, from every
bridge response, and from every file in the profile, including the core log after exit.

## Generated scene execution

Scenes are the highest-risk content: executable code that a model wrote after reading course
material. The full reasoning is in `docs/decisions/ADR-004-scene-isolation.md`.

**Layers, outermost first**

1. **Static policy** (`services/core/adle_core/generation/scene_policy.py`). Before a scene is
   stored, **and again every time a lesson is opened** (a database can be restored from a file
   made elsewhere; a scene that no longer passes is withheld and its text description is shown):
   valid Python only, imports limited to `manim`/`numpy`/`math`/`random`/`itertools`, every
   name resolved against the file's own definitions, a small builtin allowlist, and the manim API
   of the pinned Wanim build; JavaScript and DOM escape attributes refused; closed event
   vocabulary. *Defence in depth, not a sandbox.* (`tests/unit/test_scene_policy.py`)
2. **Isolated frame.** A sandboxed iframe on its own `adle://<id>.player` origin, new for every
   frame, in its own process, with a CSP of `default-src 'none'` plus same-origin assets. No
   preload bridge exists there.
3. **No network.** The same session-level request filter that covers the renderer.
4. **Validated protocol.** The only way out is `postMessage` to the embedding window, parsed by
   `parsePlayerMessage`: known types, exact keys, bounded sizes, primitive values. The host also
   checks the sending window, the exact origin, and the run id.
5. **Liveness and fallback.** A scene that errors, times out, or stops answering pings is
   discarded with its process, and the lesson shows the segment's text explanation.

**Deliberate relaxations**, each confined to player origins:

- `'unsafe-eval'`, because Wanim evaluates the compiled scene.
- `allow-same-origin` in the sandbox, because Wanim scripts a child frame; the embedder is a
  different origin, so the frame cannot lift its own sandbox.

**Residual risks, accepted**

- A scene can forge any *valid* protocol message, for example claim the learner "passed". Scene
  events are weak evidence and never decide mastery alone.
- A scene can use CPU until the watchdog fires (five seconds) and can show misleading content.
  The static policy and the lesson's own text limit the latter; the learner can report a lesson.
- Web storage is available inside a player origin for the life of that frame. Origins are
  single-use and all storage is cleared at startup.

## Imported documents

A learner's file is untrusted input to parsers written by third parties. Details and reasoning:
`docs/decisions/ADR-007-persistence-and-ingestion.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| Renderer script cannot name a file path | `sources.import_paths` is an internal operation. Paths come from the OS file dialog, or from dropped `File` objects resolved by the preload with `webUtils.getPathForFile` | `e2e/security.spec.ts` (internal operation refused; a `File` built by script is rejected); `test_courses_and_sources.py` (route marked internal) |
| Import requests are well-formed and bounded | `parseCourseId`, `parseImportPaths`: absolute paths, no NUL, at most 50; the core validates again | `electron/main/imports.test.ts`; `test_courses_and_sources.py` |
| Type is decided by content, not only by name | `ingestion/detect.py` | `tests/unit/test_ingestion.py` |
| Size, page, and text limits; a time limit per file | `ingestion/types.py` (`Limits`); the worker is killed on timeout | `test_ingestion.py`; `tests/integration/test_isolated_extraction.py` |
| A hostile file cannot take the service down | Each parse runs in a short-lived child process with its own pipes | `test_isolated_extraction.py` |
| A subverted parser cannot run code in the service | The reply is JSON, type-checked and bounded (`document_from_json`); pickle is never used | `test_ingestion.py` |
| Stored files stay inside the data directory | Copied under the generated source id; the display name is never used as a path | `test_courses_and_sources.py` |
| Search input is never query syntax | Terms are extracted and quoted by code (`build_match_query`) | `test_courses_and_sources.py` |
| Error messages do not quote documents | Only an error code and a fixed message cross the worker boundary | `test_ingestion.py` |
| Nothing is uploaded to import | Parsers are local; there is no OCR service; the session blocks all network requests | `e2e/security.spec.ts`; design |

Document content is data. Nothing in a file is executed, followed, or treated as an instruction.

**Residual risks, accepted**

- The parser worker runs as the same OS user as the service, without an additional OS sandbox.
  A parser exploit could read what that user can read. It cannot return code to the service, and
  it has no channel to the renderer or the provider key (the key is not in its memory, its
  arguments, or its environment).
- A file within the limits can still be slow to parse; the time limit (120 s) bounds it.

## Lessons and answers

Details and reasoning: `docs/decisions/ADR-010-lesson-ir-and-playback.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| A lesson reaches the database only in a validated form | `lessons.bundle.parse_bundle`: strict models, unknown fields refused, every scene through the static policy, descriptions of scenes computed from their source | `test_lesson_ir.py`, `test_lessons_api.py` |
| Lesson text cannot carry links, markup, paths, or control characters | Text validators in `lessons/ir.py` | `test_lesson_ir.py` |
| A lesson cannot cite something that is not in the learner's materials | `LessonService.store` resolves every cited section inside the course | `test_lessons_api.py` |
| The renderer never holds an answer key | `lessons.get` returns the player view; scoring happens in the core | `test_lesson_ir.py` (field by field, and by searching the output); `test_answers_api.py` |
| A stored scene is not trusted because it is stored | `LessonService.get` re-runs the policy and withholds what fails | `test_lessons_api.py`; `e2e/lesson.spec.ts` |
| Mathematics is rendered without HTML strings | `MathText`: `katex.render` into DOM nodes, `trust` off, bounded expansion | `MathText.test.tsx`; the app CSP has no `unsafe-inline` |
| No asset is loaded from a `data:` URI | Builds set `assetsInlineLimit: 0`; the CSP refuses `data:` fonts | `e2e/lesson.spec.ts` (no console errors while mathematics is on screen) |

| Practice and review questions arrive without their answers too | `learning.start_practice` returns the same player view of a question; answers go to `lessons.answer` | `test_learning_api.py` (searches the response for every key field) |
| Questions kept for practice are not in the lesson the player is given | `player_view` leaves `practice` out | `test_practice_questions_and_strategies.py` |

A learner's answers and written explanations stay in the local database. They are not logged.
So does everything else the learner tells Adle: that a suspected mix-up was a slip, that an
explanation did not help. None of it is sent to the provider; a request for another explanation
carries the concept, its objectives, and the names of the ways it was taught before, and nothing
about how the learner did.

## The model provider and its output

Details and reasoning: `docs/decisions/ADR-012-provider-quota-and-generation.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| A request goes only where the learner was told | The address is fixed at start-up; `https` only, or `http` on this computer; anything but the default is shown as "Custom endpoint (host)" | `test_provider_client.py`; `e2e/generation.spec.ts` |
| The key is in one header and nowhere else | Read from the vault per request; redirects not followed; environment proxy and `.netrc` not used | `test_provider_client.py` |
| Nothing sent or received is logged | Log lines carry a purpose and a status code only | `test_provider_client.py` (bodies and prompts absent from the log) |
| Nothing is sent that the learner did not start | Requests are made only inside a job the learner started; the suggestion dialog says what will be sent first; the lesson button says it beside itself | `test_generation_api.py`; `e2e/generation.spec.ts` |
| A learner's document cannot instruct the model through Adle | Learner text is quoted inside marked blocks whose closing tag cannot be forged; the standing rule is in the system prompt; the model has no tools | `test_generation_api.py` (hostile document) |
| Model output cannot enter the database unchecked | Draft parsed leniently, compiled deterministically, then `parse_bundle` (ADR-010); scenes through the static policy | `test_drafts.py`, `test_generation_api.py` |
| A model cannot invent an identifier or a citation | Identifiers are assigned by the core; a citation is a number the prompt offered, or it is dropped | `test_drafts.py` |
| A model cannot make Adle loop | A fixed number of requests per job; one request in flight; local limits under the provider's | `test_model_gateway.py`, `test_generation_api.py` |

**Residual risks, accepted**

- What is sent (a concept, its objectives, a few passages) leaves the computer for the provider
  once the learner asks. The provider's handling of it is outside Adle's control; the first-run
  screen and the settings say so.
- A model can write a lesson that is valid and wrong. Validation checks form, not truth. The
  lesson says where it came from ("From general knowledge", or the passages it cites).

## Reading aloud

Narration is spoken by the browser's speech synthesis using **only voices that run on this
computer** (`localService`). A voice that would send text to a service is never listed or used
(`lesson/speech.ts`, `speech.test.ts`). The session's network filter would refuse such a
request in any case. See ADR-013.

## Privacy

- No telemetry, analytics, or crash upload. No external service other than the configured AI
  provider, and only when the learner starts a generation.
- Logs contain event types and identifiers, never document text, answers, prompts, or secrets.
- The first-run screen and Settings → Privacy & data state what is stored and what is sent.

## Dependencies

- Exact versions, committed lockfiles (`package-lock.json`, `uv.lock`).
- `npm audit --audit-level=high` runs in CI. Status on 2026-11-19: 0 known vulnerabilities.
- npm install scripts are denied by default (`allowScripts` in `package.json`).
- Licences in use: MIT, ISC, BSD, Apache-2.0, OFL-1.1. No GPL/AGPL.

## Not yet done

| Item | Milestone |
|---|---|
| Electron fuses, ASAR integrity, code signing | M8 (packaging) |
| Player isolation re-verified in a packaged build | M8 |
| Python dependency audit in CI (`pip-audit` or equivalent) | M8 |
| OS-level sandbox for the parser worker (job object / seccomp / App Sandbox) | M8, with packaging |
| Prompt-injection tests against the fake provider | M5 |

## Reporting a problem

This project is not yet published. Until it is, report security concerns privately to the
repository owner rather than in a public issue.
