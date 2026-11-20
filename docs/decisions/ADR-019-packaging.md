# ADR-019: The packaged app carries a private Python; one build is for release and one for tests

- **Status:** Accepted
- **Date:** 2026-11-19
- **Builds on:** ADR-001 (the stack), ADR-002 (the core process), ADR-004 (scene isolation).

## Context

Until now Adle ran only from a checkout: Electron loading built files, and the core started
from a development environment made by uv. A learner has neither. The plan asks for a clean
installation that starts and runs the sample course, and several earlier decisions were
marked "verify again in a packaged build", scene isolation above all.

Two things had to be chosen: how the Electron side is packed, and how a Python service is
shipped to a computer that has no Python, or has one that must not be used.

## Decisions

- **The app is packed with `@electron/packager`**, the tool maintained with Electron itself,
  into a folder: the executable, `resources/app.asar`, and `resources/core/`. Everything the
  app needs at run time is already bundled into `dist/` by the build, so the archive holds
  `package.json`, `dist/`, and the icons, and there is no `node_modules` to ship or audit.
- **The core ships as a private Python, not as a frozen executable.** The interpreter is the
  relocatable build that uv manages for development, copied without the parts the core never
  uses (tests, Tk, IDLE, pip, headers), with the dependencies from `uv.lock` installed into
  it against their hashes, and the core installed as a wheel so that its data files
  (migrations, the sample course) travel with it. Everything is compiled to bytecode at
  build time, because an installed copy may sit where it cannot write.
  - A freezer (PyInstaller and the like) was the alternative. It needs hand-kept lists of
    imports it cannot see and of data files, fails at run time when one is missed, and its
    licence needs an argument. A plain interpreter runs the same code the tests run, the
    same way.
- **The private Python is cut off from the computer it runs on.** It is started with `-I`:
  no `PYTHON*` variables, no packages from a Python the user has, nothing imported from the
  current folder. The parser worker it starts inherits the same flags
  (`ingestion/extract.py`), since it is the worker that reads files from elsewhere. The
  start-up check sets a hostile `PYTHONHOME` and `PYTHONPATH` and a bare `PATH` to prove it.
- **On Windows the interpreter is renamed `adle-core.exe`**, so the process is listed as
  what it is. Elsewhere it keeps its name; renaming is not safe there.
- **The binary's fuses are set** so that it cannot be turned into something else: it will
  not run as plain Node, will not take Node options from the environment, loads its code
  only from the archive, and gives `file:` pages nothing extra.
- **Two builds from one script.** `npm run package` makes the release build, with the
  debugger switches off. `npm run package:test` makes the same build with them on, because
  that is the only way a test tool can drive an Electron app; it is never given to anyone.
  `npm run e2e:packaged` runs the whole end-to-end suite against it, unchanged.
  `npm run package:check` starts the release build from outside and checks what a working
  start leaves behind, since nothing can look inside it.
- **No telemetry half arrives unnoticed.** FastAPI depends on the interface of a telemetry
  library; without the library's other half nothing is recorded or sent. The build fails if
  that other half is ever present.

## Not built

- **Installers** (NSIS, MSI, DMG, AppImage) and **code signing**. The output is a folder that
  runs where it is put. An installer and a signature are needed before giving it to people
  who are not developers: Windows will warn about an unsigned program, and macOS will refuse
  one. Both need the owner's certificates.
- **macOS and Linux builds.** The script has the paths for both and has been run on neither.
- **Automatic updates.** There is no update server, and the app makes no network request to
  look for one.
- **Checking the archive's integrity at start-up** (the fuse for it). It needs support in
  the packaging step that was not verified here; without signing it adds little.

## Consequences

- The folder is about 460 MB, of which Electron is about 357, the core 93, and the app 9.
  It has not been zipped and measured.
- The first start of a fresh build is slower than later ones (3.6 s and 6.8 s for two
  builds, against about one second, measured here) while the operating system examines
  files it has not seen. The interface shows "Local service starting…" meanwhile.
- The packaged core starts faster than the development one (0.9 s against 2.3 s here),
  because its bytecode is already compiled and it does not look at the environment.
- Scene isolation, the bridge surface, the network block, and every journey are verified in
  the packaged build by the same tests that verify them in development.
- Upgrading Python or a dependency is `uv lock` and a rebuild; nothing else lists them.
