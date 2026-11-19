import { Card, Section, Stack } from '@adle/design-system';

import styles from './Settings.module.css';

/** A plain statement of where data lives and what, if anything, leaves the device. */
export function PrivacySettings() {
  return (
    <Stack gap={6}>
      <Section title="Stored on this computer">
        <Card>
          <ul className={styles.list}>
            <li>Course materials you import, and the text extracted from them.</li>
            <li>Your curriculum, lessons, answers, and learning progress.</li>
            <li>Generated visuals and narration audio.</li>
            <li>Your AI provider key, encrypted by your operating system.</li>
          </ul>
        </Card>
      </Section>

      <Section title="Sent to the AI provider">
        <Card>
          <Stack gap={3}>
            <ul className={styles.list}>
              <li>
                Only when you start a generation: the instructions for that task, the concept being
                taught, and short passages from your materials that are relevant to it.
              </li>
              <li>For open-ended answers you ask Adle to assess: that answer and its rubric.</li>
            </ul>
            <p className={styles.muted}>
              Whole documents, your full learning history, and your key are never sent as content.
              Adle does not switch providers or contact any other service on its own.
            </p>
          </Stack>
        </Card>
      </Section>

      <Section title="Never collected">
        <Card>
          <ul className={styles.list}>
            <li>No accounts, analytics, advertising identifiers, or usage telemetry.</li>
            <li>No crash reports are uploaded.</li>
          </ul>
        </Card>
      </Section>
    </Stack>
  );
}
