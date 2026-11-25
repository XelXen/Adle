import { Clapperboard, Download, RotateCcw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import type { Course, CourseFilm, Film, FilmMakerStatus, Job } from '@adle/contracts';
import {
  Button,
  Callout,
  Dialog,
  Disclosure,
  EmptyState,
  ErrorState,
  LoadingState,
  ProgressBar,
  Section,
  useToast,
} from '@adle/design-system';

import { useFilmWatch } from '../../app/FilmWatch';
import { WhatIsSent } from '../../components/WhatIsSent';
import { getBridge } from '../../lib/bridge';
import { callCore, describeError } from '../../lib/core-client';
import {
  aboutBytes,
  filmRequests,
  chapterState,
  type FilmStage,
  filmStage,
  lengthOf,
  makingTakes,
} from '../../lib/films';
import { destination } from '../../lib/provider';
import { useJob } from '../../lib/use-job';
import { useResource } from '../../lib/use-resource';
import styles from './Film.module.css';
import { FilmPlayer } from './FilmPlayer';

/** What a film's chapter is written from, to put after "Sends". */
const FILM_SENDS =
  'each concept’s title, summary and objectives, and passages of your materials about it';
/** How often to look again while a film is made or the film maker set up. */
const LOOK_EVERY_MS = 2000;

/**
 * A film of the whole course (ADR-065): a chapter for each concept, in the order they are
 * learned, written by the AI as an animation, checked by the film maker at every moment
 * and mended, then put together, read in the natural voice, and made into a video.
 *
 * What it offers follows where the film stands (`filmStage`): setting the film maker up
 * (a download, at the learner's word), making the film (what is sent one press away, and
 * how long it takes said before), following it while it is made, continuing one left
 * unfinished, and watching, saving or removing one that is made.
 */
export function FilmPanel({ course }: { course: Course }) {
  const toast = useToast();
  const watch = useFilmWatch();
  const view = useResource(`film:${course.id}`, () =>
    callCore('films.get', { path: { course_id: course.id } }),
  );
  const maker = useResource('film-maker', () => callCore('films.maker_status'));
  const provider = useResource('provider-status', () => callCore('provider.status'));
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState<'remove' | 'again' | 'remove-maker' | null>(null);
  /** The setup followed to its end, and why it failed if it did. */
  const [setup, setSetup] = useState<Job | null>(null);
  const [setupFailed, setSetupFailed] = useState<string | null>(null);

  const viewData = view.resource.status === 'ready' ? view.resource.data : null;
  const makerData = maker.resource.status === 'ready' ? maker.resource.data : null;
  // A setup begun before this was shown is followed as well, to its end.
  const running = makerData?.setting_up ?? null;
  if (running && setup?.id !== running.id) setSetup(running);
  useJob(setup, (finished) => {
    maker.reload();
    view.reload();
    setSetupFailed(
      finished.status === 'failed'
        ? (finished.error_message ?? 'Check the connection and try again.')
        : null,
    );
  });
  const active = Boolean(viewData?.film?.making) || Boolean(makerData?.setting_up);
  const reloadView = view.reload;
  const reloadMaker = maker.reload;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => {
      reloadView();
      reloadMaker();
    }, LOOK_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [active, reloadView, reloadMaker]);

  if (view.resource.status === 'loading' || maker.resource.status === 'loading') {
    return <LoadingState title="Loading the film…" />;
  }
  if (view.resource.status === 'error' || maker.resource.status === 'error') {
    return (
      <ErrorState
        title="Couldn’t load the film"
        description={describeError(view.resource.error ?? maker.resource.error)}
        actions={
          <Button
            onClick={() => {
              view.reload();
              maker.reload();
            }}
          >
            Try again
          </Button>
        }
      />
    );
  }

  const data: CourseFilm = view.resource.data;
  const stage = filmStage(data, maker.resource.data);
  const status = provider.resource.status === 'ready' ? provider.resource.data : undefined;
  // A chapter is written, and its pictures looked over when they are (ADR-066).
  const perChapter =
    (status?.routes.film.wait_seconds ?? 300) +
    (data.plan.checks_pictures ? (status?.routes.storyboard.wait_seconds ?? 0) : 0);

  const act = async (work: () => Promise<unknown>, failed: string): Promise<boolean> => {
    setBusy(true);
    try {
      await work();
      return true;
    } catch (error) {
      toast.show({ tone: 'danger', title: failed, description: describeError(error) });
      return false;
    } finally {
      setBusy(false);
      view.reload();
      maker.reload();
      watch.refresh();
    }
  };
  const make = (): Promise<boolean> =>
    act(
      () => callCore('films.make', { path: { course_id: course.id } }),
      'Couldn’t begin the film',
    );
  const stop = (jobId: string): Promise<boolean> =>
    act(() => callCore('jobs.cancel', { path: { job_id: jobId } }), 'Couldn’t stop it');
  const remove = (): Promise<boolean> =>
    act(
      () => callCore('films.remove', { path: { course_id: course.id } }),
      'Couldn’t remove the film',
    );
  const save = async (shown: Film): Promise<void> => {
    setBusy(true);
    try {
      const result = await getBridge().films.saveFile(shown.id);
      if (!result.ok) throw new Error(result.error.message);
      if (result.data) {
        toast.show({
          tone: 'success',
          title: 'Film saved',
          description: result.data.withCaptions
            ? `${result.data.fileName}, with its subtitles beside it.`
            : result.data.fileName,
        });
      }
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'Couldn’t save the film',
        description: describeError(error),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.panel}>
      <Body
        stage={stage}
        plan={data}
        busy={busy}
        perChapter={perChapter}
        sendsTo={destination(status, 'film')}
        picturesTo={data.plan.checks_pictures ? destination(status, 'storyboard') : null}
        setupFailed={setupFailed}
        onSetUp={() => {
          setSetupFailed(null);
          void act(
            () => callCore('films.set_up_maker').then(setSetup),
            'Couldn’t set up the film maker',
          );
        }}
        onMake={() => void make()}
        onStop={(jobId) => void stop(jobId)}
        onSave={(shown) => void save(shown)}
        onAsk={setAsking}
      />

      {makerData?.ready && !makerData.borrowed && stage.kind !== 'making' ? (
        <Disclosure label="The film maker">
          <p className={styles.note}>
            It is set up on this computer and takes {aboutBytes(makerData.installed_bytes)}. Films
            already made are kept if it is removed.
          </p>
          <div className={styles.actions}>
            <Button variant="tertiary" icon={<Trash2 />} onClick={() => setAsking('remove-maker')}>
              Remove the film maker
            </Button>
          </div>
        </Disclosure>
      ) : null}

      <Dialog
        open={asking === 'remove' || asking === 'again'}
        onClose={() => setAsking(null)}
        title={asking === 'again' ? 'Make the film again?' : 'Remove the film?'}
        description={
          asking === 'again'
            ? 'This film is removed and a new one is made from the course as it is now.'
            : 'The film and its words are removed from this computer.'
        }
        actions={
          <>
            <Button onClick={() => setAsking(null)}>Cancel</Button>
            <Button
              variant={asking === 'again' ? 'primary' : 'destructive'}
              loading={busy}
              onClick={() => {
                const again = asking === 'again';
                void remove().then((removed) => {
                  setAsking(null);
                  if (removed && again) void make();
                });
              }}
            >
              {asking === 'again' ? 'Make it again' : 'Remove'}
            </Button>
          </>
        }
      />
      <Dialog
        open={asking === 'remove-maker'}
        onClose={() => setAsking(null)}
        title="Remove the film maker?"
        description="Films already made are kept. To make another, it is downloaded again."
        actions={
          <>
            <Button onClick={() => setAsking(null)}>Cancel</Button>
            <Button
              variant="destructive"
              loading={busy}
              onClick={() =>
                void act(
                  () => callCore('films.remove_maker'),
                  'Couldn’t remove the film maker',
                ).then(() => setAsking(null))
              }
            >
              Remove
            </Button>
          </>
        }
      />
    </div>
  );
}

