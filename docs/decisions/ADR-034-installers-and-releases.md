# ADR-034: Installers made with each system's own tools, built and published by GitHub

- **Status:** Accepted
- **Date:** 2026-11-21
- **Builds on:** ADR-019 (the packaged app), which left installers, macOS and Linux, and
  signing as "not built".

## Context

Adle could be built into a folder that runs by itself, on Windows, by someone with the
project on their computer. The owner asked for installers, for Windows, macOS and Linux
alike, built and published by the repository on GitHub, without signing: "no need for
signing, add an installer yourself and make a CI/CD".

The usual tool for this, electron-builder, was tried first. Wrapped around the folder Adle
already builds, it brought about 290 more packages into the lock file, six advisories into
an audit that had none, and an install script. All of that to copy a folder into three
kinds of archive.

## Decisions

- **Each system's installer is made by a tool that system already has**, from the release
  folder exactly as `scripts/package.mjs` leaves it (`scripts/installer.mjs`):
  - **Windows:** a setup program made with Inno Setup, which GitHub's Windows machines
    have. It installs for the person running it, with no administrator; asks Adle and its
    background service to close before their files are replaced; and removes on uninstall
    what it installed.
  - **macOS:** a disk image made with `hdiutil`, holding the app and a link to
    Applications, one for Apple's processors and one for Intel's.
  - **Linux:** a `.deb` made with `dpkg-deb`, with a menu entry and icons, and a tarball of
    the folder for every other system.
- **A learner's courses and settings are never touched by installing or uninstalling.**
  They are kept elsewhere (the system's own place for an app's data).
- **Nothing is signed**, by the owner's decision. Windows and macOS say so to whoever opens
  a build, and the release says what to choose then. One thing is done that looks like
  signing and is not: on macOS the app is given the signature anyone can make ("ad hoc"),
  because a Mac with Apple's processor will not start a program whose signature does not
  match its files, and the fuses change them.
- **On Linux the package makes the sandbox work; nothing ever turns it off.** Chromium's
  sandbox helper is installed as root's and marked to run as root, which is what lets the
  sandbox be built where a system keeps namespaces from ordinary programs (Ubuntu 24.04 and
  later). Unpacked from the tarball on such a system, the app refuses to start rather than
  run without a sandbox. No AppImage is made: launched that way an app cannot have that
  helper, and the usual answer is to start it with the sandbox off.
- **Every installer is tried out where it is built, and again where it was not.** The
  installer puts the app on the build machine, the app is started from outside with an
  empty profile as the start-up check does, and it is taken away again. That machine has
  everything the app was built from, so an app that leaned on any of it would still start
  there. The same files therefore go to a second machine of the same system, which has
  Node, the scripts that do the trying and nothing else of the project, and are installed,
  started and removed there. This runs for every push, on all three systems, so packaging
  cannot rot unnoticed. That second machine is the nearest thing to a learner's computer
  that can be had with every push.
- **A tag publishes.** Pushing `v<version>` builds the installers again from that commit,
  writes their checksums, and attaches both to a release, marked as a pre-release when the
  version has a hyphen in it. The tag must be the version in `package.json`, and the
  changelog must have that version, or nothing is published.
- **The workflows can write nothing they do not need to.** Every job reads the repository
  and no more, except the one that makes the release. Actions are named by the commit they
  were reviewed at, not by a tag that can be moved.
- **Still no updates.** The app does not look for a newer version, and no installer leaves
  anything behind that does (ADR-019).

## Consequences

- No new dependency, and the audit stays empty.
- The installers are plain: no custom pictures, one language. They do the three things an
  installer is for.
- The Windows installer cannot be made on a computer without Inno Setup, and none of the
  three could be tried on the computer Adle is developed on. They are checked by the build
  machines, on every push.
- A Mac asks before opening an app signed this way that came from the internet, and since
  macOS 15 the way through is in System Settings. This is the price of not signing.
- The private Python must be one that uv manages. A build machine has a Python of its own
  of the right version, and an environment made from that one would have had the whole of
  `/usr` copied into the app; the package script refuses any other, and the workflows ask
  uv for its own.

## Not done, and why

- **Signing and notarising.** Needs certificates the owner has decided against for now.
- **Windows on ARM, Linux on ARM.** GitHub has machines for both; nobody has asked.
- **An RPM, a Flatpak, a Snap, a winget or Homebrew entry.** The tarball covers the systems
  the `.deb` does not; the rest is distribution, which can follow people actually using it.
- **Checking that a build can be reproduced bit for bit.** The inputs are locked; the
  archives carry times.
