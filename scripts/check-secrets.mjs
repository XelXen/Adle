#!/usr/bin/env node
/**
 * Fail if anything that looks like a real credential, or a file that should never be in
 * the repository, is about to be committed.
 *
 *   node scripts/check-secrets.mjs
 *
 * It looks at every file git knows about or would add (tracked, and untracked but not
 * ignored), so it catches a key pasted into a test, a fixture, or a note before the commit
 * and not after. It is a net, not a proof: a key in a form nobody thought of gets through,
 * and the rule stays "a provider key is never written into the repository".
 *
 * What it reports is where, and what kind. Never the value: a tool that prints the secret
 * it found has just written it into a log.
 *
 * The stand-in keys the tests use are words with hyphens between them
 * ("sk-test-...", "nvapi-e2e-not-a-real-key-..."). A real key is one long run of letters
 * and digits, and that difference is what the patterns go by.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** What a credential looks like, and what to call it. */
const PATTERNS = [
  // AIHubMix and other OpenAI-style keys: "sk-" and then one unbroken run.
  { kind: 'an API key ("sk-" and a long unbroken run)', pattern: /\bsk-[A-Za-z0-9]{32,}/ },
  // The same family with a word in front of the run, where the run itself may hold hyphens.
  {
    kind: 'an API key ("sk-", a known prefix, and a long run)',
    pattern: /\bsk-(?:proj|svcacct|admin|or-v1|ant-[a-z0-9]+)-[A-Za-z0-9_-]{32,}/,
  },
  // NVIDIA: "nvapi-" and then some sixty characters.
  { kind: 'an NVIDIA API key', pattern: /\bnvapi-[A-Za-z0-9_-]{40,}/ },
  { kind: 'a Google API key', pattern: /\bAIza[0-9A-Za-z_-]{35}\b/ },
  {
    kind: 'a GitHub token',
    pattern: /\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})/,
  },
  {
    kind: 'a signed web token',
    pattern: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/,
  },
  { kind: 'a private key', pattern: /-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----/ },
  // A token typed into a header in a sample request, however "bearer" is capitalised.
  { kind: 'a bearer token', pattern: /\bBearer\s+[A-Za-z0-9._~+/-]{40,}={0,2}/i },
];

/** Files that hold a learner's data or secrets when the app runs. None belongs in git. */
const FORBIDDEN_FILES = [
  { kind: 'an environment file', pattern: /(^|\/)\.env(\.(?!example$)[^/]*)?$/ },
  { kind: 'an environment file', pattern: /(^|\/)\.envrc$/ },
  { kind: 'a database', pattern: /\.(db|sqlite|sqlite3)(-wal|-shm|-journal|\.restoring)?$/ },
  { kind: "a saved copy of a learner's data", pattern: /\.adle(\.part)?$/ },
  { kind: 'a credential store', pattern: /(^|\/)credentials\.bin$/ },
  { kind: 'a secret of one installation', pattern: /(^|\/)items\.key$/ },
  { kind: 'a log of the running app', pattern: /(^|\/)(core|app)\.log$/ },
];

const MAX_BYTES = 2 * 1024 * 1024;

function candidateFiles() {
  const listed = spawnSync('git', ['ls-files', '-co', '--exclude-standard', '-z'], {
    cwd: repoRoot,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
  if (listed.status !== 0) throw new Error(`git ls-files failed: ${listed.stderr}`);
  return listed.stdout.split('\0').filter(Boolean);
}

/** Text files only: a font or a picture is not where a key gets pasted. */
function readText(file) {
  let size;
  try {
    size = statSync(file).size;
  } catch {
    return null; // listed by git, deleted in the working tree
  }
  if (size > MAX_BYTES) return null;
  const bytes = readFileSync(file);
  // Text saved by some Windows tools is two bytes to a character, and would otherwise be
  // taken for a binary file and passed over: read it as what it is.
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return bytes.subarray(2).toString('utf16le');
  if (bytes[0] === 0xfe && bytes[1] === 0xff) {
    return Buffer.from(bytes.subarray(2)).swap16().toString('utf16le');
  }
  if (bytes.includes(0)) return null;
  return bytes.toString('utf8');
}

/**
 * Before looking at any file, check that the patterns still tell a real key from a
 * stand-in. The samples are put together here so that no line of this file is itself
 * something the scan would report.
 */
function checkThePatterns() {
  const kinds = (line) => PATTERNS.filter(({ pattern }) => pattern.test(line)).length;
  const run = (piece, times) => piece.repeat(times);
  const mustBeFound = [
    `api_key = "${'sk'}-${run('A1b2', 12)}"`,
    `Authorization: ${'Bearer'} ${'nvapi'}-${run('x9', 32)}`,
    `-----BEGIN ${'OPENSSH'} PRIVATE KEY-----`,
    `OPENAI_KEY=${'sk'}-${'proj'}-${run('aB3-', 12)}`,
    `key: ${'sk'}-${'or'}-v1-${run('0f', 32)}`,
    `authorization: ${'bearer'} ${run('Zx9k', 12)}`,
    `google = "${'AI'}${'za'}${run('Sy1_', 8)}abc"`,
    `token = ${'gh'}${'p'}_${run('a1B2', 9)}`,
    `${'ey'}${'J'}${run('hbGc', 4)}.${'ey'}${'J'}${run('zdWI', 4)}.${run('s1Gn', 4)}`,
  ];
  const mustBeLeft = [
    'const KEY = "sk-e2e-not-a-real-key-7Hq2mZx94Wd1";',
    'AIHUBMIX_KEY = "sk-test-aihubmix-0123456789abcdef"',
    'NVIDIA_KEY = "nvapi-test-0123456789abcdefghijkl"',
    'headers={"Authorization": f"Bearer {api_key}"}',
    'ask-about-a-question.png risk-free task-list',
  ];
  const wrong = [
    ...mustBeFound.filter((line) => kinds(line) === 0).map(() => 'a real key would get through'),
    ...mustBeLeft
      .filter((line) => kinds(line) > 0)
      .map((line) => `a stand-in is reported: ${line}`),
  ];
  if (wrong.length > 0) {
    console.error('The secret scan can no longer be trusted:');
    for (const problem of wrong) console.error(`  - ${problem}`);
    process.exit(2);
  }
}

checkThePatterns();

const findings = [];
for (const relative of candidateFiles()) {
  for (const { kind, pattern } of FORBIDDEN_FILES) {
    if (pattern.test(relative)) findings.push(`${relative}: ${kind} must not be in the repository`);
  }
  const text = readText(path.join(repoRoot, relative));
  if (text === null) continue;
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    for (const { kind, pattern } of PATTERNS) {
      if (pattern.test(line)) findings.push(`${relative}:${index + 1}: looks like ${kind}`);
    }
  });
}

if (findings.length > 0) {
  console.error('Something that looks like a secret, or must not be committed:');
  for (const finding of findings) console.error(`  - ${finding}`);
  console.error(
    '\nRemove it (and if it was a real key, replace the key: it has been on disk in the clear).',
  );
  process.exit(1);
}
console.log('No credential or learner data found in what would be committed.');
