# Changelog

User-visible changes to Adle. The format follows [Keep a Changelog](https://keepachangelog.com/),
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Desktop app that opens without an account or an AI key.
- First-run welcome that explains what stays on your computer and what is sent to an AI provider.
- Library screen and navigation, with light and dark themes and a "follow system" option.
- Settings → AI provider: save, replace, or remove an AIHubMix key. The key is encrypted by the
  operating system and never displayed again.
- Settings → Privacy & data: a plain statement of what is stored locally and what is sent.
- Settings → About & diagnostics: status of the local service with a restart button, and a live
  check that interactive visuals work on this computer.
- Courses: create a course from a topic or from your own materials. The library lists your
  courses, most recently used first. A course can be deleted after a clear confirmation.
- Import course materials (PDF, Word .docx, Markdown, plain text) with a file picker or by
  dragging files in. Everything is read on your computer; nothing is uploaded.
- Each imported file shows what was extracted and flags anything doubtful, such as pages with no
  selectable text. Files that cannot be used are rejected with a reason and a next step.
- Search your materials and see the file and the page or section every passage comes from.
- Curriculum: see what a course teaches as a list or a map, in the order it will be taught.
  Add, rename, reorder, and remove concepts; write learning objectives; say what each concept
  needs first and why. A change that would make a loop is refused with the loop spelled out.
- Start a curriculum from the headings of your own materials, choosing which to keep. No AI is
  involved, and every concept stays linked to the place it came from.
- Link any concept to the passages in your notes that cover it.
- Tell Adle how well you already know a concept. It is treated as a claim to check, never as
  proof, and everything recorded about a concept can be read back with the reason for each
  change. Adle never shows a score.
- Settings → Learning: pace, how detailed explanations are, narration, captions, and your goal.
- A sample course, "Introduction to neural networks", that can be added from the library with
  one click and needs no AI key.
- Lessons: a lesson plays part by part with captions at your reading pace, a board that fills in
  as it goes, a transcript, and live pictures you can pause, replay, or have described in words.
  Nothing plays until you press Start. You can go back to any part you have reached.
- Things to try inside a lesson: change a value on the picture, or with the keyboard-operable
  controls shown beneath it.
- Questions inside a lesson: multiple choice, true or false, numbers, short answers, putting steps
  in order, and explaining in your own words. You can ask for a hint, say you are not sure, or
  skip. Each answer is explained, and you are told in words what it changed about what Adle
  believes you know. A wrong answer is never held against you twice.
- A lesson remembers where you stopped. A finished lesson can be gone through again, with every
  part open and no question blocking the way.
- Mathematics in lessons and questions is properly typeset.
- With an AI provider key, ask for a list of concepts for a course. You are told what will be
  sent before anything is sent, and nothing is added until you have looked at the suggestions
  and chosen. Suggestions that arrive while you are elsewhere wait for you.
- With a key, have a lesson written for any concept that has a learning objective. You see how
  far along it is and can cancel. If a picture cannot be made, the lesson is kept and that part
  is explained in words.
- Settings → AI provider shows how many requests Adle has sent today. Adle sends one request at
  a time, waits rather than exceed four a minute, and stops short of the provider's daily limit.
- Lessons are read aloud with a voice installed on your computer. Nothing is sent anywhere to
  do it. Choose the voice and volume in Settings → Learning, and switch reading aloud on or off
  inside a lesson. Without a voice, narration is shown as text.
- Your data is kept safe between versions: a copy is made before its format is ever changed.
- Interactive visuals run in an isolated frame; if one cannot run, a text explanation is shown
  instead and the rest of the lesson is unaffected.
- Full keyboard operation, visible focus, reduced-motion support, and text that scales to 200%.

### Changed

- Adle has its logo: the letters "a" and "d" as two linked rings. It appears in the app, in the
  window and taskbar icon, and the app's accent colour is now the logo's teal. Green is kept for
  one meaning only: something went well.

### Notes

- Only the first concept of the sample course has a ready-made lesson so far.
- Generated lessons depend on the AI provider. On the day this was written the provider was
  failing every request on its side; Adle reports that and saves nothing.
- A picture moves in step with its narration part by part, not sentence by sentence.
- Adle does not yet choose what you should do next or schedule reviews.
- Scanned PDFs are not supported: Adle does not run text recognition (OCR).
- There is no installer yet; the app runs from source.
