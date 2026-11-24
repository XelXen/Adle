import { useEffect, useRef, useState } from 'react';

import type { Job } from '@adle/contracts';
import { useToast } from '@adle/design-system';

import { callCore, describeError } from './core-client';
import { soundOf } from './use-recorded-narration';

/** How often a sample being made is looked at. */
const LOOK_EVERY_MS = 400;

/**
 * What a sample is asked for with: a speaker of a size, or the Expressive voice of a text
 * or of the parts it is put together from (ADR-062).
 */
export interface SampleRequest {
  tier: 'kokoro' | 'expressive';
  speaker?: string;
  design?: string;
  parts?: Record<string, string>;
}

/** The name of the sample a finished job made, or null for one that made none. */
export function sampleName(job: Job): string | null {
  if (job.status !== 'succeeded' || typeof job.result !== 'object' || job.result === null) {
    return null;
  }
  const name = (job.result as { sample?: unknown }).sample;
  return typeof name === 'string' && /^[0-9a-f]{24}$/.test(name) ? name : null;
}

/**
 * A few words in a voice set up here, made by the core (once: it keeps them) and played
 * (ADR-057). `making` is the key of the one being made or played, for its button.
 */
export function useVoiceSample(): {
  making: string | null;
  listen: (key: string, request: SampleRequest) => Promise<void>;
} {
  const toast = useToast();
  const [making, setMaking] = useState<string | null>(null);
  const playing = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);

  useEffect(
    () => () => {
      playing.current?.pause();
      if (url.current) URL.revokeObjectURL(url.current);
    },
    [],
  );

  const listen = async (key: string, request: SampleRequest): Promise<void> => {
    setMaking(key);
    try {
      let job: Job = await callCore('voice.sample', { body: request });
      while (job.status === 'queued' || job.status === 'running') {
        await new Promise((resolve) => {
          window.setTimeout(resolve, LOOK_EVERY_MS);
        });
        job = await callCore('jobs.get', { path: { job_id: job.id } });
      }
      const name = sampleName(job);
      if (!name) throw new Error(job.error_message ?? 'The sample couldn’t be made.');
      const clip = await callCore('voice.sample_clip', { path: { name } });
      playing.current?.pause();
      if (url.current) URL.revokeObjectURL(url.current);
      url.current = soundOf(clip);
      const sound = new Audio(url.current);
      playing.current = sound;
      await sound.play();
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t play a sample',
        description: describeError(error),
      });
    } finally {
      setMaking(null);
    }
  };

  return { making, listen };
}
