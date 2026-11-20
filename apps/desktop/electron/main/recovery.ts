import type { AppLog } from './app-log';

/**
 * What happens when the app itself fails: its page stops (the process crashed, was killed,
 * or ran out of memory), its page stops answering, or the main process throws something
 * nobody caught.
 *
 * In every case the learner is told what happened in plain words and given a way on, and
 * a line goes into the local log. Nothing is sent anywhere (ADR-018). Nothing the learner
 * did is lost either: answers and progress are saved by the core as they happen, which is
 * why each message can say so.
 *
 * The decisions are here, without Electron, so they can be tested; `index.ts` connects
 * them to the window and the process.
 */

export interface Question {
  title: string;
  message: string;
  detail: string;
  /** The first button is the default, and what Enter does. */
  buttons: readonly [string, string];
}

/** Ask the learner something in a window of the operating system. Resolves with the button's index. */
export type Ask = (question: Question) => Promise<number>;

export const PAGE_GONE: Question = {
  title: 'Adle stopped working',
  message: 'The window stopped working and has to be reloaded.',
  detail:
    'Your answers and your progress were saved as you went, so nothing is lost. ' +
    'Nothing about this is sent anywhere.',
  buttons: ['Reload', 'Quit Adle'],
};

export const PAGE_HUNG: Question = {
  title: 'Adle is not responding',
  message: 'The window has stopped responding.',
  detail:
    'You can wait for it, or reload it. Your answers and your progress were saved as you ' +
    'went, so reloading loses nothing.',
  buttons: ['Wait', 'Reload'],
};

export const MAIN_FAILED: Question = {
  title: 'Adle ran into a problem',
  message: 'Something went wrong inside Adle, and it should be restarted.',
  detail:
    'Your answers and your progress were saved as you went. What went wrong was noted in ' +
    'a log file on this computer; nothing is sent anywhere.',
  buttons: ['Restart Adle', 'Quit Adle'],
};

/** Ways a page's process ends that are not a failure. */
const NOT_A_FAILURE = new Set(['clean-exit']);

export interface PageActions {
  ask: Ask;
  reload: () => void;
  quit: () => void;
  log: AppLog;
}

export type PageOutcome = 'ignored' | 'reloaded' | 'quit' | 'waited';

/** The page's process is gone. Tell the learner; reload or quit as they choose. */
export async function whenPageGone(
  details: { reason: string; exitCode: number },
  actions: PageActions,
): Promise<PageOutcome> {
  if (NOT_A_FAILURE.has(details.reason)) return 'ignored';
  actions.log.record('page-gone', { reason: details.reason, exitCode: details.exitCode });
  const answer = await actions.ask(PAGE_GONE);
  if (answer === 0) {
    actions.reload();
    return 'reloaded';
  }
  actions.quit();
  return 'quit';
}

/** The page has stopped answering. Waiting is the default: it may only be busy. */
export async function whenPageHung(actions: PageActions): Promise<PageOutcome> {
  actions.log.record('page-unresponsive');
  const answer = await actions.ask(PAGE_HUNG);
  if (answer === 1) {
    actions.reload();
    return 'reloaded';
  }
  return 'waited';
}

/**
 * One question at a time. A page that crashes while the learner is still reading about the
 * last crash must not stack a second window on top of the first.
 */
export function oneAtATime<Args extends unknown[]>(
  handler: (...args: Args) => Promise<unknown>,
): (...args: Args) => void {
  let busy = false;
  return (...args) => {
    if (busy) return;
    busy = true;
    void handler(...args)
      // A question that could not even be asked must not become a failure of its own.
      .catch(() => undefined)
      .finally(() => {
        busy = false;
      });
  };
}

/**
 * A promise was rejected and nothing was waiting for it. That is a bug worth knowing about,
 * but one piece of work failing is not the whole app failing: it is noted and nothing else.
 */
export function noteRejection(reason: unknown, log: AppLog): void {
  log.record('unhandled-rejection', describeError(reason));
}

/** How many times the core is started again by itself, and within how long. */
export const MAX_CORE_RESTARTS = 2;
export const CORE_RESTART_WINDOW_MS = 5 * 60 * 1000;

/**
 * Whether a core that stopped by itself should be started again without asking.
 *
 * Once or twice, yes: the learner should not have to find a button because a process died.
 * A core that keeps dying is not helped by being started for ever, so after that it stays
 * stopped, says so, and the learner can start it from Settings when they choose.
 * `earlier` holds the times of the automatic restarts so far.
 */
export function mayRestartCore(earlier: readonly number[], now: number): boolean {
  const recent = earlier.filter((time) => now - time < CORE_RESTART_WINDOW_MS);
  return recent.length < MAX_CORE_RESTARTS;
}

export interface MainActions {
  ask: Ask;
  restart: () => void;
  quit: () => void;
  log: AppLog;
  /** How long the app has been running, in seconds. */
  uptimeSeconds: () => number;
}

/** A restart is offered only once the app has run this long, so a failure at start-up cannot loop. */
export const MIN_UPTIME_TO_RESTART_SECONDS = 15;

export const MAIN_FAILED_AT_START: Question = {
  ...MAIN_FAILED,
  message: 'Something went wrong while Adle was starting.',
  buttons: ['Quit Adle', 'Quit Adle'],
};

function describeError(error: unknown): { name: string; message: string; stack: string | null } {
  if (error instanceof Error) {
    return { name: error.name, message: error.message, stack: error.stack ?? null };
  }
  return { name: 'NonError', message: String(error), stack: null };
}

/**
 * Something was thrown in the main process and nobody caught it. Its state can no longer
 * be trusted, so it does not carry on: the learner is told, and the app restarts or quits.
 */
export async function whenMainFailed(
  error: unknown,
  actions: MainActions,
): Promise<'restarted' | 'quit'> {
  actions.log.record('uncaught-exception', describeError(error));
  if (actions.uptimeSeconds() < MIN_UPTIME_TO_RESTART_SECONDS) {
    await actions.ask(MAIN_FAILED_AT_START);
    actions.quit();
    return 'quit';
  }
  const answer = await actions.ask(MAIN_FAILED);
  if (answer === 0) {
    actions.restart();
    return 'restarted';
  }
  actions.quit();
  return 'quit';
}
