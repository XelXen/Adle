import { Monitor, Moon, Sun } from 'lucide-react';

import { Card, Section, SegmentedControl, Stack } from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import type { ThemePreference } from '../../lib/bridge';
import { usePrefersReducedMotion } from '../../lib/theme';
import styles from './Settings.module.css';

const THEME_OPTIONS = [
  { value: 'system', label: 'System', icon: <Monitor /> },
  { value: 'light', label: 'Light', icon: <Sun /> },
  { value: 'dark', label: 'Dark', icon: <Moon /> },
] as const;

/** Theme and motion. Changes apply immediately and are remembered. */
export function AppearanceSettings() {
  const { ui, updateUi } = useApp();
  const reducedMotion = usePrefersReducedMotion();

  return (
    <Stack gap={6}>
      <Section title="Theme" description="Choose how Adle looks. System follows your computer.">
        <Card>
          <SegmentedControl<ThemePreference>
            label="Theme"
            value={ui.theme}
            options={THEME_OPTIONS}
            onValueChange={(theme) => void updateUi({ theme })}
          />
        </Card>
      </Section>

      <Section title="Motion and text size">
        <Card>
          <Stack gap={3}>
            <p>
              Reduced motion is <strong>{reducedMotion ? 'on' : 'off'}</strong>. Adle follows your
              system setting: with it on, interface transitions are removed and lessons avoid
              unnecessary movement.
            </p>
            <p className={styles.muted}>
              To change text size, use the View menu or press Ctrl (⌘ on Mac) with + or −.
            </p>
          </Stack>
        </Card>
      </Section>
    </Stack>
  );
}
