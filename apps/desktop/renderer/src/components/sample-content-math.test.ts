import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

import katex from 'katex';
import { describe, expect, it } from 'vitest';

import { splitMath } from './MathText';

/**
 * The lessons that ship with Adle are written by hand, and a mistyped formula would not fail
 * anywhere: the player shows text it cannot typeset exactly as written. So every formula in
 * the sample course is typeset here, with the options the player uses.
 */
const repoRoot = path.resolve(import.meta.dirname, '..', '..', '..', '..', '..');
const lessonsDir = path.join(repoRoot, 'services', 'core', 'adle_core', 'sample_course', 'lessons');
const lessonFiles = readdirSync(lessonsDir).filter((file) => file.endsWith('.json'));

interface Found {
  where: string;
  text: string;
}

/** Every string in a document, with the path that leads to it. */
function strings(value: unknown, where: string, found: Found[] = []): Found[] {
  if (typeof value === 'string') found.push({ where, text: value });
  else if (Array.isArray(value)) {
    value.forEach((item, index) => strings(item, `${where}[${index}]`, found));
  } else if (typeof value === 'object' && value !== null) {
    for (const [key, item] of Object.entries(value)) strings(item, `${where}.${key}`, found);
  }
  return found;
}

function typesets(tex: string): string | null {
  try {
    katex.renderToString(tex, {
      throwOnError: true,
      output: 'htmlAndMathml',
      strict: 'ignore',
      trust: false,
      maxExpand: 200,
    });
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
}

describe('the sample course', () => {
  it('has a lesson for each of its eight concepts', () => {
    expect(lessonFiles).toHaveLength(8);
  });

  it.each(lessonFiles)('%s: every formula typesets', (file) => {
    const document: unknown = JSON.parse(readFileSync(path.join(lessonsDir, file), 'utf8'));
    const problems: string[] = [];
    let formulas = 0;
    for (const { where, text } of strings(document, file)) {
      // Narration is read aloud: it is words, and never contains a formula.
      const spoken = /\.narration\[\d+\]\.text$/.test(where);
      if (spoken) {
        if (text.includes('$') || text.includes('\\'))
          problems.push(`${where}: notation in speech`);
        continue;
      }
      for (const part of splitMath(text)) {
        if (!part.math) {
          // A dollar sign left in the prose is a formula that was never closed.
          if (part.text.includes('$')) problems.push(`${where}: unclosed formula`);
          continue;
        }
        formulas += 1;
        const failure = typesets(part.text);
        if (failure) problems.push(`${where}: $${part.text}$ (${failure})`);
      }
    }
    expect(problems).toEqual([]);
    // A lesson about arithmetic with no formula at all would mean this test is not looking.
    expect(formulas).toBeGreaterThan(10);
  });
});
