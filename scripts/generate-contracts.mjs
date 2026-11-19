#!/usr/bin/env node
/**
 * Generate the shared API contract from the Python core.
 *
 *   node scripts/generate-contracts.mjs          # write generated files
 *   node scripts/generate-contracts.mjs --check  # fail if they are out of date
 *
 * Source of truth: the FastAPI application in services/core. This script asks
 * it for its OpenAPI document and derives:
 *
 *   packages/contracts/schemas/openapi.json        the raw contract
 *   packages/contracts/schemas/lesson-ir.schema.json  the Lesson IR as JSON Schema
 *   packages/contracts/src/generated/models.ts     TypeScript types for every schema
 *   packages/contracts/src/generated/operations.ts the operation table used as the
 *                                                  renderer's allowlist, plus typed
 *                                                  parameters and results
 *
 * Never edit the generated files by hand.
 */
import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { compile } from 'json-schema-to-typescript';
import prettier from 'prettier';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const contractsDir = path.join(repoRoot, 'packages', 'contracts');
const checkOnly = process.argv.includes('--check');

const BANNER =
  '// GENERATED FILE — do not edit.\n' +
  '// Source: services/core (FastAPI). Regenerate with `npm run contracts`.\n\n';

function exportContracts() {
  const result = spawnSync(
    'uv',
    ['run', '--project', 'services/core', 'python', '-m', 'adle_core.tools.export_contracts'],
    { cwd: repoRoot, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, shell: false },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`Contract export failed (exit ${result.status}):\n${result.stderr}`);
  }
  return JSON.parse(result.stdout);
}

const REF_PREFIX = '#/components/schemas/';

/** Recursively rewrite component refs and drop per-property titles (they add noise aliases). */
function normaliseSchema(schema, isDefinitionRoot) {
  if (Array.isArray(schema)) return schema.map((item) => normaliseSchema(item, false));
  if (typeof schema !== 'object' || schema === null) return schema;
  const output = {};
  for (const [key, value] of Object.entries(schema)) {
    if (key === 'title' && !isDefinitionRoot) continue;
    if (key === '$ref' && typeof value === 'string' && value.startsWith(REF_PREFIX)) {
      output.$ref = `#/$defs/${value.slice(REF_PREFIX.length)}`;
      continue;
    }
    if (key === 'properties' || key === '$defs') {
      output[key] = Object.fromEntries(
        Object.entries(value).map(([name, child]) => [name, normaliseSchema(child, false)]),
      );
      continue;
    }
    output[key] = normaliseSchema(value, false);
  }
  return output;
}

async function generateModels(openapi) {
  const schemas = openapi.components?.schemas ?? {};
  const $defs = Object.fromEntries(
    Object.entries(schemas).map(([name, schema]) => [name, normaliseSchema(schema, true)]),
  );
  const root = { title: 'AdleContractRoot', type: 'object', additionalProperties: false, $defs };
  const source = await compile(root, 'AdleContractRoot', {
    bannerComment: '',
    additionalProperties: false,
    unreachableDefinitions: true,
    format: false,
    strictIndexSignatures: true,
    // Bounds on list length are enforced by the core. As types they would become
    // unions of fixed-length tuples, which no caller can build from an ordinary array.
    ignoreMinAndMaxItems: true,
  });
  return (
    source
      // The synthetic root only exists to carry $defs.
      .replace(/export interface AdleContractRoot \{\s*\}\n?/, '')
      // Drop the generator's "referenced by ... via the definition" boilerplate,
      // keeping any real description from the Python docstring.
      .replace(
        /^ \* This (?:interface|type) was referenced by .*\n \* via the `definition` .*\n/gm,
        '',
      )
      .replace(/^ \*\n(?= \*\/)/gm, '')
      .replace(/\/\*\*\n \*\/\n/g, '')
  );
}

function refName(ref) {
  return ref.startsWith(REF_PREFIX) ? ref.slice(REF_PREFIX.length) : 'unknown';
}

/** Convert a (small) parameter/response schema to a TypeScript type expression. */
function tsType(schema, usedModels) {
  if (!schema || typeof schema !== 'object') return 'unknown';
  if (schema.$ref) {
    const name = refName(schema.$ref);
    usedModels.add(name);
    return name;
  }
  if (schema.const !== undefined) return JSON.stringify(schema.const);
  if (Array.isArray(schema.enum)) return schema.enum.map((v) => JSON.stringify(v)).join(' | ');
  const union = schema.anyOf ?? schema.oneOf;
  if (Array.isArray(union)) {
    return [...new Set(union.map((member) => tsType(member, usedModels)))].join(' | ');
  }
  switch (schema.type) {
    case 'string':
      return 'string';
    case 'integer':
    case 'number':
      return 'number';
    case 'boolean':
      return 'boolean';
    case 'null':
      return 'null';
    case 'array': {
      const item = tsType(schema.items, usedModels);
      return /[ |]/.test(item) ? `Array<${item}>` : `${item}[]`;
    }
    default:
      return 'unknown';
  }
}

