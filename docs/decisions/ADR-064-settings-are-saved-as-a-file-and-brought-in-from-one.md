# ADR-064: Settings are saved as a file, and brought in from one

- **Status:** Accepted
- **Date:** 2026-11-24
- **Changes:** A provider key lived in the operating system's secure storage and in the
  core's memory, and nowhere else. It may now also be in a settings file the learner saves,
  locked with a password they chose. The bridge gains three functions, and the core three
  routes that only the desktop shell may call.
- **Keeps:** ADR-021 (a key goes to its own provider, at the address it was given for, and
  nowhere else), ADR-023 (which providers may be used is the learner's choice, and nothing
  else changes it), ADR-042 (a natural voice is downloaded only at the learner's word),
  ADR-029 (the page names no file), ADR-016 (a copy of the data holds no key).

## Context

The owner, on 2026-11-24: "importable and exportable settings, which includes API keys too,
and other settings; though if the setting is unavailable on the machine importing the
config, it either processes the thing (if voice isn't downloaded yet), or goes to closest (if
expressive isn't available then natural), or lastly resets to default. And this export and
import is also configurable in a dropdown while doing so."

Settings are in three places, on purpose: the look of the app with the main process (so
that the first paint is right), the learner's preferences and their voice with the core, and
the choice of provider and the keys in the system's secure storage, read only by the main
process. A settings file has to be put together from all three, and one of them is the most
sensitive thing Adle holds.

## Decisions

- **A settings file is one JSON document** with up to five parts: appearance (the theme,
  and whether the computer says when something is ready), learning (pace, how much is
  explained, reading aloud, the goal), voice (which reads the lessons, who speaks in it),
  the AI provider chosen, and the API keys. All five are saved unless the learner leaves
  some out; all that a file has are brought in unless the learner leaves some out. The
  four that are not keys sit under "Advanced", closed.
- **Keys go into a file only locked with a password**, typed twice as the file is saved and
  once as it is brought in. The key for the lock is made from the password with scrypt
  (N = 32768, r = 8, p = 1, a new salt each time) and the keys are encrypted with
  AES-256-GCM, so a changed file does not open. No password, no keys: the file is saved
  without them. The owner asked for the keys to be in the file; a file with keys in the
  clear would be what every other rule about a key exists to prevent, the moment it is put
  in a shared folder or sent to oneself.
- **The main process does all of it** (`settings-file.ts`, `settings-files.ts`). It reads the
  keys from secure storage, locks them, and writes the file; it reads a file, unlocks the
  keys and stores them. The page is told whose keys a file has, by the provider's name, and
  types the password. A key is never sent to the page, and the core is given one only for
  its own provider, as always.
- **A key is named by its provider and never by an address.** One brought in is kept for
  the address this installation sends that provider's requests to. A file cannot send a key
  anywhere else, and a key for a provider this installation does not offer is not kept.
- **A wrong password changes nothing.** The keys are unlocked before anything is applied.
- **What cannot be had here as the file has it** is handled as the owner said, in this
  order, and each time it is said to the learner afterwards:
  - **a voice that is not on this computer, and would run here, is set up**: but only if
    the learner leaves that ticked, having been shown what is downloaded and from where
    (ADR-042 stands: bringing in a file is not by itself the learner's word for a download
    of half a gigabyte). Until it is ready the voice in use goes on reading;
  - **a voice this computer cannot run becomes the nearest one it can**: the Expressive
    voice without a suitable graphics card becomes the Natural voice (set up the same way
    if it is not here);
  - **where no voice runs, the computer's own reads**;
  - a preference with a value this Adle does not know is left as it is here, one setting
    at a time (`from_stored`): a setting is never worth refusing a file over;
  - the name of one of the computer's own voices that this computer does not have is kept,
    and the lesson reads in the default, as it already did for a voice that went away.
- **A provider chosen in the file that is not offered here changes nothing.** The choice
  here stays as it is, and that is said. It is not "reset to the default", which is
  Automatic: that could send a request to a provider the file's owner had chosen not to
  use, and where requests go changes only as the learner says.
- **The core's part has routes of its own, internal, with no path and no key in them**
  (`settings.save_file`, `settings.look_at_file`, `settings.bring_in_file`). Looking says
  what a file's voice would be here, and changes nothing.
- **The page never names a place**, as for a course (ADR-063): where a file is saved and
  which is read is asked in a window of the operating system, and a chosen file is known to
  the page by a token.
- **After bringing settings in, the page begins again** once the learner has read what
  happened: everything on it was read before the settings changed.

## Alternatives

- **Keys in the clear, with a warning.** What a browser does when it exports passwords. The
  warning is read once and the file lasts.
- **Keys left out altogether.** Safest, and not what was asked: typing two long keys again
  on another computer is the part of moving that a file can spare.
- **Locking the keys with the operating system's storage.** That is tied to this account on
  this computer, which is exactly where the file is leaving.
- **A password for the whole file.** The other four parts are not secret, and a file that
  can be read can be checked by its owner. Only the keys are locked.
- **Setting a missing voice up without asking.** A download the learner did not ask for.
- **Putting settings in the copy of the data.** The copy is for courses and progress and is
  restored whole, replacing everything; settings are small, and wanted on a computer that
  has its own courses.

## Consequences

- Another computer is set up as this one is with one file and one password.
- A key now exists outside secure storage, in a file, encrypted. Its safety is the
  password's. Eight characters is the least Adle takes; a guess costs a tenth of a second
  of work and 32 MB of memory each.
- A forgotten password loses the keys in that file and nothing else: the rest comes in, and
  the keys can be typed again.
- The format carries a version. A file from a later version is refused whole, with a
  sentence that says to update.
- Which providers have keys can be read in the file by anyone who has it.
