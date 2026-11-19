import { Blocks, HardDrive, Route as RouteIcon, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { Button, Callout, Logo } from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import { useRouter } from '../../app/router';
import styles from './WelcomeScreen.module.css';

const HIGHLIGHTS = [
  {
    icon: RouteIcon,
    title: 'A curriculum you can inspect',
    body: 'Adle turns a topic or your own materials into concepts and prerequisites that you can review and edit before you start.',
  },
  {
    icon: Blocks,
    title: 'Lessons you can touch',
    body: 'Narrated explanations with interactive visuals, followed by short questions. Every animation has a text equivalent.',
  },
  {
    icon: Sparkles,
    title: 'Teaching that adapts, with reasons',
    body: 'Adle tracks what you have shown you understand and explains why it chose your next step. You can always choose differently.',
  },
] as const;

/** First-run screen: what Adle is, and exactly what does and does not leave this computer. */
export function WelcomeScreen() {
  const { updateUi } = useApp();
  const { navigate } = useRouter();
  const [busy, setBusy] = useState(false);

  const finish = async (destination: 'home' | 'ai'): Promise<void> => {
    setBusy(true);
    try {
      await updateUi({ onboardingCompleted: true });
      navigate(destination === 'ai' ? { name: 'settings', tab: 'ai' } : { name: 'home' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className={styles.screen}>
      <div className={styles.panel}>
        <header className={styles.header}>
          <Logo size="large" />
          <h1 className={styles.headline}>Learn at your own pace. Understand for real.</h1>
          <p className={styles.lede}>
            Adle is a learning environment that works out what you already understand and teaches
            what you need next.
          </p>
        </header>

        <ul className={styles.highlights}>
          {HIGHLIGHTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className={styles.highlight}>
              <span className={styles.highlightIcon} aria-hidden="true">
                <Icon />
              </span>
              <div>
                <h2 className={styles.highlightTitle}>{title}</h2>
                <p className={styles.highlightBody}>{body}</p>
              </div>
            </li>
          ))}
        </ul>

        <Callout tone="info" title="Your learning stays on this computer">
          <p>
            <HardDrive className={styles.inlineIcon} aria-hidden="true" /> Course files, answers,
            and progress are stored only here. There are no accounts and no analytics.
          </p>
          <p className={styles.calloutSecond}>
            One thing uses the internet: creating a course or lesson with AI sends the relevant text
            to the provider you set up (AIHubMix by default). Nothing is sent until you add a key
            and ask for it.
          </p>
        </Callout>

        <div className={styles.actions}>
          <Button variant="primary" size="large" loading={busy} onClick={() => void finish('home')}>
            Get started
          </Button>
          <Button size="large" disabled={busy} onClick={() => void finish('ai')}>
            Set up AI first
          </Button>
        </div>
      </div>
    </main>
  );
}
