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
  if (others.length === 0) return '';
  return `Uses ${first}. If it is unavailable, ${listed(others)} ${
    others.length === 1 ? 'stands' : 'stand'
  } in, and Adle says so.`;
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
    : { text: 'No key', tone: undefined };
}

/** What kind of provider this is, in a sentence: what "automatic" goes by. */
export function providerCharacter(
  choice: Pick<ProviderChoice, 'quick' | 'limits_published'>,
): string {
  if (choice.quick) {
    return choice.limits_published ? 'Fast, with a small daily allowance.' : 'Fast.';
  }
  return choice.limits_published
    ? 'Slower: its models reason before they answer.'
    : 'Slower, with room for many lessons a day.';
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
  const pace = `At most ${usage.requests_per_minute} requests a minute, one at a time.`;
  const reset = resetsAt ? ` Resets at ${resetsAt}.` : '';
  if (usage.limits_published) {
    return `Adle’s own count, kept just under the provider’s daily limit. ${pace}${reset}`;
  }
  return `${provider.display_name} publishes no daily limit, so this is Adle’s own cap. ${pace}${reset}`;
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
        'Uses each provider you have a key for, for what it does best. If one can’t answer, ' +
        'the other is asked, and Adle says so.',
      recommended: true,
    },
    ...providers.map((provider) => ({
      value: provider.provider_id,
      label: `${provider.display_name} only`,
      description: `Only ${provider.display_name} is used. Nothing ever goes elsewhere.`,
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
  ask: 'Questions',
  curriculum: 'Suggested concepts',
  lesson: 'Lessons',
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
