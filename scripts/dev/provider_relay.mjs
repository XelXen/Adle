#!/usr/bin/env node
/**
 * A relay on this computer to NVIDIA's real endpoint, for trying the whole app with a real
 * model by hand (ADR-075): its pictures tried in the hidden frame, a crowded slide drawn
 * again, a lesson heard in its teacher's voice. Never part of a test run: no test may call
 * a real provider (AGENTS.md), and this spends real allowance.
 *
 *   node scripts/dev/provider_relay.mjs <file holding the NVIDIA key> <folder outside the
 *     repository> [port, 9100]
 *
 * Then start the app with NVIDIA moved here, and give it a stand-in key in Settings (any
 * `nvapi-…` of the right length): the app never holds the real one.
 *
 *   ADLE_PROVIDER_ENDPOINTS='{"nvidia":"http://127.0.0.1:9100/v1"}'
 *
 * The key is read from its file, kept in memory and put on each request; it is never
 * printed or written. Every request body and every answer is kept in the folder, with
 * `relay.jsonl` saying which model each went to, how many were in flight, and how long
 * each took. A model's answers are the learner's to read, not the repository's.
 */
import { appendFileSync, createWriteStream, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const UPSTREAM = 'https://integrate.api.nvidia.com/v1';
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

const [keyFile, outDir, portText] = process.argv.slice(2);
if (!keyFile || !outDir) {
  console.error('Usage: node scripts/dev/provider_relay.mjs <key file> <folder> [port]');
  process.exit(2);
}
const folder = path.resolve(outDir);
if (!path.relative(repoRoot, folder).startsWith('..')) {
  console.error('Keep what a model wrote outside the repository: choose another folder.');
  process.exit(2);
}
const key = readFileSync(keyFile, 'utf8').trim();
if (!/^nvapi-[\w-]{20,}$/.test(key)) {
  console.error('That file does not hold an NVIDIA key.');
  process.exit(2);
}
const port = Number(portText ?? 9100);
mkdirSync(folder, { recursive: true });
const log = (entry) =>
  appendFileSync(path.join(folder, 'relay.jsonl'), `${JSON.stringify(entry)}\n`);
let count = 0;
let inFlight = 0;

/** What a request was, for the log: its model, and the first words of its instructions. */
function about(body) {
  try {
    const parsed = JSON.parse(body.toString('utf8'));
    const system = String(parsed.messages?.[0]?.content ?? '');
    return { model: parsed.model, stream: parsed.stream ?? false, system: system.slice(0, 80) };
  } catch {
    return {};
  }
}

http
  .createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const body = Buffer.concat(chunks);
    const number = ++count;
    const stem = path.join(folder, String(number).padStart(3, '0'));
    const started = Date.now();
    if (body.length > 0) writeFileSync(`${stem}.request.json`, body);
    inFlight += 1;
    log({
      n: number,
      event: 'start',
      path: request.url,
      inFlight,
      at: new Date().toISOString(),
      ...about(body),
    });

    const stop = new AbortController();
    response.on('close', () => {
      if (!response.writableEnded) stop.abort();
    });
    try {
      const upstream = await fetch(UPSTREAM + (request.url ?? '').replace(/^\/v1/, ''), {
        method: request.method,
        headers: {
          'content-type': request.headers['content-type'] ?? 'application/json',
          accept: request.headers.accept ?? '*/*',
          authorization: `Bearer ${key}`,
        },
        body: request.method === 'GET' || request.method === 'HEAD' ? undefined : body,
        signal: stop.signal,
      });
      response.writeHead(upstream.status, {
        'content-type': upstream.headers.get('content-type') ?? 'application/json',
      });
      const kept = createWriteStream(`${stem}.response.txt`);
      let first = null;
      if (upstream.body) {
        for await (const chunk of upstream.body) {
          first ??= Date.now();
          response.write(chunk);
          kept.write(chunk);
        }
      }
      response.end();
      kept.end();
      log({
        n: number,
        event: 'end',
        status: upstream.status,
        firstByteSeconds: first === null ? null : (first - started) / 1000,
        seconds: (Date.now() - started) / 1000,
      });
    } catch (error) {
      log({ n: number, event: 'error', message: String(error).slice(0, 300) });
      if (!response.headersSent) response.writeHead(502, { 'content-type': 'application/json' });
      response.end(JSON.stringify({ error: { message: 'The relay could not reach NVIDIA.' } }));
    } finally {
      inFlight -= 1;
    }
  })
  .listen(port, '127.0.0.1', () => console.log(`Relaying 127.0.0.1:${port} to ${UPSTREAM}`));
