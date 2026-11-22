# ADR-043: One branch, and a release is a commit

- **Status:** Accepted
- **Date:** 2026-11-21
- **Supersedes:** the branches of CONTRIBUTING.md (work on `dev`, `main` moved forward at a
  release) and ADR-034's "a tag publishes". The rest of ADR-034 stands: the installers, how
  they are made and tried, and what the workflows may write.

## Context

Work went to `dev`, and `main` was moved forward to a commit of `dev` when a version was
released; pushing a tag `v<version>` then had GitHub build the installers again from that
commit and publish them. Two branches said the same thing a tag already says, which commit
a version was made from, and a release took three pushes in the right order.

The owner asked for one branch, `main`, and for releases to decide which commit a build is
made from: "canary builds (up to the latest commit) have to be built from source; alpha
builds (a pre-release of a version) are available in releases; stable builds also; alpha
and stable builds are triggered by a specific sort of commit".

## Decisions

- **One branch, `main`.** Everything lands there, in small commits. A short-lived branch
  for a pull request is still a branch off `main`, merged back into it.
- **Every push to `main` is checked whole and nothing of it is published:** the gates and
  unit tests, every journey on Windows and Linux, and the installers built and tried on all
  three systems, where they were built and on a machine that did not build them. What a
  check builds is kept one day, for the check. The latest commit, a canary, is had by
  building it from the source (`README.md` → Run from source).
- **A release is a commit whose subject is `release: <version>`,** in which `package.json`,
  the core and the changelog are given that version. An alpha is `0.2.0-alpha.1` and is
  published as a pre-release; a stable version is `0.2.0` and becomes the latest release.
  No other kind of version is published.
- **It is published only when every check has passed for that commit,** in the same run:
  the installers made and tried for the release commit, with their checksums, are attached
  to a release tagged `v<version>` at that commit. A later push stops the checks of an
  earlier one, but never those of a release.
- **What cannot be published is said before anything is built:** a subject that is not
  `release: <version>` of one of those two kinds, a version that `package.json` or the
  changelog does not have, or a version already released from another commit. Run again
  for the same commit, the release's files are replaced.
- **Tags are made by GitHub, never by hand,** and the job that makes the release is still
  the only one that can write.

## Consequences

- A release is one commit and one push. The release commit is pushed last, on its own: the
  run looks at the commit at the head of the push.
- The installers published are the ones every check passed with, not a second build of the
  same commit.
- `release.yml` is gone; publishing is the last job of CI.
- Nothing is published for an ordinary push. Anyone who wants what is newest builds it,
  which is what "canary" means here.
