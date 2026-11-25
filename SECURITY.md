# Security

How Adle protects a learner's data and machine, what it assumes, and where the boundaries are.
Every claim below names the code that implements it and the test that checks it. If you change
one, change the other in the same commit.

## What is being protected

| Asset | Where it lives | Main risk |
|---|---|---|
| Course materials, answers, learning history | The core's data directory on disk | Leaving the device; being replaced or destroyed |
| A copy of the data the learner saved | Wherever the learner put it: an ordinary, unencrypted file | Outside Adle's control once written; the interface says so |
| The AI provider keys (one per provider) | OS secure storage; core memory while running | Disclosure to the UI, logs, disk, a scene, or the other provider |
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
| No network, by a request | CSP `connect-src 'self'`; session `onBeforeRequest` cancels every non-`adle:` request | `e2e/security.spec.ts` (https and loopback both blocked) |
| No network, by any other road | A peer connection and a connection opened ahead of time are not requests, and no policy of the page governs them here. No name is ever looked up (`refuseNameLookups`); a proxy that is nowhere, loopback included; no UDP outside a proxy (`security.ts`, ADR-029) | `e2e/security.spec.ts` (a peer connection and a preconnect against UDP and TCP listeners on this computer: nothing arrives) |
| Nothing is downloaded | `will-download` is refused | `security.ts` |
| No inline or evaluated script | CSP `script-src 'self'` sent as a response header | `e2e/security.spec.ts` (inline script does not run) |
| Cannot navigate away or open windows | `will-navigate`, `will-frame-navigate`, `setWindowOpenHandler` in `security.ts`. A frame inside the window may be a scene player or nothing, never the app | `e2e/security.spec.ts`; `security-boundaries.test.ts` |
| Pictures tried before they are shown (ADR-038) | The page asks the core for scene sources to try (`scenes.trials`) and says how each went (`scenes.report_trial`: passed, or a stage and at most 2,000 characters, of which 500 reach the provider). The trial runs in an ordinary player frame, sandboxed, on an origin of its own, out of sight and out of reach, removed afterwards. A report about a trial nobody waits for is let go; a picture costs at most two requests whatever is reported | `test_scene_trials.py`; `scene-trial.test.ts`; `e2e/generation.spec.ts` |
| No device permissions | Permission request, check, and device handlers all deny. One thing is granted, to one asker: the app's own page, as the window's own document, may fill the screen (a lesson watched full screen, ADR-035). A scene's frame, a frame inside the window, and a page from anywhere else are refused that too | `security.ts` (`mayFillTheScreen`); `session-hardening.test.ts` |
| Only fixed external links can be opened | `EXTERNAL_LINKS` allowlist; ids, not URLs, cross the bridge | `e2e/security.spec.ts` |
| Cannot name a file | Paths come from a dialog of the operating system, or from files the learner dropped. The preload calls no method of what the page hands it: a real list, each entry a real `File`, the path asked of the browser (`preload/dropped.ts`) | `dropped.test.ts`; `e2e/security.spec.ts` (a script-made file, a list of strings, and something list-like with methods of its own are all refused) |

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
- A value put into an address of the core is an identifier and nothing else: letters, digits,
  `_` and `-`. Anything that could turn one address into another once decoded is refused
  (`buildPath`; `core.test.ts`).
- A core that has just come up is given the learner's choice of provider, then their keys,
  and only then is anyone told it is ready (`CoreProcess` `afterReady`, `syncProviders`). A
  choice that cannot be applied means no key is handed over and the start fails, so a core
  never runs on "automatic" with the keys of a learner who chose one provider
  (`providers.test.ts`, `core.test.ts`).

### Core (Python, loopback)

