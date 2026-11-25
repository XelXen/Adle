# ADR-065: A film of a whole course, made with ManimGX on the learner's computer

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** Code a model wrote was run only in the player's frame: a sandboxed page with
  no network. A chapter of a film is code a model wrote, run by an animation engine on the
  learner's computer, as a program of its own on a Python of its own. A chapter may be sent
  back to be mended up to three times, each time told what the engine found: everywhere
  else a model's work is asked for again at most once. There is a second download at the
  learner's word, the film maker, and a fourth lane of jobs.
- **Keeps:** ADR-012 (the number of requests is fixed, and said before anything is sent),
  ADR-021, ADR-023 and ADR-039 (where a request goes is the learner's choice, measured
  per kind of request), ADR-036 (what is sent is one press away), ADR-042 (a download only
  at the learner's word, every file by its hash), ADR-061 (how a lesson is formed, now
  for each chapter), ADR-029 (the page has no network: a film is fetched from the core),
  ADR-063 (the page names no place to save).

## Context

The owner, on 2026-11-24: "a one shot lesson generator button is a brand new thing- it will
launch a full on agentic harness like environment to generate a full video like 3B1B to
explain the full course in one go.... yes it will take time so it will ask the user to let
it go while it builds a perfect lesson.... it doesnt care much about time and rather focuses
on covering almost EVERYTHING it needs to again following the lesson axioms but applied to
full syllabus this time. this wont be interactive but rather just a video so it can use
manimgx", whose `inspect` "produces storyboards and 2D layout checks, which gives a model
something to verify besides 'the process exited with code zero'".

Tried by hand on 2026-11-24, on Windows 11 with an RTX 4080 Laptop GPU:

- ManimGX 0.1.1 installs from the Python Package Index into Python 3.13 or later (it needs
  3.13; the core runs on 3.12): 22 packages, all built files, about 210 MB on the disk.
- `inspect` runs a scene without making a video and prints each play with the line of the
  file it came from, every problem of layout (words over words, a line through words,
  something past the edge, text too small to read) with its time and line, and where and
  why a scene stopped. It exits with an error on any of them. `render` makes an MP4 (H.264
  and AAC) with subtitles beside it.
- A voice is any function from text to sound with the time of each word, so Adle's own
  natural voice reads a film, and nothing is sent to a speech service. The engine's own
  default voice is one (fal.ai), which is why every scene Adle plays is given Adle's.
- It is quick: twelve seconds at 1280 by 720 in about a second; a film of three chapters,
  147 seconds, in 4.8 seconds.
- Kimi K3.1 Pro (through NVIDIA) wrote a chapter on Newton's second law from a draft of the
  guide: its first file stopped (a formula colored with `tex_to_color_map`, which cut
  `\frac` at its `a`); told so, its second ran with a table past both edges; told so, its
  third ran with two faults left, both in the same table. 491, 159 and 230 seconds. The
  guide now says how to color a formula and how to fit a table.
- In the two films made by hand afterwards (2026-11-25), most of what the engine found
  was words in a box whose size the model had guessed, and arrows drawn across words. The
  guide now says to make a box around its words and to draw an arrow from the edge of one
  thing to the edge of another, where nothing written lies between.

## Decisions

