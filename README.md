<img src="apps/desktop/assets/icons/icon.png" alt="" width="88" align="right">

# Adle

**Learn at your own pace. Understand for real.**

Adle (Adaptive Learning Environment) is a local-first desktop app that learns what you understand
and teaches what you need next. Give it a topic or your own course materials; it builds a
curriculum you can inspect, teaches each concept with narrated, interactive visuals, checks your
understanding with short questions, and adapts the next step to what you have actually shown.

> **Status: in development.** The whole learning loop works on the sample course: a curriculum,
> lessons with live pictures and questions, evidence about what you know, a suggested next step
> with its reason, practice, and reviews that come due. Your data can be copied to a file,
> restored, and deleted. It can be built into a folder that runs by itself; an installer and
> a lesson written by the real AI provider are still to come. See
> [`docs/engineering/PROJECT_STATE.md`](docs/engineering/PROJECT_STATE.md) for exactly what works.

## What works today

- The app starts without any account or key, explains what stays on your computer, and remembers
  that you have seen the welcome.
- Light and dark themes (or follow the system), keyboard navigation throughout.
- **Courses:** create a course from a topic or from your own materials.
- **Import** PDF, Word (.docx), Markdown, and text files by picking or dropping them. Adle shows
  what it extracted, warns about anything doubtful (for example scanned pages), and explains why
  a file was rejected.
- **Search your materials** and see the exact file and page or section each passage comes from.
- **Curriculum:** build the list of concepts a course teaches, by hand or starting from the
  headings of your materials. Give each one learning objectives, say what it needs first, and
  see the result as a list or a map. Adle keeps the order learnable and explains when it cannot
  do what you asked.
- **A sample course** you can add from the library with one click, without an AI key:
  "Introduction to neural networks", eight concepts from a single weighted sum to
  backpropagation, each with a complete lesson.
- **Lessons:** captions at your reading pace, a board that fills in as the lesson goes, live
  pictures you can pause, replay, try out, or read as a description, and questions that are
  explained whichever way you answer. A lesson remembers where you stopped, and tells you in
  words what your answers showed.
- **What next:** a course opens on one suggested step and the reason for it, with other things
  you could do instead. It is a suggestion; nothing is locked.
- **Where you are:** each concept is described in words (*Not assessed*, *Building
  understanding*, *Needs more evidence*, *Demonstrated for now*) with what is still missing.
  Never a score, and never from one answer.
- **Practice and review:** a few questions chosen for what your answers have not shown yet.
  Reviews come due after a gap that grows as you remember.
- **What your latest session showed:** right answers for each concept you worked on, what
  still needs evidence, and what is planned for review. When you come back it is there as
  "Last time".
- **Mix-ups are possibilities, not verdicts:** when more than one answer points the same way,
  Adle says so, asks a question that would show it, and lets you set it aside.
- **"This did not help":** skip ahead, ask for another kind of explanation, or do something
  else. You are never sent back through the same lesson.
- **With an AI key:** ask for a list of concepts for a course and choose which to keep; have a
  lesson written for any concept, in the way of explaining you choose. You are told what is
  sent, you can cancel, and nothing is added without you.
- **Read aloud:** lessons are read by a voice installed on your computer, with nothing sent
  anywhere. Without a voice, narration is shown as text.
- **Settings → Learning:** pace, explanation depth, narration, voice and volume, captions, and
  your goal.
- **Settings → AI provider:** choose between AIHubMix and NVIDIA NIM, and save or remove the
  key of the one you use. A key is encrypted by your operating system, never shown again, and
  only ever sent to the provider it is for. Adle never changes provider by itself.
- **Settings → About & diagnostics:** restart the local service and run a live check of the
  interactive visual runtime.

## Your data

- Course files, answers, and progress are stored only on your computer.
- One thing uses the internet: when you ask Adle to generate a course or lesson, the text needed
  for that request is sent to the one AI provider you chose (AIHubMix or NVIDIA NIM). Nothing is
  sent before you add a key and ask.
- No accounts, no analytics, no telemetry, no crash uploads.
- In Settings → Privacy & data you can save a copy of everything as one file, restore from a
  copy (what it replaces is kept, so a restore can be undone), and delete everything.

Details: [SECURITY.md](SECURITY.md).

## Run from source

