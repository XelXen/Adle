# ADR-060: Pages that are pictures are read by the AI, at the learner's word

- **Status:** Accepted
- **Date:** 2026-11-24
- **Supersedes:** ADR-007 in "No OCR, and no upload to do OCR. Scanned PDFs are rejected";
  ADR-041 in leaving text in scanned pages to a model downloaded to this computer.
- **Keeps:** ADR-007 in everything else: a file is read on this computer, in a worker of its
  own; importing sends nothing anywhere. ADR-012: what the provider is asked is fixed per
  job. ADR-036: what is sent is one press away from the control that sends it.

## Context

A learner's notes are often a scanned notebook, photographs of pages, or handwriting. Adle
refused a PDF that was all pictures ("Adle does not run text recognition (OCR) and never
uploads files to do so") and skipped the picture pages of the rest. The owner asked: "what
if PDF is a scanned copy of a notebook? or handwritten notes", and allowed the rule against
uploading to go "if it's really required".

It is required for handwriting. A model small enough to download reads printed pages and
reads handwriting poorly. The providers' models that see pictures read both. On 2026-11-24
NVIDIA's Nemotron 3.5 Super, sent a typed page and a handwritten one as pictures, wrote
both out word for word, the drawing on the second described in one line, in 2 to 16 s a
page. AIHubMix's free model could not be tried: the account answered that it can make ten
requests until it is paid for.

## Decisions

- **A page with no text to select is kept as a picture**: a scan, a photograph,
  handwriting, or a page whose drawing the reader could not take apart. A PDF of nothing
  but pictures is imported, not refused. The file says which pages are pictures
  (`picture_pages`), and the learner is told in a sentence.
- **Nothing is sent until the learner presses "Read them"**, on that file, in Materials.
  What is sent, and to whom, is one press away: "Sends pictures of those 2 pages to NVIDIA
  NIM." Importing still sends nothing.
- **Each page is drawn on this computer**, in the parser worker, by PDFium (`pypdfium2`,
  BSD-3-Clause or Apache-2.0): gray, at 150 dots to the inch, a PNG of 100 to 200 KB. One
  page is one request: the picture and an instruction to write out the page as it reads,
  to describe a drawing in a line, and to add nothing.
- **Only a model seen to read a picture is sent one** (`ModelSpec.images`): Nemotron 3.5
  Super, today. A request to read a picture (`read`) goes nowhere else: with only AIHubMix
  chosen, or only AIHubMix with a key, nothing is sent, and the learner is told what would
  let the pages be read. Another model is added after it has been tried by hand.
- **What comes back is the page's text**, stored in its place among the file's pages,
  trusted a little less than a text layer (0.8): found by search, quoted in lessons and
  cited by its page like any other. It is data, never an instruction, as all of a learner's
  material is. "[no text]" leaves nothing.
- **The pages are read one by one**, each counted against the provider's allowance;
  removing the file stops the reading. A file whose original is no longer on this computer
  (after a restored copy) is imported again to be read.

## Alternatives

- **A text recognizer downloaded to this computer** (ADR-041's plan). Private, and weak
  on handwriting, the case that prompted this. It can come later beside this, for a learner
  who would rather send nothing.
- **Reading pictures as a file is imported.** Sends pages the learner has not seen
  described, and makes every import of a scan wait for the provider.
- **Sending a whole file at once.** One request for many pages saves allowance and makes a
  page misread harder to find, and a large PDF is more than a model takes.

## Consequences

- Scanned and handwritten notes can be taught from.
- A picture of a page leaves the computer only when the learner asks, to a provider they
  chose, and the provider's allowance pays for it: a page a request.
- What a model misreads stays misread until the page is read again or corrected; the
  section's lower confidence says that it was read from a picture.
