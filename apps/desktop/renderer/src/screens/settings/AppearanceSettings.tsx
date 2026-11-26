import { Blend, Monitor, Moon, MoonStar, Sun } from 'lucide-react';

import {
  Card,
  ColorSwatches,
  Section,
  SegmentedControl,
  Slider,
  Stack,
  Switch,
} from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import type { ThemePreference } from '../../lib/bridge';
import { usePrefersReducedMotion } from '../../lib/theme';
import { hueName, isPastelTheme, PASTEL_SWATCHES } from './appearance-model';
import styles from './Settings.module.css';

const THEME_OPTIONS = [
  { value: 'system', label: 'System', icon: <Monitor /> },
  { value: 'light', label: 'Light', icon: <Sun /> },
  { value: 'dark', label: 'Dark', icon: <Moon /> },
  { value: 'pastel', label: 'Pastel', icon: <Blend /> },
  { value: 'pastel-dark', label: 'Pastel dark', icon: <MoonStar /> },
] as const;

/** Theme, motion, and notifications. Changes apply immediately and are remembered. */
export function AppearanceSettings() {
  const { ui, updateUi } = useApp();
  const reducedMotion = usePrefersReducedMotion();

  return (
    <Stack gap={6}>
      <Section title="Theme" description="System follows your computer’s setting.">
        <Card>
          <Stack gap={5}>
            <SegmentedControl<ThemePreference>
              label="Theme"
              value={ui.theme}
              options={THEME_OPTIONS}
              onValueChange={(theme) => void updateUi({ theme })}
            />
            {/* Pastel and Pastel dark are in a color the learner picks (ADR-074). */}
            {isPastelTheme(ui.theme) ? (
              <Stack gap={4}>
                <Stack gap={2}>
                  <span className={styles.fieldLabel} aria-hidden="true">
                    Color
                  </span>
                  <ColorSwatches
                    label="Color"
                    value={ui.pastelHue}
                    swatches={PASTEL_SWATCHES}
                    onValueChange={(pastelHue) => void updateUi({ pastelHue })}
                  />
                </Stack>
                <Slider
                  label="Any color"
                  value={ui.pastelHue}
                  min={0}
                  max={359}
                  step={1}
                  track="spectrum"
                  formatValue={hueName}
                  onValueChange={(pastelHue) => void updateUi({ pastelHue })}
                  className={styles.hueSlider}
                />
              </Stack>
            ) : null}
          </Stack>
        </Card>
      </Section>

      <Section
        title="Notifications"
        description="Lessons take a few minutes to write. Get notified instead of waiting."
      >
        <Card>
          <Switch
            label="Notify me when something is ready"
            description="For lessons, suggestions, answers, and breaks. Only while Adle is in the background, and never with any lesson content."
            checked={ui.notifications}
            onCheckedChange={(notifications) => void updateUi({ notifications })}
          />
        </Card>
      </Section>

      <Section title="Motion and text size">
        <Card>
          <Stack gap={3}>
            <p>
              Reduced motion is <strong>{reducedMotion ? 'on' : 'off'}</strong>. Adle follows your
              system setting.
            </p>
            <p className={styles.muted}>To change text size, press Ctrl (⌘ on Mac) with + or −.</p>
          </Stack>
        </Card>
      </Section>
    </Stack>
  );
}
