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

### Changed

- **A new look throughout.** Titles, lesson text, and questions are set in a serif, and the
  interface around them in a quieter sans: Geist Serif, Geist Sans, and Geist Mono, one
  family. Corners, borders, and shadows are finer; the brand's teal is kept for the one
  thing to press.
- **A lesson has the whole window.** The side rail steps aside, your place in the lesson is a
  single strip across the top, and the controls float at the bottom edge.
- The side rail lists your courses, so any of them is one click away.
- The welcome shows what a lesson looks like.

### Fixed

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

### Notes

- Only the first concept of the sample course has a ready-made lesson so far.
- Generated lessons depend on the AI provider. On the day this was written the provider was
  failing every request on its side; Adle reports that and saves nothing.
- A picture moves in step with its narration part by part, not sentence by sentence.
- Adle does not yet choose what you should do next or schedule reviews.
- Scanned PDFs are not supported: Adle does not run text recognition (OCR).
- There is no installer yet; the app runs from source.
