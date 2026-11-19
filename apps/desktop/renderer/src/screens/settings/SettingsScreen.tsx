import { GraduationCap, Info, KeyRound, Palette, ShieldCheck } from 'lucide-react';

import { Page, type TabItem, Tabs } from '@adle/design-system';

import { type SettingsTab, useRouter } from '../../app/router';
import { AboutSettings } from './AboutSettings';
import { AppearanceSettings } from './AppearanceSettings';
import { LearningSettings } from './LearningSettings';
import { PrivacySettings } from './PrivacySettings';
import { ProviderSettings } from './ProviderSettings';

const TABS: readonly TabItem<SettingsTab>[] = [
  { value: 'ai', label: 'AI provider', icon: <KeyRound /> },
  { value: 'learning', label: 'Learning', icon: <GraduationCap /> },
  { value: 'appearance', label: 'Appearance', icon: <Palette /> },
  { value: 'privacy', label: 'Privacy & data', icon: <ShieldCheck /> },
  { value: 'about', label: 'About & diagnostics', icon: <Info /> },
];

export function SettingsScreen({ tab }: { tab: SettingsTab }) {
  const { navigate } = useRouter();
  return (
    <Page title="Settings" description="How Adle connects, looks, and handles your data.">
      <Tabs
        label="Settings sections"
        tabs={TABS}
        value={tab}
        onValueChange={(next) => navigate({ name: 'settings', tab: next })}
      >
        {(current) => {
          switch (current) {
            case 'ai':
              return <ProviderSettings />;
            case 'learning':
              return <LearningSettings />;
            case 'appearance':
              return <AppearanceSettings />;
            case 'privacy':
              return <PrivacySettings />;
            case 'about':
              return <AboutSettings />;
          }
        }}
      </Tabs>
    </Page>
  );
}