function paramsType(parameters, location, usedModels) {
  const selected = (parameters ?? []).filter((parameter) => parameter.in === location);
  if (selected.length === 0) return 'undefined';
  const allOptional = selected.every((parameter) => !parameter.required);
  const fields = selected
    .map(
      (parameter) =>
        `${JSON.stringify(parameter.name)}${parameter.required ? '' : '?'}: ` +
        tsType(parameter.schema, usedModels),
    )
    .join('; ');
  return `{ ${fields} }${allOptional ? ' | undefined' : ''}`;
}

function resultType(operation, usedModels) {
  for (const status of ['200', '201', '202']) {
    const schema = operation.responses?.[status]?.content?.['application/json']?.schema;
    if (schema) return tsType(schema, usedModels);
  }
  return 'null';
}

function collectOperations(openapi) {
  const operations = [];
  for (const [routePath, methods] of Object.entries(openapi.paths ?? {})) {
    for (const [method, operation] of Object.entries(methods)) {
      if (!['get', 'post', 'put', 'patch', 'delete'].includes(method)) continue;
      if (!operation.operationId) {
        throw new Error(`Route ${method.toUpperCase()} ${routePath} has no operation_id.`);
      }
      operations.push({
        id: operation.operationId,
        method: method.toUpperCase(),
        routePath,
        operation,
      });
    }
  }
  operations.sort((a, b) => a.id.localeCompare(b.id));
  const seen = new Set();
  for (const { id } of operations) {
    if (seen.has(id)) throw new Error(`Duplicate operation_id "${id}".`);
    seen.add(id);
  }
  return operations;
}

function generateOperations(openapi) {
  const operations = collectOperations(openapi);
  const usedModels = new Set();

  const tableEntries = operations.map(
    ({ id, method, routePath, operation }) =>
      `  ${JSON.stringify(id)}: { method: ${JSON.stringify(method)}, path: ${JSON.stringify(routePath)}, ` +
      `internal: ${operation['x-adle-internal'] === true} },`,
  );

  const typeEntries = operations.map(({ id, operation }) => {
    const bodySchema = operation.requestBody?.content?.['application/json']?.schema;
    const body = bodySchema ? tsType(bodySchema, usedModels) : 'undefined';
    return (
      `  ${JSON.stringify(id)}: {\n` +
      `    path: ${paramsType(operation.parameters, 'path', usedModels)};\n` +
      `    query: ${paramsType(operation.parameters, 'query', usedModels)};\n` +
      `    body: ${body};\n` +
      `    result: ${resultType(operation, usedModels)};\n` +
      `  };`
    );
  });

  const imports = [...usedModels].filter((name) => name !== 'unknown').sort();
  const importLine = imports.length
    ? `import type { ${imports.join(', ')} } from './models';\n\n`
    : '';

  return (
    importLine +
    '/**\n' +
    ' * Every operation the core exposes. `internal` operations may only be called by the\n' +
    ' * Electron main process; the renderer bridge refuses them.\n' +
    ' */\n' +
    `export const OPERATIONS = {\n${tableEntries.join('\n')}\n} as const;\n\n` +
    'export type OperationId = keyof typeof OPERATIONS;\n\n' +
    '/** Parameter and result types for each operation. */\n' +
    `export interface OperationTypes {\n${typeEntries.join('\n')}\n}\n`
  );
}

async function format(source, filePath) {
  const config = (await prettier.resolveConfig(filePath)) ?? {};
  return prettier.format(source, { ...config, filepath: filePath });
}

async function main() {
  const { openapi, lesson_ir: lessonIr } = exportContracts();
  const files = new Map();

  const lessonIrPath = path.join(contractsDir, 'schemas', 'lesson-ir.schema.json');
  files.set(lessonIrPath, await format(JSON.stringify(lessonIr), lessonIrPath));

  const openapiPath = path.join(contractsDir, 'schemas', 'openapi.json');
  files.set(openapiPath, await format(JSON.stringify(openapi), openapiPath));

  const modelsPath = path.join(contractsDir, 'src', 'generated', 'models.ts');
  files.set(modelsPath, await format(BANNER + (await generateModels(openapi)), modelsPath));

  const operationsPath = path.join(contractsDir, 'src', 'generated', 'operations.ts');
  files.set(operationsPath, await format(BANNER + generateOperations(openapi), operationsPath));

  const stale = [];
  for (const [filePath, content] of files) {
    let current = null;
    try {
      current = readFileSync(filePath, 'utf8').replace(/\r\n/g, '\n');
    } catch {
      current = null;
    }
    if (current === content) continue;
    stale.push(path.relative(repoRoot, filePath));
    if (!checkOnly) {
      mkdirSync(path.dirname(filePath), { recursive: true });
      writeFileSync(filePath, content);
    }
  }

  if (checkOnly && stale.length > 0) {
    console.error(`Contracts are out of date. Run "npm run contracts".\n  ${stale.join('\n  ')}`);
    process.exit(1);
  }
  console.log(
    checkOnly
      ? 'Contracts are up to date.'
      : stale.length > 0
        ? `Updated ${stale.length} contract file(s):\n  ${stale.join('\n  ')}`
        : 'Contracts already up to date.',
  );
}

await main();
