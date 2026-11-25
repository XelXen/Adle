import type { Ask, Job } from '@adle/contracts';

/**
 * A question the learner puts to Adle in the middle of a lesson (ADR-024). Called an
 * "ask" in code, to keep it apart from the questions a lesson puts to the learner.
 *
 * The answer is written by a model, in the core, as a job. Nothing here decides what is
 * sent: this file holds the words around it and reads what the job says.
 */

export const KIND_ASK = 'lesson_ask';

/** The same bounds the core enforces (`application/asks.py`). */
export const MIN_QUESTION_CHARACTERS = 3;
export const MAX_QUESTION_CHARACTERS = 500;

/**
 * Ready-made questions for a part of a lesson: the ways a learner most often wants
 * something explained again (simpler, by example, with the mathematics, with the reason).
 *
 * Where the part is a question the lesson is asking and the learner has not answered it,
 * the suggestions ask for help with thinking, never for the answer: Adle would not give
 * it anyway.
 */
export function suggestedQuestions(kind: string, unanswered: boolean): string[] {
  if (kind === 'checkpoint') {
    return unanswered
      ? [
          'Give me a nudge, not the answer.',
          'Which idea is this question about?',
          'Show me a similar example.',
        ]
      : ['Why is that the right answer?', 'Show me a similar example.'];
  }
  return [
    'Explain this more simply.',
    'Give me an example.',
    'Show the mathematics behind this.',
    'Why is this true?',
  ];
}

/**
 * The kinds of part whose picture can be drawn again at the learner's word (ADR-067): the
 * core's list (`lessons.DRAWN_AGAIN`). A question, a reflection and something to try have
 * none to change.
 */
const DRAWN_AGAIN = new Set(['explanation', 'visualization', 'worked_example', 'summary']);

/** Whether the learner can ask for this kind of part's picture to be drawn again. */
export function canRedraw(kind: string): boolean {
  return DRAWN_AGAIN.has(kind);
}

/** Ready-made requests for a picture drawn again. The learner's own words say it best. */
export function suggestedRedraws(): string[] {
  return [
    'Draw what the words describe that the picture leaves out.',
    'Label each thing in the picture.',
    'Show it one step at a time.',
  ];
}

/**
 * Everything a question sends, as a list to put between "Sends" and "to <provider>"; asking
 * for the picture to be drawn again sends the picture too (ADR-067).
 *
 * A promise made before anything is sent. Keep it in step with `ask_request` and
 * `redraw_request` in the core (`generation/prompts.py`): if a request gains something, it
 * is named here first.
 */
export function askDisclosure(redraw = false): string {
  return redraw
    ? 'what you asked for, this part of the lesson with its picture, the lesson title, the ' +
        'course name, and this concept'
    : 'your question, this part of the lesson, the lesson outline, the course name, this ' +
        'concept, and any related passages from your materials';
}

/** What is wrong with a question as typed, or null if it can be asked. */
export function questionProblem(text: string): string | null {
  const length = text.trim().length;
  if (length === 0) return 'Type a question, or pick a suggestion.';
  if (length < MIN_QUESTION_CHARACTERS) return 'That’s too short to be a question.';
  if (length > MAX_QUESTION_CHARACTERS) {
    return `Keep it under ${MAX_QUESTION_CHARACTERS} characters.`;
  }
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Which kept answer a finished job produced, or null if it did not produce one. */
export function answeredAskId(job: Job | null): string | null {
  if (!job || job.kind !== KIND_ASK || job.status !== 'succeeded') return null;
  const result = job.result;
  return isRecord(result) && typeof result.ask_id === 'string' ? result.ask_id : null;
}

/** Who wrote an answer: "Kimi K3.1 Pro on NVIDIA NIM", or the provider alone. */
export function answeredBy(ask: Pick<Ask, 'written_by'>): string {
  const provider = ask.written_by.provider ?? '';
  const [model, ...others] = ask.written_by.models ?? [];
  if (model !== undefined && others.length === 0 && provider) return `${model} on ${provider}`;
  return provider || 'AI';
}

/** The questions asked about one part of a lesson, oldest first. */
export function asksAbout(asks: readonly Ask[], segmentId: string): Ask[] {
  return asks.filter((ask) => ask.segment_id === segmentId);
}
