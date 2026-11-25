# ADR-069: A word over something is given a shadow

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** ADR-055 and ADR-056 in what happens when a picture's words still lie over
  other words or under a line once its labels have been moved: they were counted, and
  nothing more; now each such word is given a shadow. The scene policy's bound on a
  scene's size, from 6,000 nodes to 8,000.
- **Keeps:** ADR-049 (a slide is no request: nothing is sent back to be drawn again),
  ADR-055 (labels are moved apart before anything is shown, and the end-to-end suite still
  allows no such word in any example), ADR-035 (the stage's color is the player's).

## Context

The owner, on 2026-11-25, of overlapping words on a slide: not to send the slide back to be
drawn again ("lets not even do that"), but "if text overlaps anything — the opacity of the
thing that came first reduces down"; then "in fact not even opacity, use a shadow
underneath the top (latest) element so the thing doesn't completely get low opacity"; and,
as it was being drawn: "not opaque static shadow, i meant a gradual fade shadow and that too
translucent", "the type like under mouse pointers in windows", "the shadow color depends on
the mode, if background is light then shadow should be light too so to hide the stuff
behind", and "increase the shadow opacity — still not full but more".

A slide is drawn by Adle from a model's script. Its labels are moved where they lie over
nothing (ADR-055), but a model can still write what cannot be laid out clear: an arrow from
one side of the stage to the other through the word between, more labels on one point than
there is room for round it. The audit counted those words; nothing in the app acted on it,
and the learner saw words printed over each other.

## Decisions

1. **As each step ends, the later of two words that lie over each other, and a word a line
   runs through, is given a shadow** (`layout.shade`, called by `audit`): like a mouse
   pointer's, soft and fading out, a little below and to the right of the word (an eighth
   of its height down, three quarters of that across), in the stage's own color, dark on
   the dark screen and light on the light one, so that it hides what lies behind the word.
   It is about three quarters opaque under the letters and fades to nothing over about
   twice a letter's stroke: what lies behind still shows through a little, and keeps its
   color everywhere else. A word with a line through it is drawn above the line. A label
   that follows something moving is given one while it finds no clear place.
2. **"Later" is the order things are drawn**: of two words on the stage together, the one
   that came on it after the other. Only what is on the stage together is looked at, so a
   word is never shaded for one it never meets.
3. **It is drawn as copies of the word, the first of its parts**, moved so, each only a rim
   round every letter (Wanim's background stroke), each wider and fainter than the one
   before, with round corners. Every rim is drawn before any letter, so no rim eats into
   the next letter, as one rim a letter did when tried in tight serif text; a color given
   to the word later never reaches them; they move and fade with the word. The color is
   read from the player's camera (`self.camera.background_color`): a scene still never
   chooses its own backdrop.
4. **What is counted is unchanged**: the slide still says, as each step ends, how many
   words lie over others or under a line, now with how many of them have no shadow that
   can be seen. The examples still allow none. Two slides that cannot be laid out clear
   (`fixtures/slides/crowded/`) are stepped through in both themes, each such word with
   its shadow.
5. **The scene policy's bound is 8,000 nodes**, from 6,000: every slide and figure carries
   Adle's layout methods, about 2,200 nodes of its own, and the busiest example came to
   6,187 with the shadow.

## Consequences

- A slide a model scripted badly can still be read where its words meet.
- The shadow appears as the step that brought the words together ends, not before: a
  picture's sizes are known only in the player, and only then is it known what is on the
  stage together.
- A round corner set on a shadow's rims can carry over to a stroke drawn after it in the
  same frame (Wanim sets a canvas's join only when a stroke asks for one): a corner a
  little rounder, on a slide that has a shadow at all.
- A figure (ADR-045) has its words shaded the same way as each of its pages ends.
- A model's scene may now be up to 8,000 nodes as well; the names and calls it may use are
  unchanged.
