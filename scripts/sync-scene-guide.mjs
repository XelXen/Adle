#!/usr/bin/env node
/**
 * Package the scene-authoring skill for the model that writes scenes.
 *
 *   node scripts/sync-scene-guide.mjs          # write the packaged guide
 *   node scripts/sync-scene-guide.mjs --check  # fail if it is out of date
 *
 * Source of truth: skills/wanim-scene-authoring (SKILL.md and its examples),
 * which is written for people and coding agents and is proven by the E2E
 * suite. The core cannot read that folder in a packaged build, so the parts a
 * scene writer needs are copied into one file that ships inside the package:
 *
 *   services/core/adle_core/generation/data/scene_guide.md
 *
 * Never edit the packaged file by hand. Change the skill, then run this.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const skillDir = path.join(repoRoot, 'skills', 'wanim-scene-authoring');
const target = path.join(
  repoRoot,
  'services',
  'core',
  'adle_core',
  'generation',
  'data',
  'scene_guide.md',
);
const checkOnly = process.argv.includes('--check');

/** The part of the skill that says how to write a scene (not how to test or upgrade one). */
const FIRST_HEADING = '## The one-file rule';
const HEADING_AFTER = '## Before a scene ships';

/** Examples given to the model, with what each one demonstrates. */
const EXAMPLES = [
  ['weighted_sum.py', 'An animation-only scene: shapes, text, a formula, simple animations.'],
  [
    'neuron_weight.py',
    'An interactive scene: a slider and a switch, reactions, events, named controls.',
  ],
  ['activation_curve.py', 'Axes with a plotted curve and a point that moves along it.'],
];

const read = (file) => readFileSync(path.join(skillDir, file), 'utf8').replace(/\r\n/g, '\n');

function build() {
  const skill = read('SKILL.md');
  const start = skill.indexOf(FIRST_HEADING);
  const end = skill.indexOf(HEADING_AFTER);
  if (start < 0 || end < 0 || end <= start) {
    throw new Error(
      `SKILL.md no longer has "${FIRST_HEADING}" followed by "${HEADING_AFTER}". ` +
        'Update scripts/sync-scene-guide.mjs to match its structure.',
    );
  }
  const rules = skill.slice(start, end).trimEnd();
  const examples = EXAMPLES.map(
    ([file, shows]) =>
      `### ${file}\n\n${shows}\n\n\`\`\`python\n${read(`examples/${file}`).trimEnd()}\n\`\`\``,
  ).join('\n\n');
  return (
    '<!-- GENERATED FILE: do not edit. Source: skills/wanim-scene-authoring. ' +
    'Regenerate with `npm run scene-guide`. -->\n\n' +
    '# Writing a Wanim scene for Adle\n\n' +
    `${rules}\n\n## Complete examples\n\n` +
    'Each of these files runs in Adle exactly as shown.\n\n' +
    `${examples}\n`
  );
}

const expected = build();
let current = null;
try {
  current = readFileSync(target, 'utf8').replace(/\r\n/g, '\n');
} catch {
  current = null;
}

if (current === expected) {
  console.log('Scene guide is up to date.');
} else if (checkOnly) {
  console.error('The packaged scene guide is out of date. Run "npm run scene-guide".');
  process.exit(1);
} else {
  writeFileSync(target, expected);
  console.log(`Updated ${path.relative(repoRoot, target)}`);
}
