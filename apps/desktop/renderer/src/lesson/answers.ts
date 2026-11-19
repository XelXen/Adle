import type { AnswerRequest, PlayerQuestion } from '@adle/contracts';

/** What the learner has entered so far for one question. */
export interface AnswerDraft {
  /** Chosen option (choice questions) or "true" / "false". */
  choice: string | null;
  /** Typed answer (numeric and short-answer questions). */
  text: string;
  /** Item ids in the learner's order (ordering questions). */
  order: string[];
  /** Rubric points the learner says their own explanation covered. */
  covered: string[];
}

export function emptyDraft(question: PlayerQuestion): AnswerDraft {
  return {
    choice: null,
    text: '',
    order: (question.options ?? []).map((option) => option.id),
    covered: [],
  };
}

/** The minus sign that word processors and phones insert in place of a hyphen. */
const TYPOGRAPHIC_MINUS = String.fromCharCode(0x2212);
const DECIMAL = /^[-+]?(?:\d+(?:\.\d*)?|\.\d+)$/;
const FRACTION = /^([-+]?\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/;

/**
 * Read a number the way a learner types one: "3", "-0.5", ".25", "2,5", "1/2",
 * with either kind of minus sign. Returns null for anything else.
 */
export function parseNumber(input: string): number | null {
  let text = input.trim().replaceAll(TYPOGRAPHIC_MINUS, '-');
  // A single comma and no full stop is a decimal comma.
  if (/^[^.,]*,[^.,]*$/.test(text)) text = text.replace(',', '.');
  if (DECIMAL.test(text)) return Number(text);
  const fraction = FRACTION.exec(text);
  if (fraction) {
    const denominator = Number(fraction[2]);
    return denominator === 0 ? null : Number(fraction[1]) / denominator;
  }
  return null;
}

export type BuiltAnswer = { ok: true; body: AnswerRequest } | { ok: false; message: string };

/** Turn a draft into the request for the core, or say what is still missing. */
export function buildAnswer(question: PlayerQuestion, draft: AnswerDraft): BuiltAnswer {
  switch (question.form) {
    case 'multiple_choice':
    case 'prediction':
      return draft.choice === null
        ? { ok: false, message: 'Choose one of the options first.' }
        : { ok: true, body: { option_id: draft.choice } };
    case 'true_false':
      return draft.choice === null
        ? { ok: false, message: 'Choose true or false first.' }
        : { ok: true, body: { truth: draft.choice === 'true' } };
    case 'numeric': {
      const number = parseNumber(draft.text);
      return number === null
        ? { ok: false, message: 'Enter a number, for example 2.5 or 1/2.' }
        : { ok: true, body: { number } };
    }
    case 'short_answer':
      return draft.text.trim() === ''
        ? { ok: false, message: 'Type your answer first.' }
        : { ok: true, body: { text: draft.text.trim() } };
    case 'ordering':
      return { ok: true, body: { order: draft.order } };
    case 'explanation':
      return { ok: true, body: { covered: draft.covered } };
  }
}

/** Move one item of a list a step earlier or later. */
export function moved<T>(items: readonly T[], index: number, by: -1 | 1): T[] {
  const target = index + by;
  const copy = [...items];
  const item = copy[index];
  const other = copy[target];
  if (item === undefined || other === undefined) return copy;
  copy[index] = other;
  copy[target] = item;
  return copy;
}
