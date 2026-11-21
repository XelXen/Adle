import { Monitor, Moon, Sun } from 'lucide-react';

import { Card, Section, SegmentedControl, Stack, Switch } from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import type { ThemePreference } from '../../lib/bridge';
import { usePrefersReducedMotion } from '../../lib/theme';
import styles from './Settings.module.css';

const THEME_OPTIONS = [
  { value: 'system', label: 'System', icon: <Monitor /> },
  { value: 'light', label: 'Light', icon: <Sun /> },
  { value: 'dark', label: 'Dark', icon: <Moon /> },
] as const;

/** Theme, motion, and notifications. Changes apply immediately and are remembered. */
export function AppearanceSettings() {
  const { ui, updateUi } = useApp();
  const reducedMotion = usePrefersReducedMotion();

  return (
    <Stack gap={6}>
      <Section title="Theme" description="System follows your computer’s setting.">
        <Card>
          <SegmentedControl<ThemePreference>
            label="Theme"
            value={ui.theme}
            options={THEME_OPTIONS}
            onValueChange={(theme) => void updateUi({ theme })}
          />
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
