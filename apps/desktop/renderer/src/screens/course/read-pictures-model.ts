import type { ProviderChoice } from '@adle/contracts';

/**
 * Why there is nothing to press: who could read pictures, and what the learner can do
 * about it in Settings, in the names the core gives.
 */
export function noReader(
  providers: Pick<ProviderChoice, 'display_name' | 'reads_pictures' | 'key_configured'>[],
  count: number,
): string {
  const readers = providers.filter((each) => each.reads_pictures);
  if (readers.length === 0) return 'None of your AI providers can read pictures.';
  const names = readers.map((each) => each.display_name).join(' or ');
  const them = count === 1 ? 'it' : 'them';
  return readers.some((each) => each.key_configured)
    ? `To read ${them}, choose ${names} or Automatic in Settings.`
    : `To read ${them}, add a key for ${names} in Settings.`;
}