interface BodyProps {
  stage: FilmStage;
  plan: CourseFilm;
  busy: boolean;
  perChapter: number;
  sendsTo: string;
  /** Where each chapter's pictures are sent to be checked; none when they are not (ADR-066). */
  picturesTo: string | null;
  /** Why the last setup of the film maker failed, when it did. */
  setupFailed: string | null;
  onSetUp: () => void;
  onMake: () => void;
  onStop: (jobId: string) => void;
  onSave: (film: Film) => void;
  onAsk: (question: 'remove' | 'again') => void;
}

function Body({
  stage,
  plan,
  busy,
  perChapter,
  sendsTo,
  picturesTo,
  setupFailed,
  onSetUp,
  onMake,
  onStop,
  onSave,
  onAsk,
}: BodyProps) {
  const chapters = plan.plan.chapters.length;
  const what = (
    <p className={styles.lead}>
      A narrated film that teaches the whole course, a chapter for each concept in the order they
      are learned. The AI writes each chapter as an animation; the film maker checks every moment of
      it, and has it fixed, before the film is put together.
    </p>
  );

  switch (stage.kind) {
    case 'unavailable':
      return (
        <EmptyState
          title="A film of the whole course"
          description={stage.why}
          visual={<Clapperboard />}
        />
      );
    case 'set-up':
      return (
        <Section title="A film of the whole course">
          {what}
          {setupFailed ? (
            <Callout tone="danger" title="Couldn’t set up the film maker">
              {setupFailed}
            </Callout>
          ) : null}
          <FilmMakerNeeded maker={stage.maker} busy={busy} onSetUp={onSetUp} />
        </Section>
      );
    case 'setting-up':
      return (
        <Section title="Setting up the film maker">
          <ProgressBar
            label={stage.job.progress_message || 'Setting up the film maker'}
            showLabel
            value={
              stage.job.progress_total > 0
                ? stage.job.progress_done / stage.job.progress_total
                : undefined
            }
          />
          <div className={styles.actions}>
            <Button loading={busy} onClick={() => onStop(stage.job.id)}>
              Stop
            </Button>
          </div>
        </Section>
      );
    case 'blocked':
      return (
        <Section title="A film of the whole course">
          {what}
          <Callout tone="info">{stage.why}</Callout>
        </Section>
      );
    case 'ready-to-make':
      return (
        <Section title="A film of the whole course">
          {what}
          <p className={styles.note}>
            {chapters} chapter{chapters === 1 ? '' : 's'}. Making it takes{' '}
            {makingTakes(chapters, perChapter)}: you don’t need to wait. Keep Adle open, and it
            tells you when the film is ready. {voiceNote(plan.plan.voice)}
          </p>
          <div className={styles.actions}>
            <Button variant="primary" icon={<Clapperboard />} loading={busy} onClick={onMake}>
              Make the film
            </Button>
            <WhatIsSent
              what={FILM_SENDS}
              to={sendsTo}
              after={filmRequests(plan.plan.requests_at_most, picturesTo)}
            />
          </div>
        </Section>
      );
    case 'making':
      return (
        <Section title="Making the film">
          <ProgressBar
            label={stage.job.progress_message || 'Making the film'}
            showLabel
            value={
              stage.job.progress_total > 0
                ? stage.job.progress_done / stage.job.progress_total
                : undefined
            }
          />
          <p className={styles.note}>
            You don’t need to wait here. Keep Adle open, and it tells you when the film is ready.
          </p>
          <Chapters film={stage.film} making />
          <div className={styles.actions}>
            <Button loading={busy} onClick={() => onStop(stage.job.id)}>
              Stop
            </Button>
          </div>
        </Section>
      );
    case 'unfinished':
      return (
        <Section title="The film isn’t finished">
          <Callout tone="warning">
            {stage.film.reason ?? 'It was stopped before it was made.'}
          </Callout>
          <Chapters film={stage.film} making={false} />
          <div className={styles.actions}>
            <Button variant="primary" loading={busy} onClick={onMake}>
              Continue
            </Button>
            <WhatIsSent
              what={FILM_SENDS}
              to={sendsTo}
              after={filmRequests(plan.plan.requests_at_most, picturesTo)}
            />
            <Button variant="tertiary" icon={<Trash2 />} onClick={() => onAsk('remove')}>
              Remove
            </Button>
          </div>
        </Section>
      );
    case 'ready':
      return (
        <Section title={stage.film.title}>
          <FilmPlayer film={stage.film} />
          <p className={styles.facts}>
            {stage.film.seconds ? lengthOf(stage.film.seconds) : null}
            {' · '}
            {stage.film.chapters.length} chapter{stage.film.chapters.length === 1 ? '' : 's'}
            {' · '}
            {stage.film.voice ? `Read in the ${stage.film.voice} voice` : 'No voice'}
          </p>
          {stage.film.notes.length ? (
            <ul className={styles.notes}>
              {stage.film.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
          <div className={styles.actions}>
            <Button icon={<Download />} loading={busy} onClick={() => onSave(stage.film)}>
              Save the film
            </Button>
            <Button variant="tertiary" icon={<RotateCcw />} onClick={() => onAsk('again')}>
              Make it again
            </Button>
            <Button variant="tertiary" icon={<Trash2 />} onClick={() => onAsk('remove')}>
              Remove the film
            </Button>
          </div>
        </Section>
      );
  }
}

function voiceNote(voice: string | null): string {
  return voice
    ? `It is read in the ${voice} voice.`
    : 'No natural voice is set up, so it has no sound: its words show as it plays.';
}

function FilmMakerNeeded({
  maker,
  busy,
  onSetUp,
}: {
  maker: FilmMakerStatus;
  busy: boolean;
  onSetUp: () => void;
}) {
  return (
    <>
      <p className={styles.note}>
        Making films needs the film maker on this computer: {aboutBytes(maker.download_bytes)} from{' '}
        {maker.sources.join(' and ')}, and {aboutBytes(maker.installed_bytes)} once it is set up.
      </p>
      <div className={styles.actions}>
        <Button variant="primary" loading={busy} onClick={onSetUp}>
          Set up the film maker
        </Button>
      </div>
    </>
  );
}

function Chapters({ film, making }: { film: Film; making: boolean }) {
  return (
    <ol className={styles.chapters} aria-label="Chapters">
      {film.chapters.map((chapter, index) => (
        <li
          key={`${index}-${chapter.title}`}
          className={`${styles.chapter} ${making && chapter.state === 'writing' ? styles.current : ''}`}
        >
          <span className={styles.chapterTitle}>
            {index + 1}. {chapter.title}
          </span>
          <span className={styles.chapterState}>{chapterState(chapter)}</span>
        </li>
      ))}
    </ol>
  );
}
