import type { TeacherCharacter } from '@adle/contracts';

/** What a teacher is made of: a choice for each part chosen (ADR-071). */
export type TeacherParts = Readonly<Record<string, string | undefined>>;

/** The teacher to start from that has no parts at all: the core's first. */
export const ADLE_OWN = 'Adle’s own';

export function sameParts(a: TeacherParts, b: TeacherParts): boolean {
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every((key) => a[key] === b[key]);
}

/** These parts with one changed; an empty choice leaves the part to Adle's teacher. */
export function withPart(parts: TeacherParts, key: string, choice: string): TeacherParts {
  const next: Record<string, string | undefined> = { ...parts };
  if (choice) next[key] = choice;
  else delete next[key];
  return next;
}

/** The parts as the core takes them: each a choice, none left empty. */
export function chosenParts(parts: TeacherParts): Record<string, string> {
  const chosen: Record<string, string> = {};
  for (const [key, choice] of Object.entries(parts)) if (choice) chosen[key] = choice;
  return chosen;
}

/**
 * The teacher to start from that these parts are, or '' for the learner's own. With no
 * parts and no words of their own, it is Adle's own.
 */
export function presetOf(
  presets: TeacherCharacter['presets'],
  parts: TeacherParts,
  ownWords: boolean,
): string {
  if (ownWords) return '';
  const found = presets.find((preset) => sameParts(preset.parts, parts));
  return found ? found.name : '';
}

/**
 * What to save: the parts, while the words are the sentence the core made of them; else the
 * learner's own words. No parts and no words is Adle's own teacher.
 */
export function teacherRequest(
  parts: TeacherParts,
  words: string,
  composed: string,
): { character_parts: Record<string, string> } | { character: string } {
  const said = words.trim();
  if (said === '' || said === composed) return { character_parts: chosenParts(parts) };
  return { character: said };
}
