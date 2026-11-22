import { Volume2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import type { LearnerPreferences } from '@adle/contracts';
import { Button, Select, Slider, Spinner, Stack } from '@adle/design-system';

import type { Utterance } from '../../lesson/narration';
import {
  browserLine,
  browserSpeech,
  loadLocalVoices,
  pickVoice,
  SpeechNarrator,
} from '../../lesson/speech';
import { useResource } from '../../lib/use-resource';
import styles from './Settings.module.css';

const SAMPLE =
  'This is how a lesson will sound. A neuron multiplies each input by its weight, adds the results, and then adds a bias.';

/** How long the slider may rest before its value is saved. */
const SAVE_AFTER_MS = 350;

interface PreferenceProps {
  preferences: LearnerPreferences;
  onChange: (patch: Partial<LearnerPreferences>) => void;
}

/** How loudly lessons are read, in whichever voice reads them. */
export function VolumeSetting({ preferences, onChange }: PreferenceProps) {
  const [volume, setVolume] = useState(preferences.volume);

  // The slider moves freely; what it comes to rest on is saved.
  const saved = preferences.volume;
  useEffect(() => {
    if (volume === saved) return;
    const timer = window.setTimeout(() => onChange({ volume }), SAVE_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, [volume, saved, onChange]);

  return (
    <div className={styles.voiceField}>
      <Slider
        label="Volume"
        value={volume}
        min={0}
        max={100}
        step={5}
        formatValue={(value) => (value === 0 ? 'Silent' : `${value}%`)}
        onValueChange={setVolume}
      />
    </div>
  );
}

/**
 * Which of the voices installed in the operating system reads lessons, with a sample. It
 * also reads what a natural voice has not recorded yet. Reading aloud sends nothing anywhere.
 */
export function ComputerVoiceSettings({ preferences, onChange }: PreferenceProps) {
  const voices = useResource('speech-voices', () => loadLocalVoices(browserSpeech()));
  const [sampling, setSampling] = useState(false);
  const sample = useRef<Utterance | null>(null);

  useEffect(() => () => sample.current?.cancel(), []);

  if (voices.resource.status === 'loading') {
    return <Spinner size="small" label="Loading voices" />;
  }
  const installed = voices.resource.status === 'ready' ? voices.resource.data : [];
  const engine = browserSpeech();
  if (!engine || installed.length === 0) {
    return (
      <p className={styles.muted}>
        None is installed. Install one in your system settings and it will appear here.
      </p>
    );
  }

  const playSample = (): void => {
    sample.current?.cancel();
    const voice = pickVoice(installed, preferences.voice);
    if (!voice) return;
    setSampling(true);
    sample.current = new SpeechNarrator(engine, browserLine, {
      voice,
      pace: preferences.pace,
      volume: preferences.volume / 100,
    }).speak(SAMPLE, { onEnd: () => setSampling(false) });
  };

  const stopSample = (): void => {
    sample.current?.cancel();
    sample.current = null;
    setSampling(false);
  };

  const automatic = pickVoice(installed, '');
  return (
    <Stack gap={3}>
      <div className={styles.voiceField}>
        <Select
          label="Voice"
          description="Nothing is sent anywhere."
          value={
            installed.some((voice) => voice.name === preferences.voice) ? preferences.voice : ''
          }
          options={[
            { value: '', label: automatic ? `Automatic (${automatic.name})` : 'Automatic' },
            ...installed.map((voice) => ({
              value: voice.name,
              label: `${voice.name} · ${voice.lang}`,
            })),
          ]}
          onValueChange={(voice) => {
            stopSample();
            onChange({ voice });
          }}
        />
      </div>
      <div>
        <Button icon={<Volume2 />} onClick={sampling ? stopSample : playSample}>
          {sampling ? 'Stop the sample' : 'Play a sample'}
        </Button>
      </div>
    </Stack>
  );
}