Requirements: [Node.js](https://nodejs.org/) 22.12 or newer (24.3.0 is pinned), and
[uv](https://docs.astral.sh/uv/) for Python. Python 3.12 is installed by uv if missing.

```bash
npm run setup
```

```bash
npm run dev
```

`setup` installs the JavaScript dependencies, downloads the pinned Electron binary, and creates
the Python environment. `dev` builds the app, starts it, and restarts it when you change code.

Other commands:

| Command | What it does |
|---|---|
| `npm run build` then `npm start` | Build once and run the built app |
| `npm run check` | Format, lint, type-check, and run all unit tests (TypeScript and Python) |
| `npm run e2e` | Build and run the end-to-end tests in the real app |
| `npm run package` | Build Adle as a folder that runs by itself, in `apps/desktop/out/release/` |
| `npm run package:check` | Start that build on an empty profile and check that it comes up whole |

## A build that runs by itself

`npm run package` makes a folder with the app and a private Python for its local service.
Nothing else needs to be installed on the computer, and a Python that is already there is
never used. Zip the folder to move it; run `Adle` inside it to start.

It is a folder, not an installer, and it is not signed: Windows will warn before running it
and macOS will refuse. It has been built and tested on Windows only. Details and what is
still missing: [`docs/engineering/RELEASE_CHECKLIST.md`](docs/engineering/RELEASE_CHECKLIST.md).

## Configuration

| Setting | Where |
|---|---|
| AI provider | Settings → AI provider: AIHubMix (the one in use until you choose) or NVIDIA NIM. With NVIDIA, requests go to Kimi K3.1 Pro; while it is not available, Mistral Large 4 and then GLM 5.3 Flash stand in, and Adle says when that happened. |
| AI provider key | Settings → AI provider, for the provider in use. Get one from [AIHubMix](https://aihubmix.com/token) or from [NVIDIA](https://build.nvidia.com/settings/api-keys). On 2026-11-20 AIHubMix answered a new account that had never been topped up with a notice that it "can only try 10 times" on the free model, and that topping up raises the allowance. Adle shows such a notice as it stands. |
| Theme | Settings → Appearance |
| Provider address and model | Shown in Settings → AI provider (`https://aihubmix.com/v1` with `coding-kimi-k3-free`; `https://integrate.api.nvidia.com/v1` with its three models). For development, start with `ADLE_PROVIDER_BASE_URL` and `ADLE_PROVIDER_MODEL` set to use one endpoint of your own, or with `ADLE_PROVIDER_ENDPOINTS` set to a JSON object such as `{"nvidia": "http://127.0.0.1:9100/v1"}` to move a known provider: `https` only, or `http` on this computer. Another address is always shown as a custom endpoint, and is not given a key that was saved for the real one. |
| Narration voice and volume | Settings → Learning |
| Use a separate data folder | Start with the environment variable `ADLE_USER_DATA_DIR` set to an empty folder |

The free AIHubMix model allows 5 requests per minute, 100 per day, and one million tokens per day
per account (as published on 2026-11-19; the provider's page is authoritative). Adle paces itself
below those limits. NVIDIA publishes no daily limit for its models, so there Adle keeps to limits
of its own (4 requests a minute, 200 a day, three million tokens a day) and says that they are
its own.

NVIDIA's models think before they write. On 2026-11-20 a lesson's text took Kimi K3.1 Pro about
six minutes; Adle says what the model is doing meanwhile, and you can keep using the app.

## Troubleshooting

| Symptom | Try |
|---|---|
| "Local service needs attention" in the corner | Settings → About & diagnostics → **Restart service**. From source, make sure `npm run core:sync` has been run. |
| "Secure storage is unavailable" | Your system has no credential store Adle trusts (on Linux, install and unlock GNOME Keyring or KWallet). Everything that does not need AI still works. |
| A PDF is rejected as having no selectable text | It is a scan. Adle does not run text recognition (OCR) and never uploads files to do so. Convert it with an OCR tool first, or import the text in another format. |
| An import warns about skipped pages | Some pages had no text layer. The rest was imported, and the file is marked "Check extraction". |
| A visual does not appear | Settings → About & diagnostics → **Run check**. Lessons fall back to a text explanation when a visual cannot run. |
| Start completely fresh | Close Adle and delete its data folder (`%APPDATA%\Adle` on Windows, `~/Library/Application Support/Adle` on macOS, `~/.config/Adle` on Linux). This removes your courses and progress. |

Logs for the local service are written to `logs/core.log` inside the data folder. They do not
contain your key, your documents, or your answers.

## For contributors

Start with [AGENTS.md](AGENTS.md), then [CONTRIBUTING.md](CONTRIBUTING.md) and
[TESTING.md](TESTING.md). The product specification is [PLAN.md](PLAN.md).

## Licence

Not yet licensed for redistribution (`UNLICENSED`). Third-party components keep their own
licences; see `docs/decisions/ADR-001-stack-and-pins.md` and
`skills/wanim-scene-authoring/reference.md`.
