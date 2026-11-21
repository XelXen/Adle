/**
 * Notifications of the operating system: which exist, what each says, and when one is
 * shown. The words are fixed here; the page only ever names a kind (ADR-026).
 */
import { describe, expect, it } from 'vitest';

import { NOTICE_KINDS } from '../shared/ipc';
import {
  noticeFor,
  NoticePace,
  parseNoticeKind,
  SAME_NOTICE_AGAIN_AFTER_MS,
  shouldNotify,
} from './notices';

describe('parseNoticeKind', () => {
  it('accepts the kinds Adle has words for and nothing else', () => {
    for (const kind of NOTICE_KINDS) expect(parseNoticeKind(kind)).toBe(kind);
    for (const value of [
      'Lesson ready',
      'LESSON_READY',
      '',
      '__proto__',
      'toString',
      { kind: 'lesson_ready' },
      ['lesson_ready'],
      7,
      null,
      undefined,
    ]) {
      expect(parseNoticeKind(value)).toBeNull();
    }
  });
});

describe('noticeFor', () => {
  it('has a short title and one plain sentence for every kind', () => {
    for (const kind of NOTICE_KINDS) {
      const { title, body } = noticeFor(kind);
      expect(title.length).toBeGreaterThan(5);
      expect(title.length).toBeLessThanOrEqual(60);
      expect(body.length).toBeGreaterThan(5);
      expect(body.length).toBeLessThanOrEqual(90);
      // Nothing that hurries or blames, and no punctuation that shouts.
      expect(`${title} ${body}`).not.toMatch(/!|hurry|now!|don't miss|streak|failed/i);
    }
  });

  it('says what happened without anything of the learner in it', () => {
    expect(noticeFor('lesson_ready')).toEqual({
      title: 'Your lesson is ready',
      body: 'Open Adle to start it.',
    });
    expect(noticeFor('break_over').title).toBe('Your break is over');
    // When something could not be finished, it is said calmly, with where to look.
    expect(noticeFor('writing_stopped').body).toBe('Open Adle to see what happened.');
  });
});

describe('shouldNotify', () => {
  const quiet = { enabled: true, supported: true, focused: false };

  it('speaks only when Adle is not what the learner is looking at', () => {
    expect(shouldNotify(quiet)).toBe(true);
    expect(shouldNotify({ ...quiet, focused: true })).toBe(false);
  });

  it('never speaks when the learner turned notifications off, or the system has none', () => {
    expect(shouldNotify({ ...quiet, enabled: false })).toBe(false);
    expect(shouldNotify({ ...quiet, supported: false })).toBe(false);
  });

  it('does not say the same thing twice in a row', () => {
    expect(shouldNotify({ ...quiet, justShown: true })).toBe(false);
    expect(shouldNotify({ ...quiet, justShown: false })).toBe(true);
  });
});

describe('NoticePace', () => {
  it('lets one notification of a kind through, and the next only after a while', () => {
    let now = 1_000;
    const pace = new NoticePace(() => now);
    expect(pace.justShown('lesson_ready')).toBe(false);
    pace.shown('lesson_ready');
    expect(pace.justShown('lesson_ready')).toBe(true);
    // Another kind is another thing to say.
    expect(pace.justShown('break_over')).toBe(false);
    now += SAME_NOTICE_AGAIN_AFTER_MS - 1;
    expect(pace.justShown('lesson_ready')).toBe(true);
    now += 1;
    expect(pace.justShown('lesson_ready')).toBe(false);
  });
});
