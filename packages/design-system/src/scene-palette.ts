/**
 * The colours generated Wanim scenes may use, per theme.
 *
 * Scenes are Python files and cannot read CSS variables, so this module is the
 * bridge: the player supplies `background`, and the scene-authoring skill and
 * the generation prompt list the foreground colours. `tokens.test.ts` asserts
 * that every value here still equals the token it mirrors.
 */

export interface ScenePalette {
  /** Stage backdrop. Supplied by the player; scenes must not set their own. */
  background: string;
  ink: string;
  muted: string;
  green: string;
  sun: string;
  coral: string;
  blue: string;
  violet: string;
}

/** Scene colour name -> design token it mirrors. */
export const SCENE_PALETTE_TOKENS: Record<keyof ScenePalette, string> = {
  background: '--ad-color-surface',
  ink: '--ad-color-ink',
  muted: '--ad-color-muted',
  // Scenes keep their green. It is the success green, not the brand's teal.
  green: '--ad-color-success',
  sun: '--ad-color-sun',
  coral: '--ad-color-coral',
  blue: '--ad-color-blue',
  violet: '--ad-color-violet',
};

export const SCENE_PALETTE: Record<'light' | 'dark', ScenePalette> = {
  light: {
    background: '#FFFFFF',
    ink: '#17251E',
    muted: '#5F6E65',
    green: '#269B62',
    sun: '#F2C14E',
    coral: '#EF806C',
    blue: '#5B8DE6',
    violet: '#9178D7',
  },
  dark: {
    background: '#18211C',
    ink: '#E7EFE9',
    muted: '#9DB0A5',
    green: '#3DBE7F',
    sun: '#E9BE5A',
    coral: '#F08F7D',
    blue: '#7BA4EE',
    violet: '#A694E3',
  },
};
