import { Blocks, HardDrive, Route as RouteIcon, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { Button, Logo } from '@adle/design-system';

import { useApp } from '../../app/AppContext';
import { useRouter } from '../../app/router';
import styles from './WelcomeScreen.module.css';

const HIGHLIGHTS = [
  {
    icon: RouteIcon,
    title: 'A curriculum you control',
    body: 'Turn a topic or your own materials into a map of concepts you can review and edit.',
  },
  {
    icon: Blocks,
    title: 'Interactive lessons',
    body: 'Narrated explanations with visuals you can interact with, then a few short questions.',
  },
  {
    icon: Sparkles,
    title: 'Teaching that adapts',
    body: 'Adle follows what you understand and explains every next step. You can always choose another.',
  },
] as const;

/**
 * A lesson in miniature, drawn rather than photographed: a picture with something to move,
 * the words beside it, and where the learner is in the whole. It decorates the welcome and
 * says nothing a reader of the text beside it would miss.
 */
function LessonSketch() {
  return (
    <div className={styles.sketch} aria-hidden="true">
      <div className={styles.sketchStrip}>
        <span className={styles.sketchDone} />
        <span className={styles.sketchDone} />
        <span className={styles.sketchNow} />
        <span />
        <span />
        <span />
      </div>
      <p className={styles.sketchTitle}>What a neuron does with its sum</p>
      <div className={styles.sketchBody}>
        <svg className={styles.sketchStage} viewBox="0 0 240 150">
          <line className={styles.sketchAxis} x1="20" y1="124" x2="224" y2="124" />
          <line className={styles.sketchAxis} x1="122" y1="16" x2="122" y2="130" />
          <path
            className={styles.sketchCurve}
            d="M20 122 C 80 122, 98 114, 122 72 S 164 24, 224 22"
          />
          <line className={styles.sketchGuide} x1="150" y1="124" x2="150" y2="42" />
          <circle className={styles.sketchDot} cx="150" cy="42" r="5.5" />
          <line className={styles.sketchTrack} x1="42" y1="142" x2="202" y2="142" />
          <line className={styles.sketchFill} x1="42" y1="142" x2="150" y2="142" />
          <circle className={styles.sketchKnob} cx="150" cy="142" r="5" />
        </svg>
        <div className={styles.sketchWords}>
          <span className={styles.sketchSaid} />
          <span className={styles.sketchSaid} />
          <span className={styles.sketchSaying} />
          <span className={styles.sketchSaying} />
          <span className={styles.sketchUnsaid} />
          <span className={styles.sketchUnsaid} />
        </div>
      </div>
      <div className={styles.sketchNext}>
        <span className={styles.sketchNextLabel}>Next</span>
        <span className={styles.sketchNextText}>
          The perceptron, because it builds on what you have just shown
        </span>
      </div>
    </div>
  );
}

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
      <div className={styles.layout}>
        <div className={styles.panel}>
          <header className={styles.header}>
            <Logo size="large" />
            <h1 className={styles.headline}>Learn at your own pace. Understand for real.</h1>
            <p className={styles.lede}>
              Adle works out what you already know and teaches what you need next.
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

          <section className={styles.promise} aria-labelledby="welcome-promise">
            <HardDrive className={styles.promiseIcon} aria-hidden="true" />
            <div className={styles.promiseText}>
              <h2 id="welcome-promise" className={styles.promiseTitle}>
                Private by default
              </h2>
              <p>
                Your files, answers, and progress stay on this computer. No accounts, no analytics.
              </p>
              <p>
                Only AI generation uses the internet: when you ask for a course, a lesson, or an
                answer, the relevant text goes to the provider you set up (AIHubMix or NVIDIA NIM).
                Nothing is sent until you add a key and ask.
              </p>
            </div>
          </section>

          <div className={styles.actions}>
            <Button
              variant="primary"
              size="large"
              loading={busy}
              onClick={() => void finish('home')}
            >
              Get started
            </Button>
            <Button size="large" disabled={busy} onClick={() => void finish('ai')}>
              Set up AI first
            </Button>
          </div>
        </div>
        <LessonSketch />
      </div>
    </main>
  );
}
