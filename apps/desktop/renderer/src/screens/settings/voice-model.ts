import type { Job, VoiceStatus, VoiceTier } from '@adle/contracts';

/** A size of a download as a person says it: "about 0.6 GB", "about 12 GB". */
export function aboutSize(bytes: number): string {
  const gigabytes = bytes / 1e9;
  if (gigabytes < 0.1) return `about ${Math.max(1, Math.round(bytes / 1e6))} MB`;
  const shown = gigabytes < 10 ? Math.round(gigabytes * 10) / 10 : Math.round(gigabytes);
  return `about ${shown} GB`;
}

/** What setting a size of voice up downloads: its models and the programs it runs with. */
export function setupBytes(tier: VoiceTier): number {
  return tier.model_bytes + tier.program_bytes;
}

/** Where a size of voice stands on this computer, which is what its card offers. */
export type TierState =
  | { kind: 'in-use' }
  | { kind: 'ready' }
  | { kind: 'setting-up'; job: Job }
  | { kind: 'waiting' }
  | { kind: 'available' }
  | { kind: 'unavailable'; why: string };

export function tierState(status: VoiceStatus, tier: VoiceTier): TierState {
  const setup = status.setting_up;
  if (setup && setup.subject_id === tier.id) return { kind: 'setting-up', job: setup };
  if (tier.ready) {
    return status.enabled && status.tier === tier.id ? { kind: 'in-use' } : { kind: 'ready' };
  }
  if (!tier.fits) return { kind: 'unavailable', why: tier.why };
  // One voice is set up at a time.
  if (setup) return { kind: 'waiting' };
  return { kind: 'available' };
}

/** The computer's own voice reads the lessons when no natural voice does. */
export function computerVoiceInUse(status: VoiceStatus): boolean {
  return !status.enabled || status.tier === null;
}

/** Offered as the best for this computer: the richest it runs, until one is set up. */
export function isRecommended(status: VoiceStatus, tier: VoiceTier): boolean {
  return status.recommended === tier.id && !status.tiers.some((each) => each.ready);
}

const gigabytes = (bytes: number): string => (bytes / 1e9).toFixed(1);

/** How far a setup has come, as its bar shows it: what it is doing, and how much is done. */
export function setupProgress(job: Job): {
  label: string;
  value: number | undefined;
  valueText: string | undefined;
} {
  if (job.status === 'queued') {
    return { label: 'Waiting to start', value: undefined, valueText: undefined };
  }
  const label = job.progress_message || 'Getting ready';
  const { progress_done: done, progress_total: total } = job;
  if (total <= 0) return { label, value: undefined, valueText: undefined };
  const value = Math.min(1, done / total);
  if (label === 'Downloading the voice') {
    return { label, value, valueText: `${gigabytes(done)} of ${gigabytes(total)} GB` };
  }
  if (label === 'Downloading the voice’s programs') {
    return { label, value, valueText: `${done} of ${total}` };
  }
  return { label, value, valueText: undefined };
}

/** Where a setup downloads from, said once, in a list a person would write. */
export function downloadNote(tier: VoiceTier): string {
  const places = new Intl.ListFormat('en-GB', { type: 'conjunction' }).format(tier.sources);
  return (
    `Downloads ${aboutSize(setupBytes(tier))} from ${places}: the voice, and the programs it ` +
    'runs with. Nothing of yours is sent. Once it is set up it works without a connection.'
  );
}
