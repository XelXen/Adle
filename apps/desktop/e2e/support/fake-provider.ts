/**
 * A stand-in for the AI provider, for end-to-end tests.
 *
 * It is a small HTTP server on this computer that speaks the same streamed
 * chat-completion protocol as the real provider. The app under test is pointed
 * at it with `ADLE_PROVIDER_BASE_URL`, so every part of the real path is
 * exercised (the core's client, quota, jobs, the interface) and nothing leaves
 * the machine. No end-to-end test ever reaches the real provider.
 *
 * By default it answers each kind of request with a good canned answer (the
 * same ones the Python tests use, from `fixtures/model-answers`). A test can
 * queue other answers ahead of the defaults: a refusal, nonsense, or a hang.
 */
import { readFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import path from 'node:path';

import { repoRoot } from './app';
import { exampleScene } from './player';

const answers = path.join(repoRoot, 'fixtures', 'model-answers');
const read = (name: string): string => readFileSync(path.join(answers, name), 'utf8');

export type RequestKind = 'curriculum' | 'lesson' | 'scene' | 'ask' | 'check';

export interface RecordedRequest {
  kind: RequestKind;
  /** The `Authorization` header as it arrived. */
  authorization: string | undefined;
  /** Everything the model was shown: the system and user text. */
  prompt: string;
  body: Record<string, unknown>;
}

/**
 * What to answer with:
 *  - a string: the text of the model's answer;
 *  - `{ status }`: an HTTP error with that status;
 *  - `{ notice }`: a successful answer that the provider wrote itself, in the model's place,
 *    in the shape the real provider was seen to use on 2026-11-20;
 *  - `HANG`: accept the request and say nothing until the test releases it or the app gives up;
 *  - `{ slowly }`: the ordinary answer, the way a model that thinks gives it: thinking for
 *    `thinkMs`, then the answer in pieces that each end just after a title, `pieceMs` apart.
 */
export type Answer =
  | string
  | { status: number; retryAfter?: number }
  | { notice: string }
  | { hang: true }
  | { slowly: true; thinkMs: number; pieceMs: number };

/** An answer that never comes by itself. */
export const HANG: Answer = { hang: true };

export interface FakeProvider {
  /** The value for `ADLE_PROVIDER_BASE_URL`. */
  baseUrl: string;
  requests: RecordedRequest[];
  /** Answer the next requests with these before falling back to the defaults. */
  queue: (...next: Answer[]) => void;
  /**
   * From now on, every request of this kind hangs like `HANG`, whatever is queued: a
   * picture that takes its time while the lesson it belongs to is already written.
   */
  hold: (kind: RequestKind) => void;
  /** Let the requests hanging now finish with an ordinary answer. Kinds held stay held. */
  pass: () => void;
  /** Let every hanging request finish with an ordinary answer, and hold nothing any more. */
  release: () => void;
  close: () => Promise<void>;
}

function kindOf(system: string): RequestKind {
  if (system.includes('design the curriculum')) return 'curriculum';
  if (system.includes('Wanim scene file')) return 'scene';
  // A question the learner asked in the middle of a lesson, and the check of a key.
  if (system.includes('partway through a lesson')) return 'ask';
  if (system.includes('checking that a connection works')) return 'check';
  return 'lesson';
}

function defaultAnswer(kind: RequestKind, user: string): string {
  if (kind === 'curriculum') return read('curriculum.json');
  if (kind === 'lesson') return read('lesson.json');
  if (kind === 'ask') return read('answer.json');
  if (kind === 'check') return 'ready';
  return exampleScene(user.includes('Kind: interactive') ? 'neuron_weight.py' : 'weighted_sum.py');
}

/** The answer the fake gives a request of this kind when nothing else was queued. */
export function cannedAnswer(kind: 'curriculum' | 'lesson' | 'ask'): string {
  return defaultAnswer(kind, '');
}

/**
 * A scene that passes every rule and breaks when it runs: only trying it shows that
 * (ADR-038).
 */
export const BROKEN_SCENE = `from manim import *


class Broken(Scene):
    """Passes the rules and fails when it runs."""

    def setup(self):
        dark = self.theme == "dark"
        self.ink = "#E7EFE9" if dark else "#17251E"

    def construct(self):
        dot = Dot(color=self.ink)
        self.play(FadeIn(dot))
        self.wait(0.5)
        raise ValueError("this picture breaks halfway")
`;

function readBody(request: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    request.on('data', (chunk: Buffer) => chunks.push(chunk));
    request.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    request.on('error', reject);
  });
}

/** Send `text` the way the provider streams it: a few chunks, usage, then the end marker. */
function stream(response: ServerResponse, text: string): void {
  response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
  const step = Math.max(1, Math.ceil(text.length / 4));
  for (let index = 0; index < text.length; index += step) {
    const chunk = { choices: [{ delta: { content: text.slice(index, index + step) } }] };
    response.write(`data: ${JSON.stringify(chunk)}\n\n`);
  }
  response.write(
    `data: ${JSON.stringify({ choices: [{ delta: {}, finish_reason: 'stop' }] })}\n\n`,
  );
  response.write(
    `data: ${JSON.stringify({ choices: [], usage: { prompt_tokens: 1200, completion_tokens: 600 } })}\n\n`,
  );
  response.end('data: [DONE]\n\n');
}

