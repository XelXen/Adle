# ADR-033: Adle is free software under the GNU GPL, version 3

- **Status:** Accepted
- **Date:** 2026-11-21

## Context

The repository was marked `UNLICENSED` until its owner chose a licence, which had to happen
before anything was published. On 2026-11-21 the owner chose: "GPL v3".

## Decisions

- **Adle is under the GNU General Public License, version 3.** `LICENSE` holds its text as
  the Free Software Foundation publishes it. The copyright is the owner's, under the name
  the repository is published by.
- **Version 3 only** (`GPL-3.0-only` wherever a licence is named by a short identifier):
  the owner said "v3" and nothing about later versions. Whoever holds the copyright can
  widen that later; it cannot be narrowed for copies already given out.
- **Whoever is given the app is given its terms.** The packaged app carries the licence in
  `resources/licenses/LICENSE.txt`, beside the notices of everything it is built from, and
  the start-up check fails a package without it.
- **The app says so where a person would look.** Settings → About says that Adle is free
  software under this licence, that it comes with no warranty, and that it may be shared and
  changed; and it leads to the licence and to the source. These are two more of the fixed
  pages the app may open in the browser (`EXTERNAL_LINKS`); nothing new crosses the bridge.
- **What Adle is built from must be compatible with it.** Everything that ships today is
  under MIT, BSD, ISC, Apache-2.0, MPL-2.0, the Python licence, or (the fonts) the SIL Open
  Font License, all of which can be combined with the GPL, version 3. The licence check
  still refuses copyleft and source-available licences until someone decides about one:
  some of them cannot be combined with this one at all.

## Consequences

- Anyone may run, study, share and change Adle, and whoever passes it on, changed or not,
  owes the next person the same and the source. A release on GitHub carries its source.
- A lesson a model writes, a learner's courses and their answers are not the program, and
  the licence says nothing about them.
- A dependency under a licence that cannot be combined with the GPL, version 3 (GPL-2.0
  only, for one) can never be added, whatever it would be useful for.
