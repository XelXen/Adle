import type { ProviderChoice, ProviderStatus, ProviderUsage } from '@adle/contracts';

import type { ExternalLinkId, ProviderKeyState } from '../../lib/bridge';
import { AUTOMATIC, type Work } from '../../lib/provider';

/** "A", "A and B", "A, B, and C". */
function listed(names: readonly string[]): string {
  if (names.length <= 2) return names.join(' and ');
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`;
}

/**
 * Which model a provider's requests go to, and which stand in for it, in a sentence.
 *
 * This is said where the learner sees the provider, before anything is sent, because
 * a stand-in is still somewhere their text goes. Keep it true to `ModelGateway` in the core.
 */
export function modelOrder(models: readonly { name: string }[]): string {
  const names = models.map((model) => model.name);
  const [first, ...others] = names;
  if (first === undefined) return '';
  if (others.length === 0) return `Every request here goes to ${first}.`;
  return (
    `Requests here go to ${first}. While it is not available, ${listed(others)} ` +
    `${others.length === 1 ? 'stands' : 'stand'} in, in that order, and Adle tells you when ` +
    'that happened.'
  );
}

/** The page where a key for a provider is made, where Adle knows one. */
export function keyPage(providerId: string): { link: ExternalLinkId; label: string } | null {
  switch (providerId) {
    case 'aihubmix':
      return { link: 'aihubmixKeys', label: 'Get a key from AIHubMix' };
    case 'nvidia':
      return { link: 'nvidiaKeys', label: 'Get a key from NVIDIA' };
    default:
      return null;
  }
}

/**
 * What a badge beside a provider says about its key: whether there is one, and its last
 * characters so the learner can tell which.
 */
export function keyBadge(state: ProviderKeyState | undefined): {
  text: string;
  tone: 'success' | undefined;
} {
  return state?.stored
    ? { text: `Key saved · ends in ${state.hint ?? '…'}`, tone: 'success' }
    : { text: 'No key yet', tone: undefined };
}

/** What kind of provider this is, in a sentence: what "automatic" goes by. */
export function providerCharacter(
  choice: Pick<ProviderChoice, 'quick' | 'limits_published'>,
): string {
  if (choice.quick) {
    return choice.limits_published
      ? 'Quick to answer. Its daily allowance is small, so Adle counts what it sends.'
      : 'Quick to answer.';
  }
  return choice.limits_published
    ? 'Slower to answer: its models think before they write.'
    : 'Slower to answer: its models think before they write. Room for many lessons a day.';
}

/**
 * What today's count is measured against, in a sentence.
 *
 * Where a provider publishes its limits, Adle stops a little short of them. Where it does
 * not, the limits are Adle's own, and saying "the provider's limit" would be untrue.
 */
export function limitsNote(
  provider: Pick<ProviderChoice, 'display_name'>,
  usage: Pick<ProviderUsage, 'limits_published' | 'requests_per_minute'>,
  resetsAt: string,
): string {
  const pace =
    `Adle sends it one request at a time, and never more than ${usage.requests_per_minute} a ` +
    'minute: it waits instead.';
  const reset = resetsAt ? ` The count starts again at ${resetsAt}.` : '';
  if (usage.limits_published) {
    return `Adle's own count, kept a little short of the provider's daily limit. ${pace}${reset}`;
  }
  return (
    `${provider.display_name} does not publish a daily limit for these models, so these are ` +
    `Adle's own: room for many lessons a day, and a stop if something goes wrong. ` +
    `${pace}${reset}`
  );
}

export interface SelectionOption {
  value: string;
  label: string;
  description: string;
  recommended: boolean;
}

/**
 * What the learner can choose between: every provider they have a key for, or one alone.
 *
 * "Automatic" is described by what it does, never by a promise about speed: the core
 * decides where each request goes, and what it would do now is shown beside this
 * (`routeLines`). Keep it true to `generation/routing.py`.
 */
export function selectionOptions(
  providers: readonly Pick<ProviderChoice, 'provider_id' | 'display_name'>[],
): SelectionOption[] {
  return [
    {
      value: AUTOMATIC,
      label: 'Automatic',
      description:
        'Use every provider you have given a key to, each for what it is best at. What you ' +
        'are waiting for goes to the quicker one; long work goes to the one with more room ' +
        'once the quicker one is half used for the day. If one cannot answer, the other is ' +
        'asked, and Adle tells you.',
      recommended: true,
    },
    ...providers.map((provider) => ({
      value: provider.provider_id,
      label: `${provider.display_name} only`,
      description: `Every request goes to ${provider.display_name} and nowhere else, whatever happens.`,
      recommended: false,
    })),
  ];
}

export interface RouteLine {
  work: Work;
  /** What kind of request, as a learner would call it. */
  label: string;
  /** Where it would go at this moment. */
  destination: string;
  /** Why there, when there was something to decide. */
  reason: string;
}

const WORK_LABELS: Record<Work, string> = {
  ask: 'A question during a lesson',
  curriculum: 'A list of suggested concepts',
  lesson: 'A lesson and its pictures',
};

/** Where each kind of request would go at this moment, as the core says. */
export function routeLines(status: Pick<ProviderStatus, 'routes'>): RouteLine[] {
  return (['ask', 'curriculum', 'lesson'] as const).map((work) => ({
    work,
    label: WORK_LABELS[work],
    destination: status.routes[work].sentence,
    reason: status.routes[work].reason,
  }));
}

/**
 * Whether to point out that both providers could be used together: the learner chose one,
 * and has a key for another as well. It is only ever a suggestion with a button.
 */
export function couldUseBoth(
  status: Pick<ProviderStatus, 'selection'> & {
    providers: readonly Pick<ProviderChoice, 'key_configured'>[];
  },
): boolean {
  return (
    status.selection !== AUTOMATIC &&
    status.providers.filter((provider) => provider.key_configured).length > 1
  );
}
