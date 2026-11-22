import ts from 'typescript';
import { describe, expect, it } from 'vitest';

/**
 * What a learner reads is in American English (ADR-044): every string and every piece of
 * text in the interface, the main process's dialogs and notifications, and the design
 * system's components. Comments are not read. The API's own names are identifiers, not words
 * a learner reads, and keep the spelling they have.
 */
const SOURCES = import.meta.glob<string>(
  [
    './**/*.{ts,tsx}',
    '../../electron/main/**/*.ts',
    '../../../../packages/design-system/src/**/*.{ts,tsx}',
    '!./**/*.test.{ts,tsx}',
    '!../../electron/main/**/*.test.ts',
    '!../../../../packages/design-system/src/**/*.test.{ts,tsx}',
  ],
  { query: '?raw', import: 'default', eager: true },
);

/** British spellings, at the start of a word, and what follows them. */
const BRITISH =
  /\b(?:colour|behaviour|organis|recognis|favourit|centre|learnt|analys(?:e|ed|ing)\b|summaris|realis|maths\b|cancell|labell|modell|grey|programme|judgement|licence|practis|towards|whilst|amongst|catalogue|neighbour|honour|favour|minimis|maximis|normalis|visualis|optimis|initialis)\w*/i;

/** Names the core and the main process give things, which a learner never reads. */
const IDENTIFIERS = new Set(['cancelled', 'practise', 'licence']);

/** Every string and every piece of JSX text in a file, with the line it is on. */
function textsOf(file: string, code: string): { where: string; text: string }[] {
  const source = ts.createSourceFile(
    file,
    code,
    ts.ScriptTarget.Latest,
    true,
    file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const found: { where: string; text: string }[] = [];
  const visit = (node: ts.Node): void => {
    if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node) ||
      ts.isJsxText(node)
    ) {
      const line = source.getLineAndCharacterOfPosition(node.getStart()).line + 1;
      found.push({ where: `${file}:${line}`, text: node.text });
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return found;
}

describe('what a learner reads', () => {
  it('is found in every part of the interface', () => {
    const files = Object.keys(SOURCES);
    expect(files.some((file) => file.endsWith('screens/course/LearnPanel.tsx'))).toBe(true);
    expect(files.some((file) => file.includes('electron/main/'))).toBe(true);
    expect(files.some((file) => file.includes('design-system/src/components/'))).toBe(true);
    expect(files.some((file) => file.endsWith('.test.ts'))).toBe(false);
  });

  it('is in American English', () => {
    const british = Object.entries(SOURCES)
      .flatMap(([file, code]) => textsOf(file, code))
      .filter(({ text }) => !IDENTIFIERS.has(text.trim()) && BRITISH.test(text))
      .map(({ where, text }) => `${where}: ${text.trim().slice(0, 80)}`);
    expect(british).toEqual([]);
  });

  it('is read the way it is shown', () => {
    // The check itself: a British word in a string or in JSX text is caught; a comment, or
    // a name in code, is not.
    const sample = [
      "const label = 'Practise';",
      'const shown = <p>Its colour is grey.</p>;',
      '// the licence, in a comment',
      'const neighbour = 1;',
      "const status = 'cancelled';",
    ].join('\n');
    const caught = textsOf('sample.tsx', sample)
      .filter(({ text }) => !IDENTIFIERS.has(text.trim()) && BRITISH.test(text))
      .map(({ text }) => text.trim());
    expect(caught).toEqual(['Practise', 'Its colour is grey.']);
  });
});
