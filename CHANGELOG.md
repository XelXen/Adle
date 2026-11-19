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
- Your data is kept safe between versions: a copy is made before its format is ever changed.
- Interactive visuals run in an isolated frame; if one cannot run, a text explanation is shown
  instead and the rest of the lesson is unaffected.
- Full keyboard operation, visible focus, reduced-motion support, and text that scales to 200%.

### Notes

- Curricula, lessons, questions, and adaptive teaching are not available yet.
- Scanned PDFs are not supported: Adle does not run text recognition (OCR).
- There is no installer yet; the app runs from source.