const pause = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

/** `text` cut just after each title, so that each piece completes one title. */
export function piecesAtTitles(text: string): string[] {
  const pieces: string[] = [];
  let from = 0;
  for (const match of text.matchAll(/"title"\s*:\s*"(?:[^"\\]|\\.)*"/g)) {
    const end = match.index + match[0].length;
    pieces.push(text.slice(from, end));
    from = end;
  }
  pieces.push(text.slice(from));
  return pieces.filter((piece) => piece.length > 0);
}

/**
 * Send `text` the way a model that thinks first sends it: its thinking, a pause, then the
 * answer piece by piece. Stops as soon as the app hangs up.
 */
async function streamSlowly(
  request: IncomingMessage,
  response: ServerResponse,
  text: string,
  thinkMs: number,
  pieceMs: number,
): Promise<void> {
  const gone = (): boolean => response.destroyed || request.socket.destroyed;
  response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
  const thinking = { choices: [{ delta: { content: null, reasoning_content: 'Planning.' } }] };
  response.write(`data: ${JSON.stringify(thinking)}\n\n`);
  await pause(thinkMs);
  for (const piece of piecesAtTitles(text)) {
    if (gone()) return;
    response.write(`data: ${JSON.stringify({ choices: [{ delta: { content: piece } }] })}\n\n`);
    await pause(pieceMs);
  }
  if (gone()) return;
  response.write(
    `data: ${JSON.stringify({ choices: [{ delta: {}, finish_reason: 'stop' }] })}\n\n`,
  );
  response.end('data: [DONE]\n\n');
}

/**
 * A notice as the real provider sent one: a single chunk whose identifier begins
 * "chatcmpl-fake", marked as finished, with no report of tokens used.
 */
function streamNotice(response: ServerResponse, notice: string): void {
  response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
  const chunk = {
    choices: [{ delta: { content: notice, role: 'assistant' }, finish_reason: 'stop', index: 0 }],
    created: 1795158495,
    id: 'chatcmpl-fake-1795158495575810024',
    model: 'coding-kimi-k3-free',
    object: 'chat.completion.chunk',
  };
  response.write(`data: ${JSON.stringify(chunk)}\n\n`);
  response.end('data: [DONE]\n\n');
}

export async function startFakeProvider(options: { delayMs?: number } = {}): Promise<FakeProvider> {
  const delayMs = options.delayMs ?? 250;
  const requests: RecordedRequest[] = [];
  const queued: Answer[] = [];
  const held = new Set<RequestKind>();
  const hanging = new Set<() => void>();

  const server = createServer((request, response) => {
    void (async () => {
      if (request.method !== 'POST' || request.url !== '/v1/chat/completions') {
        response.writeHead(404).end();
        return;
      }
      const body = JSON.parse(await readBody(request)) as Record<string, unknown> & {
        messages: { role: string; content: string }[];
      };
      const system = body.messages[0]?.content ?? '';
      const user = body.messages[1]?.content ?? '';
      const kind = kindOf(system);
      requests.push({
        kind,
        authorization: request.headers.authorization,
        prompt: `${system}\n${user}`,
        body,
      });

      const answer = held.has(kind) ? HANG : (queued.shift() ?? defaultAnswer(kind, user));
      if (typeof answer === 'object' && 'hang' in answer) {
        await new Promise<void>((resolve) => {
          hanging.add(resolve);
          // The app closing the connection (a cancel) ends the wait too.
          request.socket.on('close', resolve);
        });
        if (response.destroyed || request.socket.destroyed) return;
        stream(response, defaultAnswer(kind, user));
        return;
      }
      // Long enough for the interface to show that something is happening.
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      if (typeof answer === 'string') {
        stream(response, answer);
        return;
      }
      if ('notice' in answer) {
        streamNotice(response, answer.notice);
        return;
      }
      if ('slowly' in answer) {
        await streamSlowly(
          request,
          response,
          defaultAnswer(kind, user),
          answer.thinkMs,
          answer.pieceMs,
        );
        return;
      }
      const headers: Record<string, string> = { 'content-type': 'application/json' };
      if (answer.retryAfter !== undefined) headers['retry-after'] = String(answer.retryAfter);
      response.writeHead(answer.status, headers);
      response.end(JSON.stringify({ error: { message: 'refused by the fake provider' } }));
    })().catch(() => {
      if (!response.headersSent) response.writeHead(500);
      response.end();
    });
  });

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;

  return {
    baseUrl: `http://127.0.0.1:${port}/v1`,
    requests,
    queue: (...next) => {
      queued.push(...next);
    },
    hold: (kind) => {
      held.add(kind);
    },
    pass: () => {
      for (const resolve of hanging) resolve();
      hanging.clear();
    },
    release: () => {
      held.clear();
      for (const resolve of hanging) resolve();
      hanging.clear();
    },
    close: () =>
      new Promise<void>((resolve) => {
        for (const finish of hanging) finish();
        hanging.clear();
        server.closeAllConnections();
        server.close(() => resolve());
      }),
  };
}
