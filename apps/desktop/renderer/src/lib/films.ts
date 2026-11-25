import type { CourseFilm, Film, FilmChapter, FilmCue, FilmMakerStatus, Job } from '@adle/contracts';

import { callCore } from './core-client';

/**
 * A film of a whole course (ADR-065), in the words the interface shows. Nothing here
 * decides anything about a film: the core does (`films.get`, `films.maker_status`), and
 * this reads it and fetches what it made.
 */

export const KIND_FILM = 'film_making';
export const KIND_FILM_SETUP = 'film_setup';

/** Where a course's film stands, which is what its tab offers. */
export type FilmStage =
  | { kind: 'unavailable'; why: string }
  | { kind: 'set-up'; maker: FilmMakerStatus }
  | { kind: 'setting-up'; job: Job }
  | { kind: 'blocked'; why: string }
  | { kind: 'ready-to-make' }
  | { kind: 'making'; film: Film; job: Job }
  | { kind: 'unfinished'; film: Film }
  | { kind: 'ready'; film: Film };

export function filmStage(view: CourseFilm, maker: FilmMakerStatus): FilmStage {
  const film = view.film;
  if (film?.status === 'ready') return { kind: 'ready', film };
  if (film?.making) return { kind: 'making', film, job: film.making };
  if (maker.setting_up) return { kind: 'setting-up', job: maker.setting_up };
  if (!maker.ready) {
    return maker.fits
      ? { kind: 'set-up', maker }
      : { kind: 'unavailable', why: 'The film maker doesn’t run on this kind of computer.' };
  }
  if (film?.status === 'unfinished') return { kind: 'unfinished', film };
  if (view.plan.blocked) return { kind: 'blocked', why: view.plan.blocked };
  return { kind: 'ready-to-make' };
}

/** A chapter's state as the learner reads it, while a film is made or after. */
export function chapterState(chapter: FilmChapter, next: boolean): string {
  if (chapter.state === 'written') {
    return chapter.problems > 0 ? 'Written, with a little overlap' : 'Written and checked';
  }
  if (chapter.state === 'in_words') return 'Told in words';
  return next ? 'Being written' : 'Waiting';
}

/** The chapter being worked on now: the first not written yet. */
export function nextChapter(film: Film): number {
  return film.chapters.findIndex((chapter) => chapter.state === 'waiting');
}

/** A time in a film, as a player shows it: 0:05, 3:41, 1:02:09. */
export function clockOf(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = String(whole % 60).padStart(2, '0');
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

/**
 * A size on the disk as a person says it: "about 110 MB" under a gigabyte, to the nearest
 * ten, and "about 1.4 GB" over one.
 */
export function aboutBytes(bytes: number): string {
  if (bytes < 1e9) return `about ${Math.max(10, Math.round(bytes / 1e7) * 10)} MB`;
  const gigabytes = bytes / 1e9;
  return `about ${gigabytes < 10 ? Math.round(gigabytes * 10) / 10 : Math.round(gigabytes)} GB`;
}

/** How long a film is, said plainly: "12 minutes", "1 hour 4 minutes". */
export function lengthOf(seconds: number): string {
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'}`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const head = `${hours} hour${hours === 1 ? '' : 's'}`;
  return rest ? `${head} ${rest} minute${rest === 1 ? '' : 's'}` : head;
}

/**
 * How long making a film of this many chapters is likely to take, from how long one
 * chapter usually takes where it would be written. Each chapter is checked and may be
 * mended, so it is said as at least that, and never more exactly than it is known.
 */
/**
 * What making a film sends besides its chapters' words, and how many requests it may make
 * at most, as the core planned it: put after "Sends … to …". Each chapter's pictures go to
 * a model that reads them when one can be asked (ADR-066).
 */
export function filmRequests(requestsAtMost: number, picturesTo: string | null): string {
  if (picturesTo) {
    return (
      `Sends pictures of each chapter to ${picturesTo} to be checked. At most ${requestsAtMost} ` +
      'requests: one for each chapter, up to three more for each to fix it, and one for each ' +
      'to check its pictures.'
    );
  }
  return `At most ${requestsAtMost} requests: one for each chapter, and up to three more for each to fix it.`;
}

export function makingTakes(chapters: number, secondsPerChapter: number): string {
  const minutes = Math.round((chapters * Math.max(60, secondsPerChapter) * 1.5) / 60);
  if (minutes < 50) return `at least ${Math.max(5, Math.round(minutes / 5) * 5)} minutes`;
  const hours = Math.round(minutes / 30) / 2;
  return hours <= 1 ? 'about an hour or more' : `${hours} hours or more`;
}

/** The line being said at a moment of the film, if one is. */
export function cueAt(cues: readonly FilmCue[], seconds: number): FilmCue | null {
  let low = 0;
  let high = cues.length - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    const cue = cues[middle];
    if (!cue) return null;
    if (seconds < cue.start) high = middle - 1;
    else if (seconds >= cue.end) low = middle + 1;
    else return cue;
  }
  return null;
}

/** Which chapter a moment of the film is in: the last that began before it. */
export function chapterAt(chapters: readonly FilmChapter[], seconds: number): number {
  let found = -1;
  chapters.forEach((chapter, index) => {
    if (chapter.start !== null && chapter.start <= seconds + 0.05) found = index;
  });
  return found;
}

function stamp(seconds: number): string {
  const whole = Math.max(0, seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = whole % 60;
  const two = (value: number): string => String(value).padStart(2, '0');
  return `${two(hours)}:${two(minutes)}:${rest.toFixed(3).padStart(6, '0')}`;
}

/**
 * A film's words as subtitles the browser's own player shows (WebVTT). The words are the
 * film's own, written by the AI: a cue is plain text, so nothing in one can be read as a
 * cue's settings or its markup.
 */
export function vttOf(cues: readonly FilmCue[]): string {
  const lines = ['WEBVTT', ''];
  for (const cue of cues) {
    if (!(cue.end > cue.start)) continue;
    const text = cue.text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .split(/\r?\n/)
      .filter((line) => line.trim() !== '')
      .join('\n');
    if (!text) continue;
    lines.push(`${stamp(cue.start)} --> ${stamp(cue.end)}`, text, '');
  }
  return lines.join('\n');
}

function bytesOf(data: string): Uint8Array<ArrayBuffer> {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

/**
 * A film's video, fetched from the core a part at a time and made a video of the page's
 * own to play (the page has no network, and the core names a film by its id, never by a
 * path). `onProgress` is told how much of it has come, from 0 to 1. Stops between parts
 * when `stopped` says so.
 */
export async function fetchFilm(
  filmId: string,
  onProgress: (share: number) => void,
  stopped: () => boolean,
): Promise<string | null> {
  const parts: Uint8Array<ArrayBuffer>[] = [];
  let total = 1;
  for (let part = 0; part < total; part += 1) {
    if (stopped()) return null;
    const answer = await callCore('films.video_part', {
      path: { film_id: filmId, part },
    });
    total = answer.parts;
    parts.push(bytesOf(answer.data));
    onProgress((part + 1) / total);
  }
  if (stopped()) return null;
  return URL.createObjectURL(new Blob(parts, { type: 'video/mp4' }));
}
