import { useEffect, useRef, useState } from 'react';

import type { Film } from '@adle/contracts';
import { Button, ErrorState, ProgressBar } from '@adle/design-system';

import { callCore, describeError } from '../../lib/core-client';
import { chapterAt, clockOf, fetchFilm, vttOf } from '../../lib/films';
import styles from './Film.module.css';

/**
 * A film of the course, played on a screen of its own (ADR-035, ADR-065): the browser's
 * own player, with its controls, its full screen and its subtitles, and the chapters
 * beside it to go to. The video is fetched from the core a part at a time and played from
 * the page's own memory: the page has no network, and a film is never named by a path.
 */
interface Loading {
  /** Which film, and which try at loading it, this is about. */
  key: string;
  loaded: number;
  source?: { video: string; captions: string };
  error?: unknown;
}

export function FilmPlayer({ film }: { film: Film }) {
  const video = useRef<HTMLVideoElement>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${film.id}:${attempt}`;
  const [loading, setLoading] = useState<Loading>({ key, loaded: 0 });
  const [now, setNow] = useState(0);
  // What was loaded for another film, or an earlier try, is not this one's.
  const mine: Loading = loading.key === key ? loading : { key, loaded: 0 };
  const { loaded, source, error } = mine;

  useEffect(() => {
    let stopped = false;
    const made: string[] = [];
    Promise.all([
      fetchFilm(
        film.id,
        (share) => {
          if (!stopped) setLoading({ key, loaded: share });
        },
        () => stopped,
      ),
      callCore('films.captions', { path: { film_id: film.id } }),
    ]).then(
      ([url, words]) => {
        if (url) made.push(url);
        if (stopped || !url) return;
        const captions = URL.createObjectURL(new Blob([vttOf(words.cues)], { type: 'text/vtt' }));
        made.push(captions);
        setLoading({ key, loaded: 1, source: { video: url, captions } });
      },
      (failure: unknown) => {
        if (!stopped) setLoading({ key, loaded: 0, error: failure });
      },
    );
    return () => {
      stopped = true;
      for (const url of made) URL.revokeObjectURL(url);
    };
  }, [film.id, key]);

  const goTo = (seconds: number): void => {
    const player = video.current;
    if (!player) return;
    player.currentTime = seconds;
    void player.play().catch(() => undefined);
  };
  const current = chapterAt(film.chapters, now);

  return (
    <div className={styles.panel}>
      <div className={styles.screen}>
        {error ? (
          <div className={styles.loading}>
            <ErrorState
              title="Couldn’t load the film"
              description={describeError(error)}
              actions={<Button onClick={() => setAttempt((count) => count + 1)}>Try again</Button>}
            />
          </div>
        ) : source ? (
          <video
            ref={video}
            className={styles.video}
            src={source.video}
            controls
            preload="metadata"
            aria-label={`Film: ${film.title}`}
            onTimeUpdate={(event) => setNow(event.currentTarget.currentTime)}
          >
            <track kind="captions" srcLang="en" label="English" src={source.captions} default />
          </video>
        ) : (
          <div className={styles.loading}>
            <ProgressBar
              label="Loading the film"
              showLabel
              value={loaded}
              valueText={loaded > 0 ? `${Math.round(loaded * 100)}%` : undefined}
            />
          </div>
        )}
      </div>
      <nav aria-label="Chapters of the film">
        <ol className={styles.marks}>
          <li>
            <Button
              size="small"
              variant={current < 0 ? 'secondary' : 'tertiary'}
              aria-current={current < 0 ? 'true' : undefined}
              disabled={!source}
              onClick={() => goTo(0)}
            >
              Introduction <span className={styles.time}>0:00</span>
            </Button>
          </li>
          {film.chapters.map((chapter, index) =>
            chapter.start === null ? null : (
              <li key={`${index}-${chapter.title}`}>
                <Button
                  size="small"
                  variant={current === index ? 'secondary' : 'tertiary'}
                  aria-current={current === index ? 'true' : undefined}
                  disabled={!source}
                  onClick={() => goTo(chapter.start ?? 0)}
                >
                  {index + 1}. {chapter.title}{' '}
                  <span className={styles.time}>{clockOf(chapter.start)}</span>
                </Button>
              </li>
            ),
          )}
        </ol>
      </nav>
    </div>
  );
}
