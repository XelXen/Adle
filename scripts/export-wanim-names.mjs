#!/usr/bin/env node
/**
 * Derive the name allowlist for generated scenes from the pinned Wanim build.
 *
 *   node scripts/export-wanim-names.mjs          # write the data file
 *   node scripts/export-wanim-names.mjs --check  # fail if it is out of date
 *
 * A scene may only reference names it defines itself, a small set of Python
 * builtins, and the manim API. This script produces that last list from what
 * the Wanim browser bundle actually exports, minus runtime plumbing that a
 * scene has no business calling (renderers, font and module loaders, embed
 * and file helpers, schedulers) and minus anything that loads external assets.
 *
 * Output: services/core/adle_core/generation/data/wanim_names.json
 * Re-run whenever `@wanimjs/wanim` is upgraded, then review the diff.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outputPath = path.join(
  repoRoot,
  'services',
  'core',
  'adle_core',
  'generation',
  'data',
  'wanim_names.json',
);

const wanimDir = path.dirname(require.resolve('@wanimjs/wanim/package.json'));
const { version } = JSON.parse(readFileSync(path.join(wanimDir, 'package.json'), 'utf8'));

/** Runtime plumbing and asset loaders: exported by the bundle, forbidden in scenes. */
const EXCLUDED_PATTERNS = [
  // Rendering, playback, and presentation machinery.
  /^(render|play|benchmark|run|construct)_/,
  /^(serialize|deserialize)_/,
  /(Renderer|Host|Presentation|Player|PlayerHandle|Formatter|Backend)$/,
  /^(create_canvas_backend|standard_backend|default_camera_class|apply_quality)$/,
  /scheduler|is_async_rendering/,
  // Module, font, and configuration loading.
  /^(configure|preload|register)_/,
  /^(submodule_status|load_module_into_namespace|get_module)$/,
  /^(config|config_file_paths|make_config_parser|tempconfig|ManimConfig|RendererType)$/,
  /scene_classes|scenes_to_render|scenes_from_module|parse_scene_choice|prompt_user/,
  // Files, paths, logging, and external tools.
  /file|path_from_defaults|_paths?$|logger|guarantee_existence|modify_atime|open_/,
  /^(add_extension_if_not_present|add_version_before_extension|add_import_statement)$/,
  /tex_compilation|template|typst|convert_to_svg|video_metadata|_format$/,
  // Embedding, sharing, hashing, and theme helpers meant for the host page.
  /embed|^parse_(mjson|theme|svg)|^svg_|hash|^crc32$|^capture$|^get_json$/,
  /presentation_(mode|theme)|prefers_dark|dark_from_hex|numpy_wasm/,
  // Anything that loads an image, a vector file, or sound.
  /Image|SVGMobject|VMobjectFromSVGPath|Sound/,
];

function exportedNames(bundlePath) {
  const source = readFileSync(bundlePath, 'utf8');
  const match = /export\{([^}]+)\}\s*;?\s*$/.exec(source);
  if (!match) throw new Error('Could not find the export list in the Wanim browser bundle.');
  return match[1].split(',').map((entry) => entry.split(' as ').pop().trim());
}

/** manim's Python API is snake_case, PascalCase, or CONSTANT_CASE; lowerCamelCase is TS internals. */
function isPythonStyle(name) {
  if (name.startsWith('_')) return false;
  return !/^[a-z]+[a-z0-9]*[A-Z]/.test(name);
}

const manim = exportedNames(path.join(wanimDir, 'browser', 'wanim.browser.js'))
  .filter(isPythonStyle)
  .filter((name) => !EXCLUDED_PATTERNS.some((pattern) => pattern.test(name)))
  .sort();

const publicNames = await import(
  /* The stdlib name tables Wanim rewrites `from math import *` etc. against. */
  new URL(`file://${path.join(wanimDir, 'dist', 'public_names.js').replace(/\\/g, '/')}`)
);

const data = {
  wanim_version: version,
  manim,
  math: [...publicNames.MATH_PUBLIC].sort(),
  random: [...publicNames.RANDOM_PUBLIC].sort(),
  itertools: [...publicNames.ITERTOOLS_PUBLIC].sort(),
};
const content = `${JSON.stringify(data, null, 1)}\n`;

if (process.argv.includes('--check')) {
  let current = '';
  try {
    current = readFileSync(outputPath, 'utf8').replace(/\r\n/g, '\n');
  } catch {
    current = '';
  }
  if (current !== content) {
    console.error('wanim_names.json is out of date. Run "node scripts/export-wanim-names.mjs".');
    process.exit(1);
  }
  console.log('wanim_names.json is up to date.');
} else {
  writeFileSync(outputPath, content);
  console.log(`Wrote ${manim.length} manim names for Wanim ${version}.`);
}
