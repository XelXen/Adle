import type { ProviderChoice, ProviderUsage } from '@adle/contracts';

import type { ExternalLinkId, ProviderKeyState } from '../../lib/bridge';

/** "A", "A and B", "A, B, and C". */
function listed(names: readonly string[]): string {
  if (names.length <= 2) return names.join(' and ');
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`;
}

/**
 * Which model a provider's requests go to, and which stand in for it, in a sentence.
 *
 * This is said where the learner chooses the provider, before anything is sent, because
 * a stand-in is still somewhere their text goes. Keep it true to `ModelGateway` in the core.
 */
export function modelOrder(models: readonly { name: string }[]): string {
  const names = models.map((model) => model.name);
  const [first, ...others] = names;
  if (first === undefined) return '';
  if (others.length === 0) return `Every request goes to ${first}.`;
  return (
    `Requests go to ${first}. While it is not available, ${listed(others)} ` +
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
 * What a badge beside a provider says about its key: only whether there is one. Which key
 * it is (its last characters) is shown once, where the key is looked after.
 */
export function keyBadge(state: ProviderKeyState | undefined): {
  text: string;
  tone: 'success' | undefined;
} {
  return state?.stored
    ? { text: 'Key saved', tone: 'success' }
    : { text: 'No key yet', tone: undefined };
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
    `It sends one request at a time, and never more than ${usage.requests_per_minute} a ` +
    'minute: it waits instead.';
  const reset = resetsAt ? ` The count starts again at ${resetsAt}.` : '';
  if (usage.limits_published) {
    return `Adle stops a little short of the provider's daily limit. ${pace}${reset}`;
  }
  return (
    `${provider.display_name} does not publish a daily limit for these models, so the ones ` +
    `above are Adle's own: room for many lessons a day, and a stop if something goes wrong. ` +
    `${pace}${reset}`
  );
}
