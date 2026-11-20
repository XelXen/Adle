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
    body: 'Adle has finished writing it.',
  },
  concepts_ready: {
    title: 'Suggested concepts are ready',
    body: 'Have a look, and choose what to add.',
  },
  answer_ready: {
    title: 'Your question has an answer',
    body: 'It is beside the part of the lesson you asked about.',
  },
  writing_stopped: {
    title: 'Adle could not finish what it was writing',
    body: 'Open Adle to see what happened. Nothing was lost.',
  },
  break_over: {
    title: 'Your break is over',
    body: 'Ready when you are.',
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
}): boolean {
  return state.enabled && state.supported && !state.focused;
}
