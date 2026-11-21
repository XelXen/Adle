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
> restored, and deleted. With a key for an AI provider (AIHubMix, NVIDIA NIM, or both
> together) it writes curricula and lessons for your own topics and answers questions in the
> middle of a lesson; a real model has done all three. There are installers for
> Windows, macOS and Linux on the [releases page](https://github.com/XelXen/Adle/releases); this is an alpha. See
> [`docs/engineering/PROJECT_STATE.md`](docs/engineering/PROJECT_STATE.md) for exactly what works.

## What works today

- The app starts without any account or key, explains what stays on your computer, and remembers
  that you have seen the welcome.
- Light and dark themes (or follow the system), keyboard navigation throughout. On Windows
  the window has a title bar of Adle's own.
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
- **Where you are:** each concept is described in words (*Not started*, *Learning*, *Nearly
  there*, *Understood*) with what is still missing. Never a score, and never from one answer.
- **Practice and review:** a few questions chosen for what your answers have not shown yet.
  Reviews come due after a gap that grows as you remember.
- **What your latest session showed:** right answers for each concept you worked on, what
  still needs evidence, and what is planned for review. When you come back it is there as
  "Last time".
- **Mix-ups are possibilities, not verdicts:** when more than one answer points the same way,
  Adle says so, asks a question that would show it, and lets you set it aside.
- **"This didn't help":** skip ahead, ask for another kind of explanation, or do something
  else. You are never sent back through the same lesson.
- **With an AI key:** ask for a list of concepts for a course and choose which to keep; have a
  lesson written for any concept, in the teaching style you choose. You are told what is
  sent and where before anything is, you can cancel, and nothing is added without you.
- **Ask a question during a lesson:** about the part in front of you, in your own words or
  with one press. The answer is kept beside that part. On a question the lesson is asking,
  you get help thinking it through, not the answer.
- **While a lesson is written** (a few minutes) Adle says about how long it takes, offers a
  break, and tells you when it is ready, with a notification if you are doing something else.
- **Read aloud:** lessons are read by a voice installed on your computer, with nothing sent
  anywhere. Without a voice, narration is shown as text.
- **Settings → Learning:** pace, explanation depth, narration, voice and volume, captions, and
  your goal.
- **Settings → AI provider:** use AIHubMix, NVIDIA NIM, or both ("Automatic": each for what
  it does best, and the other if one can't answer, which Adle always says). Save, test, or
  remove a key for each. A key is encrypted by your operating system, never shown again, and
  only ever sent to the provider it is for. With one provider chosen, nothing ever goes to
  the other.
- **Settings → About:** restart Adle's background service if something seems stuck, check
  that animations work on this computer, and open the folder of logs.

## Your data

- Course files, answers, and progress are stored only on your computer.
- One thing uses the internet: when you ask Adle to suggest concepts, write a lesson, or
  answer a question, the text needed for that request is sent to an AI provider you gave a
  key to (AIHubMix or NVIDIA NIM), named beside the button before you press it. Nothing is
  sent before you add a key and ask.
- No accounts, no analytics, no telemetry, no crash uploads.
- In Settings → Privacy & data you can save a copy of everything as one file, restore from a
  copy (what it replaces is kept, so a restore can be undone), and delete everything.

Details: [SECURITY.md](SECURITY.md).

## Install

Download the file for your system from the [releases page](https://github.com/XelXen/Adle/releases).

| System | File | Then |
|---|---|---|
| Windows 10 or 11 (64-bit) | `Adle-…-windows-x64-setup.exe` | Run it. It installs for you alone and asks for no administrator. |
| macOS, Apple processor | `Adle-…-macos-arm64.dmg` | Open it and drag Adle onto Applications. |
| macOS, Intel processor | `Adle-…-macos-x64.dmg` | The same. |
| Debian, Ubuntu and their kin | `Adle-…-linux-x64.deb` | `sudo apt install ./Adle-…-linux-x64.deb` |
| Any other Linux | `Adle-…-linux-x64.tar.gz` | Unpack it and run `Adle` inside. |

Nobody has signed these builds, and each system says so in its own way:

- **Windows** shows "Windows protected your PC". Choose **More info**, then **Run anyway**.
- **macOS** says Adle could not be checked. Try to open it once, then go to **System
  Settings → Privacy & Security** and choose **Open Anyway**. Or, in Terminal:
  `xattr -dr com.apple.quarantine /Applications/Adle.app`
- **Linux**, from the tarball only: on Ubuntu 24.04 and later an unpacked app may refuse to
  start, because the system does not let it build its sandbox, and Adle will not run without
  one. Use the `.deb`, which sets that up.

Each release lists a checksum for every file in `SHA256SUMS.txt`. Adle does not update
itself and never looks for a newer version: to update, install the newer one over the old.
Your courses and settings are kept apart from the program and stay where they are.

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

Run this way, the program your system sees is Electron itself, so Electron's name and icon
appear where the system names the program (Task Manager, the heading of a notification). The
window, its taskbar button, and the picture in a notification are Adle's. The packaged build
below is `Adle`, with Adle's own icon everywhere.

Other commands:

| Command | What it does |
|---|---|
| `npm run build` then `npm start` | Build once and run the built app |
| `npm run check` | Format, lint, type-check, and run all unit tests (TypeScript and Python) |
| `npm run e2e` | Build and run the end-to-end tests in the real app |
| `npm run package` | Build Adle as a folder that runs by itself, in `apps/desktop/out/release/` |
| `npm run package:check` | Start that build on an empty profile and check that it comes up whole |
| `npm run installer` | Wrap that build into the installer for this system, in `apps/desktop/out/installers/` |

## A build that runs by itself

`npm run package` makes a folder with the app and a private Python for its background service.
Nothing else needs to be installed on the computer, and a Python that is already there is
never used. Zip the folder to move it; run `Adle` inside it to start.

`npm run installer` wraps that folder into what a person downloads: a setup program on
Windows (it needs [Inno Setup](https://jrsoftware.org/isinfo.php)), a disk image on macOS,
a `.deb` and a tarball on Linux. Nothing is signed. The installers of a release are not
made by hand: GitHub builds them on each system, tries each one out there, and publishes
them when a version is tagged. How, and what is still missing:
[`docs/engineering/RELEASE_CHECKLIST.md`](docs/engineering/RELEASE_CHECKLIST.md).

## Configuration

| Setting | Where |
|---|---|
| AI provider | Settings → AI provider: Automatic (every provider you gave a key to; the setting a new installation starts on), AIHubMix only, or NVIDIA NIM only. With NVIDIA, requests go to Kimi K3.1 Pro; while it is not available, Mistral Large 4 and then GLM 5.3 Flash stand in, and Adle says when that happened. |
| AI provider key | Settings → AI provider, one for each provider you use; "Test key" asks that provider for one word. Get one from [AIHubMix](https://aihubmix.com/token) or from [NVIDIA](https://build.nvidia.com/settings/api-keys). On 2026-11-20 AIHubMix answered a new account that had never been topped up with a notice that it "can only try 10 times" on the free model, and that topping up raises the allowance. Adle shows such a notice as it stands. |
| Theme, notifications | Settings → Appearance. Text size: Ctrl (or Cmd) with + or − |
| Provider address and model | Shown in Settings → AI provider (`https://aihubmix.com/v1` with `coding-kimi-k3-free`; `https://integrate.api.nvidia.com/v1` with its three models). For development, start with `ADLE_PROVIDER_BASE_URL` and `ADLE_PROVIDER_MODEL` set to use one endpoint of your own, or with `ADLE_PROVIDER_ENDPOINTS` set to a JSON object such as `{"nvidia": "http://127.0.0.1:9100/v1"}` to move a known provider: `https` only, or `http` on this computer. Another address is always shown as a custom endpoint, and is not given a key that was saved for the real one. |
| Narration voice and volume | Settings → Learning |
| Use a separate data folder | Start with the environment variable `ADLE_USER_DATA_DIR` set to an empty folder |

The free AIHubMix model allows 5 requests per minute, 100 per day, and one million tokens per day
per account (as published on 2026-11-19; the provider's page is authoritative). Adle paces itself
below those limits. NVIDIA publishes no daily limit for its models, so there Adle keeps to limits
of its own (4 requests a minute, 200 a day, three million tokens a day) and says that they are
its own.

NVIDIA's models think before they write. On 2026-11-20 a lesson's text took Kimi K3.1 Pro about
six minutes, and its pictures about as long again. You can start a lesson as soon as its text
is written: its pictures appear in it as they are drawn. Adle says what the model is doing
meanwhile, and you can keep using the app or take the break it offers.

## Troubleshooting

| Symptom | Try |
|---|---|
| "Something needs attention" or "Adle has stopped" at the bottom of the side rail | Settings → About → **Restart**. From source, make sure `npm run core:sync` has been run. |
| "Secure storage is unavailable" | Your system has no credential store Adle trusts (on Linux, install and unlock GNOME Keyring or KWallet). Everything that does not need AI still works. |
| A PDF is rejected as having no selectable text | It is a scan. Adle does not run text recognition (OCR) and never uploads files to do so. Convert it with an OCR tool first, or import the text in another format. |
| An import warns about skipped pages | Some pages had no text layer. The rest was imported, and the file is marked "Check extraction". |
| A picture does not appear | Settings → About → **Run check**. Lessons fall back to a description in words when a picture cannot run. |
| Start completely fresh | Close Adle and delete its data folder (`%APPDATA%\Adle` on Windows, `~/Library/Application Support/Adle` on macOS, `~/.config/Adle` on Linux). This removes your courses and progress. |

Logs are written to the `logs` folder inside the data folder (Settings → About → **Open log
folder**). They do not contain your key, your documents, or your answers, and are never sent
anywhere.

## For contributors

Start with [AGENTS.md](AGENTS.md), then [CONTRIBUTING.md](CONTRIBUTING.md) and
[TESTING.md](TESTING.md). The product specification is [PLAN.md](PLAN.md).

## Licence

Copyright © 2026 XelXen.

Adle is free software: you can redistribute it and modify it under the terms of the
[GNU General Public License, version 3](LICENSE), as published by the Free Software
Foundation. It is distributed in the hope that it will be useful, but **without any
warranty**; without even the implied warranty of merchantability or fitness for a particular
purpose. See the licence for details.

Third-party components keep their own licences: `docs/engineering/THIRD_PARTY.md` lists every
one, and the packaged app carries that list, the licence texts, and Adle's own licence in
`resources/licenses`.
