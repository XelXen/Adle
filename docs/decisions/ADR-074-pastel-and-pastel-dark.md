# ADR-074: Pastel and Pastel dark

- **Status:** Accepted
- **Date:** 2026-11-25
- **Changes:** the themes (System, Light, Dark) gain two, Pastel and Pastel dark, in a color
  the learner picks.
- **Keeps:** one way the light or dark scheme is set (`nativeTheme.themeSource`, which
  Chromium gives the page and every player frame as `prefers-color-scheme`), the scene
  palette and the lesson's dark screen in every theme (ADR-035), the colors that mean
  something (success, danger, the accents, the focus ring).

## Context

The owner, on 2026-11-25: "also 2 more themes: pastel (user can pick the color), and
pastel dark".

## Decisions

1. **Pastel is the light theme in a color, and Pastel dark the dark one.** The main process
   sets the scheme for them as for Light and Dark (`colorSchemeOf`), so the page, the
   players and the window follow it the one way they always have.
2. **The color is a hue**, a whole number of degrees round the OKLCH circle, kept with the
   theme (`UiState.pastelHue`, checked in the main process like every other field) and in
   a settings file with it. It stays while another theme is chosen, so Pastel comes back
   in it. Pastel starts in lavender.
3. **The page is marked `data-ad-palette="pastel"` and told the hue in `--ad-pastel-hue`**,
   through the CSSOM, before its first paint and whenever either changes. The tokens do the
   rest: a block at the end of `tokens.css` gives the grounds, the text, the borders and
   the one color (the filled action, its soft ground, its text) that hue, in OKLCH, at a
   lightness and chroma that sRGB can show in every hue. In Pastel the action is a deep
   shade of the color with a white label; in Pastel dark it is the color itself, light,
   with a dark label of its own hue.
4. **Every hue keeps every contrast.** `tokens.test.ts` works each token out as a screen
   shows it in all 360 hues, checks it is inside sRGB, and checks every pair the light
   and dark themes are held to. The end-to-end suite runs axe over the primary screens in
   both, each in a color of its own.
5. **The window follows the color** (`electron/main/pastel.ts`): its ground before the page
   paints and the strip its buttons sit on take the canvas and the ink, worked out from
   the same numbers, which a unit test reads from the tokens.
6. **The color is picked** in Settings → Appearance, shown only in the two Pastel themes:
   ten named swatches (Pink, Peach, Butter, Sage, Mint, Aqua, Sky, Periwinkle, Lavender,
   Lilac; `ColorSwatches`, a radio group) and a slider along every hue for any color
   between them (`Slider track="spectrum"`), said as the swatch it is nearest.

## Consequences

- The mark of the app takes the color too, being drawn in the one color.
- A green chosen for Pastel makes the action green, like success; success keeps its icon
  and its words.
- What a picture is drawn on and with does not change: a lesson looks the same in every
  theme.
