import { NOTICE_KINDS, type NoticeKind } from '../shared/ipc';

/** What a notification of the operating system says. */
export interface Notice {
  title: string;
  body: string;
}

/**
 * Every notification Adle can show, word for word.
 *
 * The page asks for one by its kind and nothing else. It cannot supply a title, a
 * sentence, or a name: the words are these, so nothing from a lesson, a document, a
 * model's answer, or a course's title can reach the notification centre, where other
 * people may read it and other programs may keep it (ADR-026).
 */
const NOTICES: Record<NoticeKind, Notice> = {
  lesson_ready: {
    title: 'Your lesson is ready',
    body: 'Open Adle to start it.',
  },
  concepts_ready: {
    title: 'Suggested concepts are ready',
    body: 'Review them and choose what to add.',
  },
  answer_ready: {
    title: 'Your answer is ready',
    body: 'It’s next to the part of the lesson you asked about.',
  },
  writing_stopped: {
    title: 'Adle couldn’t finish writing',
    body: 'Open Adle to see what happened.',
  },
  break_over: {
    title: 'Your break is over',
    body: 'Ready when you are.',
  },
  film_ready: {
    title: 'Your film is ready',
    body: 'Open Adle to watch it.',
  },
};

/** A kind of notification, if it is one Adle has words for. Anything else is refused. */
export function parseNoticeKind(value: unknown): NoticeKind | null {
  return typeof value === 'string' && (NOTICE_KINDS as readonly string[]).includes(value)
    ? (value as NoticeKind)
    : null;
}

export function noticeFor(kind: NoticeKind): Notice {
  return NOTICES[kind];
}

/**
 * Whether to show a notification at all.
 *
 * Only when the learner has left them on, the operating system can show one, and Adle
 * is not what they are looking at: while its window has the focus, the app says the
 * same thing itself, and a second announcement from the system would be noise.
 */
export function shouldNotify(state: {
  enabled: boolean;
  supported: boolean;
  focused: boolean;
  /** One of this kind was shown a moment ago. */
  justShown?: boolean;
}): boolean {
  return state.enabled && state.supported && !state.focused && !state.justShown;
}

/** One notification of a kind says it; a second within this long says nothing new. */
export const SAME_NOTICE_AGAIN_AFTER_MS = 10_000;

/**
 * Remembers when each kind of notification was last shown, so that a page that asks again
 * and again (by mistake, or on purpose) gets one notification and not a stream of them.
 */
export class NoticePace {
  private readonly shownAt = new Map<NoticeKind, number>();

  constructor(private readonly now: () => number = Date.now) {}

  justShown(kind: NoticeKind): boolean {
    const last = this.shownAt.get(kind);
    return last !== undefined && this.now() - last < SAME_NOTICE_AGAIN_AFTER_MS;
  }

  shown(kind: NoticeKind): void {
    this.shownAt.set(kind, this.now());
  }
}
