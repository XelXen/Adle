import { describe, expect, it } from 'vitest';

import type { CourseFilm, Film, FilmChapter, FilmMakerStatus, Job } from '@adle/contracts';

import {
  aboutBytes,
  chapterAt,
  chapterState,
  clockOf,
  cueAt,
  filmStage,
  lengthOf,
  filmRequests,
  makingTakes,
  vttOf,
} from './films';

const MAKER: FilmMakerStatus = {
  ready: true,
  fits: true,
  borrowed: false,
  setting_up: null,
  download_bytes: 110_000_000,
  installed_bytes: 300_000_000,
  sources: ['GitHub', 'the Python Package Index'],
};
const JOB = { id: 'job_1', status: 'running' } as unknown as Job;

function chapter(
  state: FilmChapter['state'],
  start: number | null = null,
  problems = 0,
): FilmChapter {
  return { title: 'A chapter', state, problems, start };
}

function film(patch: Partial<Film> = {}): Film {
  return {
    id: `flm_${'1'.repeat(20)}`,
    status: 'ready',
    title: 'Area and volume',
    chapters: [chapter('written', 8), chapter('in_words', 60)],
    voice: null,
    seconds: 120,
    size: 4000,
    notes: [],
    written_by: {},
    reason: null,
    created_at: null,
    finished_at: null,
    making: null,
    ...patch,
  };
}

function view(patch: Partial<CourseFilm> = {}): CourseFilm {
  return {
    plan: {
      chapters: ['Area', 'Volume'],
      requests_at_most: 8,
      voice: null,
      blocked: null,
      checks_pictures: false,
    },
    film: null,
    ...patch,
  };
}

describe('where a course’s film stands', () => {
  it('follows the film first, then the film maker, then what stands in the way', () => {
    expect(filmStage(view({ film: film() }), MAKER).kind).toBe('ready');
    expect(filmStage(view({ film: film({ status: 'making', making: JOB }) }), MAKER).kind).toBe(
      'making',
    );
    expect(filmStage(view({ film: film({ status: 'unfinished' }) }), MAKER).kind).toBe(
      'unfinished',
    );
    expect(filmStage(view(), { ...MAKER, ready: false }).kind).toBe('set-up');
    expect(filmStage(view(), { ...MAKER, ready: false, setting_up: JOB }).kind).toBe('setting-up');
    expect(filmStage(view(), { ...MAKER, ready: false, fits: false })).toEqual({
      kind: 'unavailable',
      why: 'The film maker doesn’t run on this kind of computer.',
    });
    const blocked = view({ plan: { ...view().plan, blocked: 'Add concepts first.' } });
    expect(filmStage(blocked, MAKER)).toEqual({ kind: 'blocked', why: 'Add concepts first.' });
    expect(filmStage(view(), MAKER).kind).toBe('ready-to-make');
  });

  it('shows a made film even after the film maker is taken away', () => {
    expect(filmStage(view({ film: film() }), { ...MAKER, ready: false }).kind).toBe('ready');
  });
});

describe('a film’s chapters', () => {
  it('says how each stands, and which is being written', () => {
    expect(chapterState(chapter('written'))).toBe('Written and checked');
    expect(chapterState(chapter('written', null, 2))).toBe('Written, with a little overlap');
    expect(chapterState(chapter('in_words'))).toBe('Told in words');
    // Several at once, where the provider takes several requests at once (ADR-068).
    expect(chapterState(chapter('writing'))).toBe('Being written');
    expect(chapterState(chapter('waiting'))).toBe('Waiting');
  });

  it('knows which chapter a moment is in', () => {
    const chapters = [chapter('written', 8), chapter('written', 60)];
    expect(chapterAt(chapters, 2)).toBe(-1);
    expect(chapterAt(chapters, 8)).toBe(0);
    expect(chapterAt(chapters, 59.9)).toBe(0);
    expect(chapterAt(chapters, 61)).toBe(1);
  });
});

describe('sizes', () => {
  it('are said in megabytes under a gigabyte, to the nearest ten', () => {
    expect(aboutBytes(109_523_022)).toBe('about 110 MB');
    expect(aboutBytes(300_000_000)).toBe('about 300 MB');
    expect(aboutBytes(2_000)).toBe('about 10 MB');
    expect(aboutBytes(1_450_000_000)).toBe('about 1.5 GB');
    expect(aboutBytes(12_400_000_000)).toBe('about 12 GB');
  });
});

describe('times and lengths', () => {
  it('are said as a player shows them, and plainly', () => {
    expect(clockOf(5)).toBe('0:05');
    expect(clockOf(221)).toBe('3:41');
    expect(clockOf(3729)).toBe('1:02:09');
    expect(lengthOf(30)).toBe('1 minute');
    expect(lengthOf(720)).toBe('12 minutes');
    expect(lengthOf(3840)).toBe('1 hour 4 minutes');
    expect(lengthOf(7200)).toBe('2 hours');
  });

  it('say what a film sends besides its words, and the most requests it may make', () => {
    expect(filmRequests(8, null)).toBe(
      'At most 8 requests: one for each chapter, and up to three more for each to fix it.',
    );
    expect(filmRequests(10, 'NVIDIA NIM')).toBe(
      'Sends pictures of each chapter to NVIDIA NIM to be checked. At most 10 requests: one ' +
        'for each chapter, up to three more for each to fix it, and one for each to check its ' +
        'pictures.',
    );
  });

  it('say how long making a film takes as at least that, never more exactly than known', () => {
    expect(makingTakes(2, 420)).toBe('at least 20 minutes');
    expect(makingTakes(1, 10)).toBe('at least 5 minutes');
    expect(makingTakes(12, 420)).toBe('2 hours or more');
    expect(makingTakes(6, 420)).toBe('about an hour or more');
  });
});

describe('a film’s words', () => {
  const cues = [
    { start: 0, end: 2.5, text: 'How much floor does a rug cover?' },
    { start: 2.5, end: 4, text: 'Let us count it.' },
    { start: 6, end: 7, text: 'Next.' },
  ];

  it('are found by the moment they are said', () => {
    expect(cueAt(cues, 1)?.text).toBe('How much floor does a rug cover?');
    expect(cueAt(cues, 2.5)?.text).toBe('Let us count it.');
    expect(cueAt(cues, 5)).toBeNull();
    expect(cueAt([], 1)).toBeNull();
  });

  it('become subtitles whose text cannot be read as markup or as timing', () => {
    const vtt = vttOf([
      ...cues,
      { start: 8, end: 9, text: '<b>bold</b> & 00:00:01.000 --> 00:00:02.000' },
      { start: 9, end: 9, text: 'never shown' },
    ]);
    expect(vtt.startsWith('WEBVTT\n')).toBe(true);
    expect(vtt).toContain('00:00:00.000 --> 00:00:02.500\nHow much floor does a rug cover?');
    expect(vtt).toContain('&lt;b&gt;bold&lt;/b&gt; &amp; 00:00:01.000 --&gt; 00:00:02.000');
    expect(vtt).not.toContain('never shown');
  });
});
