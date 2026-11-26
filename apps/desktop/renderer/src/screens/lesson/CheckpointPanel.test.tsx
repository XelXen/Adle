import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { AnswerResult, PlayerQuestion } from '@adle/contracts';

import { CheckpointPanel } from './CheckpointPanel';

/**
 * A question typed into, against a stand-in for the core, which scores. What a near miss is
 * (ADR-078) is the core's to say; here, what the page does when it is told one.
 */
const answers: AnswerResult[] = [];
const sent: unknown[] = [];

vi.mock('../../lib/core-client', () => ({
  describeError: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  callCore: (_operation: string, request: { body: unknown }) => {
    sent.push(request.body);
    const next = answers.shift();
    return next ? Promise.resolve(next) : Promise.reject(new Error('Nothing to answer with.'));
  },
}));

const QUESTION: PlayerQuestion = {
  id: 'q_propane',
  concept_id: 'con_alkanes',
  form: 'short_answer',
  stem: 'Write the formula of propane.',
  difficulty: 1,
  is_transfer: false,
};

const KNOWLEDGE = {
  state: 'building',
  label: 'Building',
  missing: [],
  answered: 0,
} as unknown as AnswerResult['knowledge'];

function said(outcome: AnswerResult['outcome'], more: Partial<AnswerResult> = {}): AnswerResult {
  return {
    outcome,
    feedback: null,
    explanation: '',
    correct_answer: '',
    correct_option: null,
    change: '',
    knowledge: KNOWLEDGE,
    attempt_number: 0,
    ...more,
  };
}

describe('a question answered by typing', () => {
  beforeEach(() => {
    answers.length = 0;
    sent.length = 0;
    // What is said of an answer is brought into view; jsdom draws nothing to scroll.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('says a near miss, keeps the answer open, and reports nothing until it is answered again (ADR-078)', async () => {
    const user = userEvent.setup();
    const onAnswered = vi.fn();
    answers.push(
      said('near', { feedback: 'Check what you typed, and try again.' }),
      said('correct', {
        explanation: 'Three carbons, single bonds.',
        correct_answer: 'CH3CH2CH3',
        change: 'You answered a short-answer question correctly.',
        attempt_number: 1,
      }),
    );
    render(<CheckpointPanel lessonId="les_1" question={QUESTION} onAnswered={onAnswered} />);

    const field = screen.getByRole('textbox', { name: 'Your answer' });
    await user.type(field, 'CH3CHWCH3');
    await user.click(screen.getByRole('button', { name: 'Check answer' }));

    // Almost: said, nothing of the answer shown, and the answer still there to mend.
    expect(await screen.findByText('Almost')).toBeInTheDocument();
    expect(screen.getByText('Check what you typed, and try again.')).toBeInTheDocument();
    expect(screen.queryByText(/The answer:/)).not.toBeInTheDocument();
    expect(field).toBeEnabled();
    expect(field).toHaveValue('CH3CHWCH3');
    expect(onAnswered).not.toHaveBeenCalled();

    await user.clear(field);
    await user.type(field, 'CH3CH2CH3');
    await user.click(screen.getByRole('button', { name: 'Check answer' }));

    expect(await screen.findByText('Correct')).toBeInTheDocument();
    expect(screen.queryByText('Almost')).not.toBeInTheDocument();
    expect(onAnswered).toHaveBeenCalledTimes(1);
    expect(onAnswered.mock.calls[0]![0]).toMatchObject({ outcome: 'correct' });
    expect(sent).toEqual([
      expect.objectContaining({ text: 'CH3CHWCH3' }),
      expect.objectContaining({ text: 'CH3CH2CH3' }),
    ]);
  });
});