| Guarantee | Implementation | Verified by |
|---|---|---|
| Loopback only, OS-assigned port | `__main__.py` binds `127.0.0.1:0` | `tests/integration/test_process_lifecycle.py` |
| Every route needs the per-launch token | App-wide dependency `require_launch_token`, constant-time comparison | `tests/unit/test_api_boundary.py` |
| Nothing of a request is read before it is known to be ours, and no body is larger than the app's own | `api/gate.py`, in front of all routing: the token, then a two-megabyte bound, before any of the body is read | `test_api_boundary.py` (the body of a request without the token is never read; a declared or an undeclared oversize is refused) |
| Token never in argv, environment, or logs | Delivered over stdin | `core.test.ts` (fake core checks argv and env); `test_process_lifecycle.py` (stderr) |
| A file to restore from is named the same way, and never logged | `restore_from` in the handshake line; `_restore` logs the outcome only | `core.test.ts` (fake core checks argv and env); `test_process_lifecycle.py` (the folder's name is not in stderr) |
| No orphaned backend | Core exits on stdin EOF | `test_process_lifecycle.py`; `core.test.ts` |
| DNS rebinding closed | `TrustedHostMiddleware`: `127.0.0.1` and `localhost`, and no other name | `test_api_boundary.py` |
| The log holds no text of an error | An error is logged by its kind and where it happened (`logs.where`); the database keeps a statement's values out of its errors; the HTTP client's own lines are not written; a key in a traceback is removed like one in a message | `test_jobs.py`, `test_database.py`, `test_provider_credentials.py` |
| No CORS, no interactive docs | Not configured; `docs_url=None` | `test_api_boundary.py` |
| Errors do not echo input | `_summarise_validation_errors` | `test_api_boundary.py` |

Loopback traffic is unencrypted HTTP. See "Out of scope".

Reads and writes of the database are separate kinds of connection (ADR-015): code that only
reads runs where SQLite refuses any write. Nothing in a database file's schema is trusted
(`trusted_schema = OFF`, `cell_size_check = ON` on every connection), because the file may
have been restored from a copy the learner was given (ADR-016).

## The provider keys

There are two providers (AIHubMix and NVIDIA NIM), and each has a key of its own. The learner
chooses one of them, or "automatic": every provider they have given a key to, each used for
what it is good at. Reasoning: `docs/decisions/ADR-021-a-choice-of-providers.md` and
`docs/decisions/ADR-023-every-provider-with-a-key.md`.

1. Entered in Settings on that provider's own card, and sent once over IPC to the main
   process with that provider's **name**.
2. Validated (`validateApiKey`: printable ASCII, 8–512 characters, no whitespace or control
   characters, which also rules out header injection). The name is checked against a fixed
   list (`parseProviderId`).
3. The main process asks the **core** where that provider is (`provider.status`), and keeps
   the key with the provider's name and that address. Everything is encrypted together with
   Electron `safeStorage` (Windows DPAPI, macOS Keychain, Linux libsecret/KWallet) and
   written to `credentials.bin` in the profile. The file does not show which providers have
   a key.
4. Pushed to the core over the authenticated loopback route `provider.set_credential`, which is
   internal: the renderer cannot call it. After each start, a key is pushed only for a
   provider whose address is the one the key was stored for.
5. Held by the core in memory only (`CredentialVault`), one per provider. Never in the
   database, a file, or a log; a redaction filter on every log handler covers every key held,
   not only the one in use.

6. Written into a **settings file** only when the learner saves one with their keys in it
   (ADR-064), and then only locked: encrypted with AES-256-GCM under a key made from a
   password they typed (scrypt, N = 32768, r = 8, p = 1, a new salt for each file). The
   main process does this; the page types the password and is told whose keys are
   there. A file names a key's provider and never an address.

The renderer only ever receives `{ stored, hint }` for each provider, where `hint` is the last
four characters.

| Guarantee | Implementation | Verified by |
|---|---|---|
| A key is only ever sent to the provider it was given for | Each provider has its own client, bound to one address, which asks the vault for its own provider's key and no other | `test_provider_choice.py` (both keys held: each address receives its own; one key held: nothing is sent to the other) ; `e2e/providers.spec.ts` (two servers; the one not chosen receives nothing) |
| A key is only ever handed over for the address it was typed for | `ProviderKeyStore` keeps and returns a key by provider **and** address | `local-state.test.ts`; `e2e/providers.spec.ts` (the same profile with the provider moved: no key reaches the core) |
| The page cannot say where a key goes | `setApiKey`, `clearApiKey`, `select` take a name from a fixed list; the address comes from the core | `e2e/providers.spec.ts` (an address, an unknown name, an extra argument); `local-state.test.ts` (`parseProviders`) |
| Nothing changes the learner's choice but the learner | `provider.select` is internal and is only called from the handler of the learner's click. The choice is one provider, or "automatic" | `test_provider_choice.py`; `e2e/security.spec.ts` (the bridge's exact surface) |
| With one provider chosen, nothing moves a request to another | The plan for a request is that provider alone (`generation/routing.py`); its failure, a missing key, or a used-up allowance is the answer | `test_provider_routing.py` (a property over every state of every provider); `e2e/providers.spec.ts` (the one not chosen receives nothing) |
| With "automatic", a request only ever goes to a provider the learner gave a key to | A provider without a key of its own is never in a plan while another has one, and is refused before anything is sent when none has | `test_provider_routing.py`; `e2e/providers.spec.ts` |
| Where a request may go is said before it is sent, and who wrote the answer afterwards | Every control that sends names the plan the core has at that moment, including the provider that would be asked second; a job's progress says when one is passed over; `written_by` records each provider and model | `test_provider_routing.py`; `e2e/providers.spec.ts` (the second provider writes, and the dialog says so) |
| Checking a key sends nothing of the learner's, and goes to that provider alone | `provider.check` is one fixed request of a few words to the provider named; it has no stand-in | `test_provider_routing.py` (the whole prompt is asserted); `e2e/providers.spec.ts` |
| The choice is not changed under work that is under way | The core refuses while any job that asks a model is waiting or running | `test_provider_choice.py`; `e2e/providers.spec.ts` |
| A provider's other model is still the same provider | A stand-in is asked at the same address with the same key; the models and their order are shown before anything is sent, and a stand-in is said while it happens and afterwards | `test_provider_choice.py`; `e2e/providers.spec.ts` |
| A key is never in a settings file in the clear | `lockKeys` in the main process; without a password the keys are left out | `settings-file.test.ts` (no key, part of one, or its base64 in the text; a changed file does not open); `e2e/settings-file.spec.ts` (the file on disk is searched); `e2e/security.spec.ts` (no password, no file) |
| A settings file cannot send a key anywhere | A key in a file is named by its provider; it is stored for the address the core gives for that provider here, and one for a provider not offered here is not kept | `settings-file.test.ts` (an address in a file is not read); `e2e/settings-file.spec.ts` |
| A settings file cannot change where requests go unasked | The provider it names is applied through `provider.select` only if it is offered here; otherwise the choice here stays | `settings-files.ts`; `e2e/settings-file.spec.ts` |
| A settings file cannot make this computer download unasked | A voice that is not here is set up only when the learner left that ticked, having been shown what is downloaded | `test_settings_file.py`; `e2e/settings-file.spec.ts` (unticked: nothing is set up) |
| A settings file cannot ask for unbounded work | The costs it names for unlocking are bounded, and a file larger than 256 KB is not read | `settings-file.test.ts` |
| A model's thinking is not kept | Counted for the token estimate; never stored, shown, or logged | `test_provider_choice.py` |

A developer can move a known provider to another address before launch
(`ADLE_PROVIDER_ENDPOINTS`). It is then named with that address everywhere it is shown, and it
is not handed the key that was stored for the real address.

On Linux without a keyring Electron would fall back to a hard-coded password (`basic_text`).
Adle treats that as "no secure storage" and refuses to save the key (`createSecureEncryptor`).

Verified by `e2e/provider-key.spec.ts`: after saving, the key is absent from the DOM, from every
bridge response, and from every file in the profile, including the core log after exit.

## Generated scene execution

Scenes are the highest-risk content: executable code that a model wrote after reading course
material. The full reasoning is in `docs/decisions/ADR-004-scene-isolation.md`.

**Most pictures are written by the core, not a model** (ADR-045). A figure is data in the
lesson: a kind from a fixed list and its values, checked field by field. The core fills a
template with them, in `generation/figures.py`. The model's text reaches the scene file only
as a quoted string literal (`repr`), TeX is refused if it uses a command that can reach
outside a formula (`\href`, `\url`, `\cssId`, `\def`, `\require` and the like), and a
formula is parsed into a tree that may hold only numbers, `x`, the slider's name, two
constants, arithmetic, comparisons and sin, cos, tan, exp, log, sqrt and abs, and is written out again
from that tree: nothing the model typed is pasted in as code. Before it is drawn the formula
is evaluated in the core, on that rewritten expression only, with no builtins. The file that
results is then treated exactly as a scene a model wrote: every layer below applies to it.

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
   discarded with its process, and the lesson shows the segment's text explanation. So is one
   that sends more messages in a second than a scene has reason to (`MESSAGE_BUDGET_PER_SECOND`
   in `WanimPlayerAdapter`): each message is work for the page that shows the lesson, and
   they are counted before they are read.

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

### A chapter of a film (ADR-065)

A film of a whole course is the one place where code a model wrote runs **outside the
player's frame**: each chapter is a ManimGX file, run by the film engine, a program of its
own on a Python of its own, on the learner's computer and as the learner. Nothing in it is
sandboxed by the operating system. What stands between a chapter and the computer:

| Guarantee | Implementation | Verified by |
|---|---|---|
| Nothing of a chapter runs before the policy has passed it | `film/policy.py` (`check_chapter_source`) parses the file and looks at every node: only `manimgx as m`, `numpy as np` and `math`; one scene; only the names and members of the pinned engine that are listed (`film/data/names.json`, written from the engine by `scripts/dev/film_names.py`), with files, pictures from files, sound, the voice, the typesetter's own code, the engine's settings, the film being made and three dimensions left out; no underscore names or attributes; a few of Python's own names, none that looks inside an object or runs text, and none of the others may be bound either; no `while`, `try`, `with`, `global`, decorators or `**`; no text holding an address, a path, or a typesetter's command that reads a file. What Adle mends in a file (an engine name used bare, `np` or `math` not imported, brackets beyond a line's animations) it mends before the check, and the mended file is checked whole | `test_film_policy.py`: 72 hostile files, each refused (another import, `__import__`, `open` bound and used, a class's machinery, `getattr`, `vars`, `eval`, numpy reading or writing a file, pictures and drawings from files, sound, the engine's voices, a voice of the file's own, the engine's settings, the typesetter's preamble directly and in a mapping, `**`, font and code files, a format string, paths and addresses in text, TeX's `\input` and Typst's `#read`, the film and its clock, a window, a camera, a 3-D scene, and every refused statement), and nothing of a refused file run |
| A chapter runs only inside Adle's own files | The engine is given `take_NN.py` or `film.py`, never the chapter: they import `adle_voice.py` first, which takes the network away from the process (`socket.connect`, `create_connection`, `getaddrinfo`) and gives every scene Adle's voice (the engine's own default voice is a service on the internet) | `test_film_script.py`; the films made by hand (ADR-065) |
| The engine has nothing of this computer's | `bare_environment`: no setting for Python, no profile, its home, temporary files and caches a folder of the film maker's own (kept between runs: a first run in an empty home never ends, so it is readied by a small scene ended after twenty seconds), and a proxy that leads nowhere; started with `-I -B`; its output read up to a bound and never logged | `test_film_install.py` |
| A chapter that never ends is ended | Five minutes for a chapter alone, more for a long film by its length; the learner's Stop ends it at once | `test_film_install.py` (a scene that hangs, ended in time and when stopped) |
| What the engine says of a chapter goes only to the model that wrote it | `report.findings`, by the chapter's own lines, at most fourteen sentences of 300 characters; the core logs only counts | `test_film_report.py` |
| The number of requests is bounded, and said first | One a chapter, and `MAX_MENDS` (three) more at most; the bound is beside "Make the film", one press away | `test_films.py`; `e2e/film.spec.ts` |
| The film maker is downloaded only at the learner's word, and only what is pinned | `FilmInstaller`: the Python by its size and SHA-256 (`film/catalog.py`), unpacked with `tarfile`'s `data` filter; ManimGX and what it needs by the lock for this system with `--require-hashes --no-deps --only-binary=:all:`; the engine draws a circle here before it is called set up; only its own folder is ever removed | `test_film_install.py` (a changed or longer Python refused, an archive that reaches out of its folder refused, a failed install leaves nothing) |
| The page plays a film and names no place | The video is fetched from the core a part at a time into a `blob:`; its words become WebVTT as plain text; saving is `films.saveFile(filmId)`, the place asked in the system's own window | `film-file-rules.test.ts`; `films.test.ts`; `e2e/security.spec.ts`; `e2e/film.spec.ts` |

**Residual risks, accepted**

- **The policy is a list, not a sandbox.** A way out of the engine it does not know of is a
  way out, as the learner. The list is short on purpose and every name on it was read; text
  put together while the file runs is not seen by the policy, and the engine gives text to
  its typesetter only escaped (tried by hand: `#read(...)` and `\input` in a chapter's text
  are set as text or refused).
- **The network is taken away inside the engine's process, not by the system.** A library
  of the engine that opened a connection without Python's `socket` could reach the network.
- **The engine's programs are trusted as their publishers built them**: ManimGX, its Rust
  core and its fonts, numpy, Pillow and the rest, from the Python Package Index, and the
  Python from python-build-standalone, each by its hash.
- **A chapter can show what is wrong**, as any picture a model drew can. A film is the
  model's work and says so.

## Imported documents

A learner's file is untrusted input to parsers written by third parties. Details and reasoning:
`docs/decisions/ADR-007-persistence-and-ingestion.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| Renderer script cannot name a file path | `sources.import_paths` is an internal operation. Paths come from the OS file dialog, or from dropped `File` objects resolved by the preload with `webUtils.getPathForFile`, which calls no method of what the page handed it (`preload/dropped.ts`) | `e2e/security.spec.ts` (internal operation refused; a `File` built by script is rejected); `test_courses_and_sources.py` (route marked internal) |
| Import requests are well-formed and bounded | `parseCourseId`, `parseImportPaths`: absolute paths, no NUL, at most 50; the core validates again | `electron/main/imports.test.ts`; `test_courses_and_sources.py` |
| Type is decided by content, not only by name | `ingestion/detect.py` | `tests/unit/test_ingestion.py` |
| Size, page, and text limits; a time limit per file | `ingestion/types.py` (`Limits`); the worker is killed on timeout. A file over the largest limit is refused before any of it is read (`SourceService.import_file`) | `test_ingestion.py`; `test_courses_and_sources.py`; `tests/integration/test_isolated_extraction.py` |
| A hostile file cannot take the service down | Each parse runs in a short-lived child process with its own pipes | `test_isolated_extraction.py` |
| A subverted parser cannot run code in the service | The reply is JSON, type-checked and bounded (`document_from_json`); pickle is never used | `test_ingestion.py` |
| Stored files stay inside the data directory | Copied under the generated source id; the display name is never used as a path | `test_courses_and_sources.py` |
| Search input is never query syntax | Terms are extracted and quoted by code (`build_match_query`) | `test_courses_and_sources.py` |
| Error messages do not quote documents | Only an error code and a fixed message cross the worker boundary. The service shows what a worker says only if the code is one a parser has, as one plain line of limited length (`_refusal` in `ingestion/extract.py`); anything else is treated as a worker that broke | `test_ingestion.py` |
| Nothing is uploaded to import | Parsers are local; a page with no text to select is kept as a picture and nothing more is done with it; the session blocks all network requests | `e2e/security.spec.ts`; `e2e/course-materials.spec.ts` (nothing sent until "Read them"); design |
| A page that is a picture leaves the computer only at the learner's word (ADR-060) | Nothing is sent until "Read them" is pressed on that file; what is sent and to whom is one press away. The page is drawn by PDFium in the parser worker, and what the worker hands back is checked to be a PNG of a sensible size (`render_isolated`). It is sent only to a model seen to read pictures (`ModelSpec.images`); a provider without one is never asked, even when chosen | `test_reading_pictures.py`; `test_isolated_extraction.py`; `e2e/course-materials.spec.ts` |
| What a model reads off a picture is data | Kept as the page's text, cleaned, bounded (20,000 characters), trusted less (0.8), and quoted in a block like any document text when it is sent again | `test_reading_pictures.py`; `test_prompt_quoting.py` |

Document content is data. Nothing in a file is executed, followed, or treated as an instruction.

**Residual risks, accepted**

- The parser worker runs as the same OS user as the service, without an additional OS sandbox.
  A parser exploit could read what that user can read. It cannot return code to the service, and
  it has no channel to the renderer or the provider key (the key is not in its memory, its
  arguments, or its environment).
- A file within the limits can still be slow to parse; the time limit (120 s) bounds it.
- PDFium, which draws a page to be read, is a large C++ library reading a file from
  anywhere. It runs in the parser worker, with the same exposure as the parsers.
- A picture of a page may hold more than the learner meant to share (a name on a notebook's
  cover, a note in the margin). It is sent only at their word, a file at a time, and what
  is sent is said first.

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

## A course as a file

A course saved as a file, to give away or to move, and a new course made of one that was
brought in (a course's page, and the library). Reasoning:
`docs/decisions/ADR-063-a-course-is-saved-as-a-file-and-brought-in-from-one.md`.

A file that is brought in comes from anywhere. Everything below about bringing in assumes
someone hostile made it.

| Guarantee | Implementation | Verified by |
|---|---|---|
| Page script cannot say where a course is saved or which file one is brought in from | `window.adle.courses.*` take a course, a kind of file and four choices. Both dialogs are opened by the main process (`electron/main/course-files.ts`); a chosen file is known to the page by its name and a token, for that file, for half an hour | `e2e/security.spec.ts` (a path as an argument, as a field and as a token is refused or ignored; each question is still asked); `course-file-rules.test.ts` |
| The core is never told a place to write | It writes under `handover/` in its own folder, under a name it makes; the main process moves the file, finding it only by a name of that kind | `test_course_sharing.py`; `course-file-rules.test.ts`; `e2e/course-files.spec.ts` (nothing left behind) |
| The core's routes for it are the main process's alone | `courses.save_file`, `courses.look_at_file`, `courses.bring_in_file` are internal | `e2e/security.spec.ts`; `test_course_sharing.py` |
| Nothing in a file is extracted, and no name in it is a path | A member is read by a name the core made; a member of any other name, a folder, a locked member, or two of one name refuse the file | `test_course_file.py` (path-like names, other endings, a folder) |
| A file cannot make the core read without end | Each member is read up to a bound that ignores the size the file gives, and all of them against a bound on the whole; the count of members is bounded | `test_course_file.py` |
| A file changes nothing that is here | Bringing in always makes a new course; every identifier in a file is replaced by a new one, and none is looked up | `test_course_sharing.py` (no identifier shared; the course saved from is as it was) |
| A lesson from a file is no more trusted than one a model wrote | `parse_bundle` and `LessonService.store`: shape, text, references, and every scene through the policy; a scene runs only in the player frame | `test_course_sharing.py` (a scene that imports `os`, a lesson about a concept that is not there, text with an address: each left out) |
| A file cannot say what a learner knows | It has no field for a state. Answers are recorded again through `LearnerService.replay`, and every state is worked out here | `test_course_file.py`; `test_course_sharing.py` (a planted state refuses the file) |
| A file cannot make a curriculum that cannot be learned | Concepts and what they need go through `CurriculumService` | `test_course_sharing.py` (a loop is not made) |
| A file is never taken for Adle's own sample | A course from a file is from a topic or from materials, its lessons written elsewhere, and it says "Imported" | `test_course_sharing.py`; `e2e/course-files.spec.ts` |
| A document from a file is the one its text was read from, or it is not kept | Its size and SHA-256 must be what its entry says; it is stored under a generated name | `test_course_sharing.py` |
| A template carries nothing of the learner | No answers, no notes, no materials; lessons cite nothing and name no file | `test_course_sharing.py` (the file's bytes are searched) |
| Half a course is not left behind | The new course is deleted if anything fails | `test_course_sharing.py` |

**Residual risks, accepted**

- A course file is not encrypted. One that holds everything holds the text of the learner's
  materials and their answers; the dialog says what each choice puts in.
- Who wrote a lesson is what the file says, kept as names only. It can say anything; it is
  shown as a name and decides nothing.
- A document brought in with a course is as trusted as one the learner imported: it is read
  again only to draw a page as a picture, in the parser's own process.

## Lessons and answers

Details and reasoning: `docs/decisions/ADR-010-lesson-ir-and-playback.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| A lesson reaches the database only in a validated form | `lessons.bundle.parse_bundle`: strict models, unknown fields refused, every scene through the static policy, descriptions of scenes computed from their source. A picture added to a lesson that is already stored (ADR-031) goes in the same way: the whole lesson passes the gate again with the picture, or with that part in words | `test_lesson_ir.py`, `test_lessons_api.py`, `test_lesson_before_pictures.py` |
| Lesson text cannot carry links, markup, paths, or control characters | Text validators in `lessons/ir.py` | `test_lesson_ir.py` |
| A lesson cannot cite something that is not in the learner's materials | `LessonService.store` resolves every cited section inside the course | `test_lessons_api.py` |
| The renderer never holds an answer key | `lessons.get` returns the player view; scoring happens in the core. An id can be a key too: the items of an ordering question are shown under names made with a secret of the installation, in the order of those names (`ItemMask`), and their own ids are not accepted back | `test_lesson_ir.py` (field by field, and by searching the output); `test_answers_api.py`; `test_scoring.py`, `test_lessons_api.py` (the ids in order are refused) |
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

### A question asked during a lesson

The one thing a learner types that is sent to a provider is a question they ask about a part
of a lesson, when they press "Ask" (ADR-024).

| Guarantee | Implementation | Verified by |
|---|---|---|
| What is sent is said first, and nothing is sent before "Ask" | The dialog names the destination and lists what goes: the question, the part, the lesson's outline, the course and concept, related passages | `e2e/ask.spec.ts` (no request before the button; the request itself is read) |
| The learner's words cannot instruct the model | The question is placed in a quoted block whose closing tag cannot be forged, and the system prompt says it is something to answer, never an instruction | `test_asks.py` (a question that tries to close its block and speak as Adle) |
| A question the lesson is asking is never answered for the learner | The request carries the stem and the choices only: never which is right, accepted answers, the expected number, the rubric, the hint, or per-choice feedback; ordering items are sent sorted | `test_asks.py`; `e2e/ask.spec.ts` |
| Asking about an open question counts as help | The core records the next answer on that part as aided, like one given after the hint. Removing the note takes its words and leaves the fact; skipping the question shows its explanation, so the answer that follows a skip is an aided one as well | `test_asks.py`; `e2e/ask.spec.ts` (read from the database) |
| An answer cannot carry a link, markup, or a path, and cannot invent a source | Read strictly into one to four paragraphs of display text; a source is a number the prompt offered, or it is dropped | `test_asks.py` |
| The learner's own words are shown as text | Rendered as plain text, never as mathematics or markup | `e2e/ask.spec.ts` |
| A question costs a bounded number of requests | One, a second only if the first answer was unusable; one question per lesson at a time; 30 kept per lesson | `test_asks.py` |

## The model provider and its output

Details and reasoning: `docs/decisions/ADR-012-provider-quota-and-generation.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| A request goes only where the learner was told | The address is fixed at start-up; `https` only, or `http` on this computer; anything but the default is shown as "Custom endpoint (host)" | `test_provider_client.py`; `e2e/generation.spec.ts` |
| The key is in one header and nowhere else | Read from the vault per request; redirects not followed; environment proxy and `.netrc` not used | `test_provider_client.py` |
| Nothing sent or received is logged | Log lines carry a purpose and a status code only | `test_provider_client.py` (bodies and prompts absent from the log) |
| Nothing is sent that the learner did not start | Requests are made only inside a job the learner started; the suggestion dialog says what will be sent first; the lesson button says it beside itself | `test_generation_api.py`; `e2e/generation.spec.ts` |
| Nothing more is sent for what the learner has removed | Removing a lesson, or a course, stops the work under way for it: the request being made is let go of and no other follows (ADR-031) | `test_lesson_before_pictures.py`; `e2e/generation.spec.ts` |
| A learner's document cannot instruct the model through Adle | Learner text is quoted inside marked blocks whose closing tag cannot be forged; the standing rule is in the system prompt; the model has no tools. What a document is called (its file name, a heading) is quoted inside the block with the excerpt, and nothing in quoted text that could pass for the tag survives, in any spelling | `test_generation_api.py` (hostile document); `test_prompt_quoting.py` |
| Model output cannot enter the database unchecked | Draft parsed leniently, compiled deterministically, then `parse_bundle` (ADR-010); scenes through the static policy | `test_drafts.py`, `test_generation_api.py` |
| A model cannot invent an identifier or a citation | Identifiers are assigned by the core; a citation is a number the prompt offered, or it is dropped | `test_drafts.py` |
| A model cannot make Adle loop | A fixed number of requests per job; one request in flight at each provider; local limits under the provider's | `test_model_gateway.py`, `test_generation_api.py`, `test_provider_routing.py` |
| A provider's answer cannot fill the memory or hold the service up | Read with a bound on a line and on the whole, asked for uncompressed, with "Stop" and the time limit asked on everything that arrives; a document that is not a stream meets the same limits; text is tidied in one pass; "Stop" closes the answer | `test_provider_client.py` (a line that never ends, a stream of nothing, a document dripped slowly, a hang-up on stop); `test_drafts.py` |
| A notice the provider sends in the model's place is not taken for the model's answer, and its words cannot do anything | Recognised by the client (ADR-020) and raised as `provider_notice`; the words are made one line, cut at 300 characters, cleared of control and text-reordering characters, quoted, and shown as text with no link; never logged, never followed, never retried | `test_provider_notice.py`; `e2e/generation.spec.ts` (no link in the message; one request sent) |

**Residual risks, accepted**

- What is sent (the course's name, a concept and its objectives, a few words about where the
  learner stands on it, their pace, depth, and goal, a few passages, and a question the
  learner typed about a lesson) leaves the computer for a provider once the learner asks.
  With "automatic" that may be either provider they gave a key to. The providers' handling
  of it is outside Adle's control; the first-run screen and the settings say so.
- The choice of provider is changed by a call from the page, with no question asked outside
  it. A page that had been taken over could move a learner from one provider to "automatic".
  It could also read every course through the core, so this is not where that is stopped;
  the keys it would use are ones the learner gave (ADR-029).
- The ids of the options of a multiple-choice question follow the order the model wrote
  them in. They carry no key, only whatever habit a model has.
- A model can write a lesson that is valid and wrong. Validation checks form, not truth. The
  lesson says where it came from ("From general knowledge", or the passages it cites).

## Reading aloud

Narration is spoken by the browser's speech synthesis using **only voices that run on this
computer** (`localService`). A voice that would send text to a service is never listed or used
(`lesson/speech.ts`, `speech.test.ts`). The session's network filter would refuse such a
request in any case. See ADR-013.

### A natural voice (ADR-042)

| Guarantee | Implementation | Verified by |
|---|---|---|
| Nothing is downloaded but at the learner's word, and what and where from is said first | Settings says each voice's size beside "Set up", and where it downloads from one press away; the core starts a setup only when asked (`voice.install`) | `VoiceChoices.test.tsx`; `test_narration.py` |
| Only the files pinned are kept | Each model file is checked against its size and hash in `voice/catalog.py` (SHA-256, or Git's hash for a small file) after it arrives and before it is used; a file that differs is deleted. A redirect is followed and what arrives is checked, not where it came from | `test_voice_install.py` (a changed, a longer and a shorter file are each refused; a stopped download leaves nothing) |
| The programs are exactly the ones locked | pip installs the lock for this system with `--require-hashes --no-deps --only-binary=:all:`, from the Python Package Index and PyTorch's index only, with this computer's settings for pip and Python left out (`quiet_environment`) | `test_voice_install.py`; the CI audit of the locks |
| The programs never touch the core's | They go into an environment of their own, made with `python -m venv` from the core's Python; only that folder is ever removed | `test_voice_install.py` (removal keeps what another voice needs) |
| The engine reads only what was checked, and says nothing of what it speaks | `voice/engine.py` runs as its own process with `-I`, told it is offline before its libraries load, with models only from the voice's folder; its standard error is thrown away | `test_narration.py` with a stand-in engine; the real voices tried by hand (ADR-042) |
| A recording is reached by a name the core made, never by a path | A clip is named by a hash of the voice and the words, and asked for by that name (24 hexadecimal digits) under a lesson that exists | `test_narration.py` |

**Residual risks, accepted**

- **The engine is not shut off from the network by the system.** Its libraries are told
  they are offline and everything it loads is here and checked; a library that ignored that
  could reach the network from the engine's process.
- **The voice's programs carry advisories that were read and set aside** (ADR-042 lists
  them): each needs a model file Adle did not pin, or a part of a library the voice never
  runs. CI fails on any other.
- **The voice's programs are large and trusted as their publishers built them**: torch,
  transformers, Kokoro and Qwen3-TTS, from the Python Package Index and PyTorch's index,
  each by its hash.

## Privacy

- No telemetry, analytics, or crash upload. No external service other than the AI providers
  the learner gave a key to, and only when the learner asks for something they write; and,
  when the learner sets a natural voice up, its downloads from Hugging Face, the Python
  Package Index, PyTorch and GitHub, which carry nothing of theirs (ADR-042); and, when the
  learner sets the film maker up, its downloads from GitHub and the Python Package Index,
  which carry nothing of theirs either (ADR-065). Pictures of a
  file's pages go to a provider only when the learner presses "Read them" on that file
  (ADR-060).
- A notification of the operating system carries fixed words chosen in the main process by
  its kind (`electron/main/notices.ts`, ADR-026). The page cannot supply text for one, so no
  course title, lesson, or model output reaches the notification centre. None is shown while
  Adle's window has the focus, or when the learner has turned them off.
  Verified by `notices.test.ts` and `e2e/break.spec.ts`.
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
- Adle itself is under the GNU GPL, version 3 (ADR-033). Licences of what ships with it:
  MIT, ISC, BSD-3-Clause, Apache-2.0, MPL-2.0, OFL-1.1, PSF-2.0, all of which can be
  combined with it. Nothing under a copyleft or source-available licence is built from,
  shipped or not, until someone decides about it.
- The programs a natural voice is set up with are not shipped: they are downloaded at the
  learner's word, from locks with every hash (`adle_core/voice/data/`). CI audits those
  locks too, setting aside only the advisories ADR-042 lists.
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
| Every boundary in this document holds in the packaged app | The whole end-to-end suite runs against it unchanged | `npm run e2e:packaged`: every journey there is, including `security.spec.ts` and `scene-player.spec.ts` |

## Releases

Details and reasoning: `docs/decisions/ADR-034-installers-and-releases.md` and
`ADR-043-one-branch-and-a-release-commit.md`.

| Guarantee | Implementation | Verified by |
|---|---|---|
| What is published is what the repository builds, from a commit anyone can read | A release is made by CI from a commit `release: <version>` on `main`, once every check has passed for it, with the installers that were tried for that commit; nobody uploads a file or makes a tag. The version must be the one in `package.json` and the changelog, and not released from another commit | `ci.yml` (`release` and `publish`); `scripts/release-notes.mjs --tag` |
| The workflows can change nothing they do not need to | Every job has read access only, except the one that makes the release; no job is given a secret; a checkout leaves no credential behind | `permissions` and `persist-credentials: false` in `.github/workflows/` |
| An action cannot be swapped under a workflow | Each is named by the commit it was reviewed at, with its version beside it | `.github/workflows/` |
| A download can be checked | Every release lists a SHA-256 for each file | `SHA256SUMS.txt`, written by `ci.yml` |
| An installer never weakens the app it installs | No launcher passes `--no-sandbox`. On Linux the package installs Chromium's sandbox helper so that the sandbox can be built; where it cannot be, the app does not start | `scripts/installer.mjs --check` on every push: the installed app is started on a system as Ubuntu ships it |
| Installing or removing Adle does not touch a learner's data | The installers write only the program's own folder, a menu entry, and what the system needs to remove them again | The Windows try-out installs, starts and uninstalls with a profile of its own |
| Nothing looks for updates | No updater is installed and the app makes no request about versions | ADR-019; `e2e/security.spec.ts` (the session refuses everything) |

**Residual risks, accepted**

- **Nothing is signed.** Windows and macOS cannot tell a real Adle from a changed copy, and
  say so. The checksums help someone who checks them and nobody else. This is the owner's
  decision for now (ADR-034).
- **A release trusts GitHub's build machines** and the tools on them (Inno Setup, `hdiutil`,
  `dpkg-deb`, uv's Python builds, Electron's binaries).

## Not yet done

| Item | Milestone |
|---|---|
| Code signing and notarisation | The owner's decision for now (ADR-034). Windows warns about the program and macOS asks before opening it |
| Checking the archive's integrity at start-up (the fuse for it) | With signing; without a signature it adds little |
| OS-level sandbox for the parser worker (job object / seccomp / App Sandbox) | Not built. The worker is a separate, short-lived, isolated process that returns only checked JSON; see "Residual risks" under "Imported documents" |
| The end-to-end suite on macOS | NOT RUN. The app is built, installed and started there by every push; the journeys run on Windows and Linux |

## Reporting a problem

Report a security problem privately, not in a public issue: on
[the repository](https://github.com/XelXen/Adle) use **Security → Report a vulnerability**
where GitHub offers it, or contact the owner through their GitHub profile.
