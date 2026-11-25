import type { SettingsFileParts, SettingsVoicePlan } from './bridge';

/**
 * Settings saved as a file, and brought in from one (ADR-064): the parts a file can hold,
 * and the words for them. The file is made and read by the main process and the core; the
 * page says which parts, and types the password that locks the keys.
 */

export type SettingsPart = keyof SettingsFileParts;

export interface PartChoice {
  key: SettingsPart;
  label: string;
  description: string;
}

/** The parts of a settings file, in the order they are shown. */
export const PARTS: readonly PartChoice[] = [
  {
    key: 'appearance',
    label: 'Appearance',
    description: 'The theme, and whether your computer says when something is ready.',
  },
  {
    key: 'learning',
    label: 'Learning',
    description: 'Pace, how much is explained, reading aloud, and your goal.',
  },
  {
    key: 'voice',
    label: 'Voice',
    description: 'Which voice reads your lessons, and who speaks in it.',
  },
  {
    key: 'provider',
    label: 'AI provider',
    description: 'Which provider is used, or that Adle chooses.',
  },
  { key: 'keys', label: 'API keys', description: 'Locked with a password you choose.' },
];

export const EVERY_PART: SettingsFileParts = {
  appearance: true,
  learning: true,
  voice: true,
  provider: true,
  keys: true,
};

/** The shortest password the keys can be locked with. The main process checks it too. */
export const MIN_PASSWORD_LENGTH = 8;

function listed(items: string[]): string {
  if (items.length <= 1) return items.join('');
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

/** "appearance, learning, voice, AI provider and API keys" */
export function partsListed(parts: SettingsFileParts): string {
  const names = PARTS.filter((part) => parts[part.key]).map((part) =>
    part.key === 'provider' || part.key === 'keys' ? part.label : part.label.toLowerCase(),
  );
  return listed(names);
}

/** Whether nothing at all is chosen: there is then nothing to save or to bring in. */
export function nothingChosen(parts: SettingsFileParts): boolean {
  return !PARTS.some((part) => parts[part.key]);
}

/** The parts chosen of the parts there are: a part a file does not have is never asked for. */
export function chosenOf(wanted: SettingsFileParts, has: SettingsFileParts): SettingsFileParts {
  return {
    appearance: wanted.appearance && has.appearance,
    learning: wanted.learning && has.learning,
    voice: wanted.voice && has.voice,
    provider: wanted.provider && has.provider,
    keys: wanted.keys && has.keys,
  };
}

/** Why a password for a new file cannot be used yet, or nothing. */
export function passwordProblem(password: string, again: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Use ${MIN_PASSWORD_LENGTH} characters or more.`;
  }
  if (password !== again) return 'The two passwords are different.';
  return null;
}

function aboutSize(bytes: number): string {
  const gigabytes = bytes / 1e9;
  if (gigabytes < 0.1) return `about ${Math.max(1, Math.round(bytes / 1e6))} MB`;
  const shown = gigabytes < 10 ? Math.round(gigabytes * 10) / 10 : Math.round(gigabytes);
  return `about ${shown} GB`;
}

/** What setting a voice up downloads, and from where: said before the learner agrees. */
export function setUpNote(plan: SettingsVoicePlan): string {
  const from = plan.sources.length > 0 ? ` from ${listed(plan.sources)}` : '';
  return `Downloads ${aboutSize(plan.downloadBytes)}${from}.`;
}
