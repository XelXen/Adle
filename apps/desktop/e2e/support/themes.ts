/**
 * Which themes an example of a set is run in.
 *
 * A theme changes a picture's colors and nothing a journey here looks at: where its words
 * lie, whether it finishes, what it says along the way. So each example runs once, the
 * two themes taking turns along the set, and both are still run in every set. Set
 * `ADLE_E2E_EVERY_THEME=1` to run every example in both, when a change is about the themes
 * themselves.
 */
export type Theme = 'light' | 'dark';

export function themesFor(index: number): readonly Theme[] {
  if (process.env.ADLE_E2E_EVERY_THEME === '1') return ['dark', 'light'];
  return [index % 2 === 0 ? 'dark' : 'light'];
}