1. **A film is a chapter for each concept of the course, in the order it is learned**,
   after an opening Adle writes (the course's title and what the film covers). Each
   chapter is one complete ManimGX file written by a model, asked for as a kind of request
   of its own (`film`: Kimi K3.1 Pro first at NVIDIA, a model made for code, then the
   others), from the concept's title, summary, objectives, the chapters it builds on and
   passages of the learner's materials about it, with the rules of every lesson and what
   the course's subject needs (ADR-061), and one chapter as an example of the form.
   Such a request may take half an hour where any other is given up on sooner (a
   silence of three minutes still ends it): a chapter is a long file a model thinks
   over for minutes, and nobody is waiting for it.
2. **A chapter is checked before any of it runs**, by a policy written for this
   (`film/policy.py`, its names written down from the pinned engine by
   `scripts/dev/film_names.py`): only `import manimgx as m`, `numpy as np` and `math`;
   one scene; the engine's names and members as listed, and nothing that names a file, a
   picture from a file, a sound, a voice, the typesetter's own code, the engine's settings,
   the film being made, or three dimensions; no name or attribute that begins with an
   underscore; a few of Python's own names, and none that can look inside an object or run
   text; no `while`, `try`, `with`, `global`, decorators or `**`; no text with an address,
   a path, or a typesetter's command that reads a file; and what is said is one plain
   literal line of words, with its brackets whole and one animation for each of them
   (the engine stops at the first line that has not; the policy names every one). Three
   slips are mended rather than sent back (as for a lesson, ADR-047), and the file is
   then checked as any other: an engine name used bare, `WHITE` for `m.WHITE`, which the
   first chapter of the first film made by hand had; `np` or `math` used and not
   imported; and a line with more bracketed spans than animations, whose spans after the
   last animation lose their brackets, so that what is said stays the same (the first
   chapter of the second film had two such lines, and lost a request to them). A line
   with fewer spans than animations is sent back: which words an animation belongs to is
   not Adle's to guess.
3. **Then it runs, alone, in the engine, without making a video** (`inspect`): with Adle's
   voice, in a folder of the film's own, with nothing of this computer's in its environment
   (no setting for Python, no profile, a proxy that leads nowhere: its home is a folder of
   the film maker's own), with the network taken away inside its own process by the file
   Adle writes around it, and for five minutes at most. That home is kept between runs.
   In a home that had never been used the engine's first run never ended (not in ten
   minutes), and once it had been ended, after as little as five seconds, every later run
   took two (2026-11-25): what it sets up for the graphics driver is kept in the home. So
   the setup's trial and every film begin with a small scene that is ended after twenty
   seconds if it has not ended by itself, and a chapter that runs out of time is looked
   at once more before it is blamed. What the engine found is told to the model by the line of its own file, and the
   model writes the whole file again: **three times at most**. The version that ran with
   the least wrong is kept; a chapter none of whose versions ran is told in words by Adle
   (its title, and its objectives one at a time). Everywhere else a model's work is asked
   for again at most once (ADR-012, ADR-038). A film is the exception because nobody is
   waiting for it, and because what is wrong is found by the engine at every moment, by
   line, and not by a learner in front of a broken picture. The bound is said before
   anything is sent: one request for each chapter, and up to three more for each.
4. **Each chapter's lines are recorded in the natural voice that reads lessons** while the
   next chapter is written, in the voice lane, into the film's folder. The engine is given
   each line's recording and when each word is said, a time for every word as it counts
   them, so an animation begins as the words it belongs to are said. Without a natural
   voice a film has no sound, and its words show as it plays.
5. **The chapters are put together and made into a video**: each chapter a module of its
   own, run in turn on one stage, each beginning on an empty stage with the camera as it
   was; looked at whole; a chapter that ran alone and stops once joined is told in words;
   then rendered at 1920 by 1080, 30 frames a second, with subtitles. One film a course, in
   `films` (revision 0016), its video and subtitles under `films/<id>/`.
6. **It is made in a lane of its own** (`LANE_FILM`): lessons go on being written while a
   film is made. It can be stopped. A film stopped, failed, or left when Adle closed is
   unfinished, and continuing it begins at the first chapter not kept. Removing the film or
   its course stops the work and takes its files.
7. **The film maker is downloaded only at the learner's word**: a standalone Python 3.13.18
   from python-build-standalone's release on GitHub, kept only if its size and SHA-256 are
   the pinned ones and unpacked with nothing let out of its folder; then ManimGX 0.1.1 and
   what it needs from the Python Package Index, by the lock for this system, every file by
   its hash, built files only (`scripts/dev/film_locks.sh`); then the engine draws a circle
   here, or it is not set up. About 110 MB downloaded on Windows and 300 MB on the disk.
   Offered on Windows (x64), Linux (x64 and ARM) and macOS (Apple and Intel). Removing it
   takes its folder and nothing else; films already made are kept.
8. **The page plays a film it fetched from the core**, a megabyte at a time, as a video of
   its own (`blob:`, already allowed for media), with its subtitles made into WebVTT in the
   page as plain text. The page names a film by its id. Saving it where the learner chooses
   is the shell's, as for a course (ADR-063): the core writes it into its own folder, the
   shell asks where and moves it, its subtitles beside it. When a film is ready, the app
   says so wherever the learner is, and the operating system does too when Adle is behind
   other windows (`film_ready`, words fixed in the main process, ADR-026).

## What this is not

- **The operating system's sandbox.** The engine runs as the learner, on their computer.
  What keeps a chapter in is, in order: the policy, which refuses every way out it knows of
  and every name it has not been given; the engine, which hands text to its typesetter only
  escaped (tried by hand: `#read(...)` in a text or a formula is set as text, and
  `\input` is an unknown command); the file Adle writes around a chapter, which takes the
  network away from the process before the chapter is imported; an environment with
  nothing of the computer's in it and a proxy that leads nowhere; and a time limit. A
  policy is a list, and a way out it does not know of is a way out. That is the risk this
  decision accepts, for films alone; a lesson's pictures stay in the player's frame.
- **Interactive.** A film is watched.
- **Quick.** Several minutes a chapter, most of it the model's; a course of a dozen
  concepts is hours.

## Alternatives

- **Wanim in the player's frame**, the lessons' own engine, sandboxed: it reports no layout
  a model could be told, renders no video, and would keep a page busy for hours.
- **Manim Community Edition**: needs LaTeX, FFmpeg and Cairo installed on the computer, and
  reports nothing about layout.
- **ManimGX in the page** (its player runs takes in a browser): it cannot render a video
  there, and the page has no files.
- **An agent with tools that runs the engine itself**: a model would choose what runs on
  the learner's computer. Here Adle runs the engine and tells the model what it found.
- **A container or a virtual machine**: not on every learner's computer, and not something
  an app should install.
- **The engine's own voice**: a service on the internet with a key of its own.

## Consequences

- A whole course can be watched from start to end, and saved as a video to keep or share.
- A film costs up to four requests a chapter, and an hour or more.
- A second program runs code a model wrote outside the frame. Its policy and its names
  belong to the pinned engine: a new version of ManimGX is `scripts/dev/film_names.py`,
  `scripts/dev/film_locks.sh`, the sizes in `film/catalog.py`, and a film made by hand.
- ManimGX's own licence is MIT, with GPL-2.0-or-later, LGPL and others for what it
  bundles. It is a program the learner downloads, not part of Adle, as the natural voice's
  programs are not.
