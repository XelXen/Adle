# Security

How Adle protects a learner's data and machine, what it assumes, and where the boundaries are.
Every claim below names the code that implements it and the test that checks it. If you change
one, change the other in the same commit.

## What is being protected

| Asset | Where it lives | Main risk |
|---|---|---|
| Course materials, answers, learning history | The core's data directory on disk | Leaving the device; being replaced or destroyed |
| A copy of the data the learner saved | Wherever the learner put it: an ordinary, unencrypted file | Outside Adle's control once written; the interface says so |
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
- Handlers that act on the data as a whole take no arguments at all (see "The learner's data
  as a whole").
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
| A file to restore from is named the same way, and never logged | `restore_from` in the handshake line; `_restore` logs the outcome only | `core.test.ts` (fake core checks argv and env); `test_process_lifecycle.py` (the folder's name is not in stderr) |
| No orphaned backend | Core exits on stdin EOF | `test_process_lifecycle.py`; `core.test.ts` |
| DNS rebinding closed | `TrustedHostMiddleware` | `test_api_boundary.py` |
| No CORS, no interactive docs | Not configured; `docs_url=None` | `test_api_boundary.py` |
| Errors do not echo input | `_summarise_validation_errors` | `test_api_boundary.py` |

Loopback traffic is unencrypted HTTP. See "Out of scope".

Reads and writes of the database are separate kinds of connection (ADR-015): code that only
reads runs where SQLite refuses any write. Nothing in a database file's schema is trusted
(`trusted_schema = OFF`, `cell_size_check = ON` on every connection), because the file may
have been restored from a copy the learner was given (ADR-016).

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

## The learner's data as a whole

Saving a copy of everything, restoring from one, and deleting everything
(Settings → Privacy & data). Reasoning: `docs/decisions/ADR-016-copy-restore-and-delete.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| Page script cannot say where a copy goes, which file is restored, or that the learner is sure | `window.adle.data.*` take no arguments. The save dialog, the open dialog, and the confirmation are opened by the main process (`electron/main/data.ts`) | `e2e/security.spec.ts` (arguments are ignored; each question is still asked; backing out does nothing); `data.test.ts` |
| The page never learns a path | A saved copy is reported by file name only | `data.test.ts` |
| Writing a copy to a named file is for the main process alone | `data.save_copy` is an internal operation | `e2e/security.spec.ts` (refused from the page); `test_data_copy.py` (every operation that takes a path is internal) |
| A copy is never written inside the data folder, over a folder, or with another ending | `parseSavePath` in main; `_destination` in the core, again | `data-copy.test.ts`; `test_data_copy.py` |
| A failed save damages nothing | Written as `<name>.part`, renamed when complete | `test_data_copy.py` (an older copy is byte-for-byte as it was) |
| The provider key is not in a copy | The key is never in the database | `test_data_copy.py`; `e2e/data.spec.ts` |
| A file is checked before any of it is used | `_check_backup`: opened read-only with nothing in its schema trusted; integrity, a known revision, Adle's own tables | `test_database.py`; `test_data_copy.py` (another program's database with a version table is refused) |
| A restore is all or nothing | The copy is brought to the current schema in a working file first; the current data is kept as a safety copy; one atomic rename | `test_data_copy.py` (a copy that cannot be upgraded replaces nothing); `test_database.py`; `test_process_lifecycle.py` |
| A refused restore leaves a working app | Reported in the `ready` line; the core starts on the data as it was | `test_process_lifecycle.py`; `e2e/data.spec.ts` |
| Nothing can start the core while its folder is being deleted | `CoreProcess.whileStopped` | `core.test.ts`; `data.test.ts` (order of events) |
| Only Adle's own folder can be deleted | `canErase`: absolute, not a root, not directly under one; the folder comes from `paths.coreDataDir()` | `data-copy.test.ts`; `data.test.ts` |
| Deleting everything leaves no learner text on disk in Adle's folders, and leaves the key | The data directory is removed; the core log is rewritten at the next start; `credentials.bin` is outside it | `e2e/data.spec.ts` (searches the folders for a phrase from an imported file) |
| After a restore, no imported original stays that the learner cannot see | `SourceService.forget_unreferenced_files` at start-up | `test_data_copy.py` |
| "Show safety copies" can open one folder only | The folder is fixed in the main process | `data.test.ts`; `e2e/data.spec.ts` |

**Residual risks, accepted**

- A copy is not encrypted. Anyone who can read the file can read the text of the learner's
  materials and their learning history. The interface says so where the copy is made.
- "Delete everything" unlinks files; it does not overwrite the disk blocks they occupied.
- A copy the learner was given is someone else's content. Restoring it gives that content the
  standing of the learner's own and no more: text is shown as text, scenes are checked again
  on every read and run only in the player frame.

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
| A notice the provider sends in the model's place is not taken for the model's answer, and its words cannot do anything | Recognised by the client (ADR-020) and raised as `provider_notice`; the words are made one line, cut at 300 characters, cleared of control and text-reordering characters, quoted, and shown as text with no link; never logged, never followed, never retried | `test_provider_notice.py`; `e2e/generation.spec.ts` (no link in the message; one request sent) |

**Residual risks, accepted**

- What is sent (the course's name, a concept and its objectives, a few words about where the
  learner stands on it, their pace, depth, and goal, and a few passages) leaves the computer for the provider
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
  There are two, both under the profile's `logs/` folder and both local: the core's
  (`core.log`, rewritten at each start) and the app's own failures (`app.log`, ADR-018).
  Settings → About opens the folder. Nothing reads them but the learner.
- No crash reporter is started and no failure is reported to anyone. When the page crashes
  or hangs, or the main process throws, the learner is told in plain words, offered a way on,
  and a line is written to `app.log` (`electron/main/recovery.ts`; `recovery.test.ts`,
  `e2e/recovery.spec.ts`).
- The first-run screen and Settings → Privacy & data state what is stored and what is sent.
  Each control that sends something lists what it sends beside it, from one function per kind
  of request (`lessonDisclosure` in `renderer/src/lib/generation.ts`), which must be kept in
  step with the prompt builder in the core.
- The learner can take a copy of everything, put one back, and delete everything
  (see "The learner's data as a whole").

## Dependencies

- Exact versions, committed lockfiles (`package-lock.json`, `uv.lock`).
- `npm audit --audit-level=high` and `pip-audit` over everything in `uv.lock` run in CI.
  Status on 2026-11-20: 0 known vulnerabilities in either.
- `npm run licenses:check` is part of every gate: it fails if a package states no licence or
  is under one that would bind the whole of Adle, or if something that ships is missing from
  `docs/engineering/THIRD_PARTY.md`.
- npm install scripts are denied by default (`allowScripts` in `package.json`).
- Licences of what ships: MIT, ISC, BSD-3-Clause, Apache-2.0, OFL-1.1, PSF-2.0. No GPL,
  AGPL, or LGPL anywhere, shipped or not.
- FastAPI depends on the interface package of a telemetry library. Without that library's
  other half it records and sends nothing; the package build fails if the other half is ever
  present (`scripts/package.mjs`).

## The packaged app

Reasoning: `docs/decisions/ADR-019-packaging.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| The binary cannot be made to run as plain Node, take Node options from the environment, or load code from outside its archive | Electron fuses set by `scripts/package.mjs` | `npm run package:check` reads the fuses back and tries to run a script through it |
| The release build cannot be debugged from outside | The inspect fuse is off in the release build; it is on only in the build made for tests, which is never distributed | `npm run package:check` (release) and `--test` (the other) |
| Nothing on the learner's computer changes what the core runs | The private Python is started with `-I`: no `PYTHON*` variables, no user site-packages, nothing imported from the current folder. The parser worker inherits the same flags | `npm run package:check` (hostile `PYTHONHOME` and `PYTHONPATH`, bare `PATH`); `test_isolated_extraction.py`; `local-state.test.ts` |
| The core is exactly what the lock file says | Dependencies installed from `uv.lock` with `--require-hashes` | The package build fails otherwise |
| No package tree to audit at run time | Everything the app needs is bundled into `dist/`; the archive has no `node_modules` | `scripts/package.mjs` stages only `package.json`, `dist/`, and the icons |
| Every boundary in this document holds in the packaged app | The whole end-to-end suite runs against it unchanged | `npm run e2e:packaged`: 83 journeys, including `security.spec.ts` and `scene-player.spec.ts` |

## Not yet done

| Item | Milestone |
|---|---|
| Code signing, and an installer | Needs the owner's certificates (ADR-019). Until then Windows warns about the program and macOS refuses it |
| Checking the archive's integrity at start-up (the fuse for it) | With signing; without a signature it adds little |
| OS-level sandbox for the parser worker (job object / seccomp / App Sandbox) | Not built. The worker is a separate, short-lived, isolated process that returns only checked JSON; see "Residual risks" under "Imported documents" |
| A build and a test run on macOS and Linux | NOT RUN |
| The CI workflow | Written, never run: the repository has no remote |

## Reporting a problem

This project is not yet published. Until it is, report security concerns privately to the
repository owner rather than in a public issue.
