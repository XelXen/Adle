# Changelog

User-visible changes to Adle. The format follows [Keep a Changelog](https://keepachangelog.com/),
and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **A lesson is something to watch.** Its pictures are on a wide, dark screen in either
  theme, with the words being said along the foot of it, one line at a time, the word being
  spoken marked. One press shows every line. "Full screen" gives the lesson the whole
  screen; Escape gives it back.
- **A lesson can be watched taking shape.** While it is written, the card says what is
  happening ("Planning the lesson", then "Writing" and the lesson's title), lists its parts
  by title as each one is begun, and keeps a clock moving. The bar counts parts, and
  moves without a measure while the model is still thinking instead of standing empty.
  Suggested concepts appear by name the same way.
- **Far fewer sentences.** What a request to an AI provider sends, and where it goes, is one
  press away from the button that sends it (the small "i" beside it) instead of written out
  beside every button; it is still said in full in Settings. What a lesson is made from and
  who wrote it is behind "About this lesson". Suggested concepts are asked for with one
  press: nothing is added until you have reviewed them, as before.

### Fixed

- A list of choices now follows the theme. In the dark theme it showed light words on a
  light ground.
- The sections of a course's Materials tab stand as far apart as sections do everywhere else.

## [0.1.0-alpha.1] - 2026-11-21

The first alpha of Adle, for Windows, macOS and Linux. Adle turns a topic or your own
materials into a curriculum you can inspect, teaches each concept with narrated pictures you
can try out, asks short questions, and chooses what comes next from what your answers show.
Everything stays on your computer. It comes with a sample course, "Introduction to neural
networks", that needs no key and no account.

This is a preview. It has been tested thoroughly on Windows and by automation on macOS and
Linux; nobody has yet learnt a subject with it.

### Added

- **Installers for Windows, macOS and Linux**, built and published by GitHub: a setup
  program for Windows, a disk image for macOS (Apple and Intel processors), and a `.deb`
  package and a tarball for Linux. Nothing is signed yet, so each system will ask before it
  opens one; the release page says what to choose.
- Adle is free software under the GNU General Public License, version 3. Settings → About
  says so, and leads to the source and the licence.
- Desktop app that opens without an account or an AI key.
- First-run welcome that explains what stays on your computer and what is sent to an AI provider.
- Library screen and navigation, with light and dark themes and a "follow system" option.
- Settings → AI provider: save, replace, or remove an AIHubMix key. The key is encrypted by the
  operating system and never displayed again.
- **A second AI provider: NVIDIA NIM.** Choose between AIHubMix and NVIDIA in Settings → AI
  provider. Each has its own key, which is only ever sent to that provider. Adle never
  changes provider by itself, and not while something is being written.
- With NVIDIA, requests go to Kimi K3.1 Pro. While it is not available, Mistral Large 4 and
  then GLM 5.3 Flash stand in. You are told this where you choose the provider, again while
  it happens, and afterwards with what was written.
- While a lesson is being made you can see what the model is doing: thinking it through, or
  writing. Suggested concepts say which model suggested them.
- "Use today" counts each provider separately, and says when the limits shown are Adle's own
  rather than the provider's.
- **Use both providers together.** With a key for each, "Automatic" (Settings → AI provider)
  sends what you are waiting for to the quicker one and long work to the one with more room,
  and asks the other if one cannot answer. Before anything is sent Adle says where it may go,
  and afterwards who wrote it. You can still choose one provider only.
- **Ask a question in the middle of a lesson.** "Ask a question" pauses the lesson and lets
  you ask about the part in front of you, in your own words or with a ready-made question
  ("Say this more simply", "Give me an example"). The answer is kept beside that part. If
  the part is a question for you, Adle helps you think and does not give the answer away.
- **Take a break while a lesson is written.** Adle says about how long the wait is, offers a
  break of that length, shows what it is writing from anywhere in the app, and tells you
  when it is ready, with a notification if you are in another window. Notifications can be
  turned off in Settings → Appearance.
- Check that a provider's key works, from Settings, before relying on it.
- The library opens with "Pick up where you left off": the next step Adle suggests in the
  course you were last in, with the reason for it.
- A lesson written by an AI can be removed from its concept, to make room for another way
  of teaching the same thing.
- A lesson that draws on your own materials says which passages, under its title.
- **Start a lesson as soon as it is written.** A lesson an AI writes can be opened when its
  text is ready, about half the wait there used to be. Its pictures are drawn meanwhile and
  appear in the lesson as they arrive; until then that part is explained in words. If one
  arrives while you are reading its part, it is offered, not sprung on you. "Stop" at that
  point stops the pictures and keeps the lesson. You are told once that the lesson is
  ready.
- A lesson an AI wrote says who wrote it, in one line under its title.

### Changed

- **Plainer words everywhere.** Shorter sentences, ordinary speech, and nothing about how the
  app works inside. Progress is now Not started, Learning, Nearly there, and Understood. An
  answer says who wrote it in one line: "Answered by Kimi K3.1 Pro on NVIDIA NIM. AI can
  make mistakes."
- **A darker, neutral dark theme.** Near black, with no green tint, and plain greys in the
  light theme too. The one filled button is a deep teal with a white label in both.
- **A title bar of Adle's own** on Windows and macOS: the window's buttons sit on the app's
  own surface, in its colours, and the system's band above it is gone. The window is moved
  by the strip along its top.
- Scroll bars are thin and quiet, without arrows.
- The side rail no longer says "Local service ready". It only speaks when Adle is starting
  or something has stopped.
- A picture that has not started shows a play mark instead of an empty frame; pressing it
  starts the lesson, like the Start button.
- Settings → AI provider and Privacy & data say the same things in a third of the space.
- **A new look throughout.** Titles, lesson text, and questions are set in a serif, and the
  interface around them in a quieter sans: Geist Serif, Geist Sans, and Geist Mono, one
  family. Corners, borders, and shadows are finer; the brand's teal is kept for the one
  thing to press.
- **A lesson has the whole window.** The side rail steps aside, your place in the lesson is a
  single strip across the top, and the controls float at the bottom edge.
- The side rail lists your courses, so any of them is one click away.
- The welcome shows what a lesson looks like.

### Fixed

- A small formula in a picture no longer loses a minus sign, or one bar of an equals sign,
  on a display set to 100% scaling. Pictures are now drawn at a size that suits the space
  they are shown in.
- Removing a lesson or a course now stops any work still under way for it, at once.
  Before, a request already on its way to the provider ran to its end.
- "Create a lesson with AI" no longer shows for a moment, with the wrong wording, while a
  concept's lessons are still loading.
- The loading mark sits in the middle of its frame.
- A question whose answer could not be written is now reported even if you had gone back to
  the lesson, and "Ask a question" can be opened again while an answer is on its way, to
  watch it or stop it. A question still being answered when you leave a lesson is picked up
  when you come back.
- A lesson or a list of concepts that could not be written is always reported, wherever you
  are. A break no longer announces a lesson that was ready before the break began.
- The library no longer says "Not set up" for a moment when a key is saved.
- At the smallest window size the rail keeps showing what is being written and a running
  break.
- Closing a dialog returns you to the button that opened it. Selecting text in a dialog and
  letting go outside it no longer closes it.
- A break taken at the end of a lesson returns to the course, not to the lesson's first part.
- "Your break is over" and "Your lesson is ready" arrive on time while the window is
  minimised, and a break's end is also said inside the app.
- Messages no longer appear underneath a dialog or on top of a lesson's controls, and what
  is said after an answer is scrolled clear of them.
- Skipping a question shows its explanation, so answering it straight afterwards now counts
  as an answer with help. So does answering after a question you asked and then removed.
- Testing a key just after replacing it now tests the new key.
- A white line at the edge of a picture in the dark theme.
- A tall dialog no longer reaches under the top edge of the window, where a press on its
  close button would have moved the window instead. While a dialog is open the top of the
  window keeps its own look, like the title bar it is.
- A lesson a model writes is checked for a way of colouring shapes that stopped its picture
  from running. The model is asked once more with the reason, instead of the picture being
  lost when the lesson is played.
- "Try it" is no longer said about a picture that is not there.
- A concept's lessons line up, whether or not a lesson can be removed.
- "Up next" is said once on a course's Learn tab, not twice.
- "Cancel" and "Stop" now take effect at once. They used to wait until the provider next
  sent something, which with a model that thinks before it writes could be minutes.
- The time a lesson takes is no longer described as "a minute or two".
- A lesson whose formulas the model wrote with single backslashes is now read as it was
  meant. Before, it was refused as unreadable and written again, or, worse, could have been
  accepted with its mathematics damaged.
- "Stop" now takes effect while a model is still thinking, not only once it has begun to
  write.
- Pictures written by the AI no longer show a curve as a filled shape when they switch
  between two curves.
- Settings → Privacy & data: a plain statement of what is stored locally and what is sent.
- **Save a copy of your data** as one file you can keep anywhere or take to another computer.
  Your AI provider key is not in it.
- **Restore from a copy.** The copy is checked first, and what it replaces is kept as a safety
  copy, so a restore can be undone. A copy from an older version of Adle is brought up to date;
  if anything goes wrong, your data is left exactly as it was.
- **Delete everything** Adle has stored on this computer, after a confirmation. Your key and
  copies you saved elsewhere are not touched.
- Every "what is sent" note now lists all of it, including your goal, your pace and depth
  preferences, and a few words about where you stand on the concept.
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
  one click and needs no AI key. All eight of its concepts have a full lesson: weights and bias,
  activation functions, the perceptron, forward propagation, loss, derivatives and the chain
  rule, gradient descent, and backpropagation. Each has animated pictures described in words,
  questions, and further questions for practice and review, so the whole of Adle can be tried
  without an AI provider.
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
- If the AI provider answers about your account instead of passing a request to the model
  (an allowance used up, a balance needed), Adle shows you what the provider said, in its
  own words, and does not spend a second request asking again.
- Settings → AI provider shows how many requests Adle has sent today. Adle sends one request at
  a time, waits rather than exceed four a minute, and stops short of the provider's daily limit.
- Lessons are read aloud with a voice installed on your computer. Nothing is sent anywhere to
  do it. Choose the voice and volume in Settings → Learning, and switch reading aloud on or off
  inside a lesson. Without a voice, narration is shown as text.
- A course now opens on **Learn**: one suggested next step with the reason for it, other things
  you could do instead, and where you stand on each concept in words. Adle never gives an order
  and never shows a score.
- Practice and review: a few questions on one concept, chosen for what your answers have not
  shown yet. Reviews come due after a gap that grows each time you recall something, and a
  question you answered today is not asked again today.
- When more than one answer points at the same kind of mix-up, Adle says so as a possibility,
  asks a question that would show it, and lets you set it aside with "That was a slip". One
  answer is never treated as a diagnosis.
- A slip (the right number with the wrong sign, for instance) is counted as partly right, not as
  a gap in understanding.
- "This did not help" in a lesson: skip to the next question, have the concept explained another
  way of your choosing, or do something else. Adle does not send you back through the same
  lesson, and after a run of answers that did not go well it says that stopping is fine.
- When creating another lesson for a concept you can choose how it should explain: pictures
  first, a worked example, an everyday comparison, the mathematics step by step, a calculation by
  hand, or leading questions.
- A lesson ends with what to do next, not only with what it covered.
- A course shows what your latest session showed: how many answers were right for each concept
  you worked on, what still needs evidence, and when each comes back for review. Coming back
  another day, it is there as "Last time". It is never a score, and wrong answers are not
  listed.
- A right answer to a question you mark yourself is now described as that, instead of as an
  answer you were unsure of.
- If the window stops working, Adle tells you and reloads it; your answers and progress were
  already saved. If the local service stops by itself, it is started again.
- Settings → About & diagnostics: "Show log files" opens the short log Adle keeps of its own
  failures. It stays on your computer and is never sent anywhere.
- After "That was a slip", the keyboard stays on the line it belonged to.
- Adle can be built into a folder that runs by itself, with its own private Python for the
  local service. Nothing else has to be installed, and a Python already on the computer is
  never used. There is no installer yet, and the build is not signed.
- Your data is kept safe between versions: a copy is made before its format is ever changed.
- Interactive visuals run in an isolated frame; if one cannot run, a text explanation is shown
  instead and the rest of the lesson is unaffected.
- Full keyboard operation, visible focus, reduced-motion support, and text that scales to 200%.

### Changed

- Adle has its logo: the letters "a" and "d" as two linked rings. It appears in the app, in the
  window and taskbar icon, and the app's accent colour is now the logo's teal. Green is kept for
  one meaning only: something went well.

### Security

- A page that had been taken over could have made Adle import a file of its choosing by
  handing over a forged list of "dropped files". It cannot any more.
- "No network" for the interface and for a lesson's pictures now also covers peer
  connections and name lookups, which are not requests and were not refused.
- The part of Adle that holds your data refuses a request before reading any of it unless
  it comes from Adle, and refuses oversized ones.
- If you chose one provider, its keys reach Adle's service only after that choice has; a
  start where the choice could not be applied hands over no key at all.
- A document's file name and headings are quoted like its text when a lesson is written, so
  they cannot pass for instructions.
- An ordering question no longer reveals its order to the interface.
- A provider's answer is read within limits on its size and time, and "Stop" hangs up.
- The log records what kind of error happened and where, never its text.
- A picture that floods the app with messages is ended, like one that hangs.
- Two requests arriving at the same moment can no longer start the same lesson twice, and
  the provider cannot be changed in the instant something starts to be written.
- A file far over the size limit is refused before it is read. What the separate process
  that reads documents says about a file is shown only if it is one of its known reasons.

### Notes

- Only the first concept of the sample course has a ready-made lesson so far.
- Generated lessons depend on the AI provider. On the day this was written the provider was
  failing every request on its side; Adle reports that and saves nothing.
- A picture moves in step with its narration part by part, not sentence by sentence.
- Adle does not yet choose what you should do next or schedule reviews.
- Scanned PDFs are not supported: Adle does not run text recognition (OCR).
- There is no installer yet; the app runs from source.
