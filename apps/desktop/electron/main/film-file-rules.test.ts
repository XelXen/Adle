import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { filmHandedOverPath, parseFilmId, parseFilmSavePath } from './film-file-rules';

const root = path.resolve(path.sep, 'adle-test');
const dataDir = path.join(root, 'data');

describe('which film the page may ask to save', () => {
  it('is a film id as the core gives them out, and nothing else', () => {
    expect(parseFilmId('flm_0123456789abcdef0123')).toBe('flm_0123456789abcdef0123');
    for (const value of [
      'crs_0123456789abcdef0123',
      'flm_0123456789abcdef012',
      'flm_0123456789abcdef0123/..',
      '../flm_0123456789abcdef0123',
      'C:\\films\\a.mp4',
      42,
      null,
      { id: 'flm_0123456789abcdef0123' },
    ]) {
      expect(parseFilmId(value)).toBeNull();
    }
  });
});

describe('where the core left a film to be moved', () => {
  it('is a name of the kind the core makes, in its own folder', () => {
    expect(filmHandedOverPath(dataDir, 'film-0123456789abcdef0123.mp4', 'mp4')).toBe(
      path.join(dataDir, 'handover', 'film-0123456789abcdef0123.mp4'),
    );
    expect(filmHandedOverPath(dataDir, 'film-0123456789abcdef0123.srt', 'srt')).toBe(
      path.join(dataDir, 'handover', 'film-0123456789abcdef0123.srt'),
    );
  });

  it('is refused for any other name, or a name of the other kind', () => {
    for (const name of [
      'film-0123456789abcdef0123.srt',
      '../film-0123456789abcdef0123.mp4',
      'course-0123456789abcdef0123.zip',
      'film-0123456789abcdef0123.mp4.exe',
      'FILM-0123456789ABCDEF0123.MP4',
      null,
    ]) {
      expect(filmHandedOverPath(dataDir, name, 'mp4')).toBeNull();
    }
  });
});

describe('where the learner chose to save a film', () => {
  it('ends in .mp4, and its subtitles go beside it under its name', () => {
    const chosen = path.join(root, 'films', 'Area.mp4');
    expect(parseFilmSavePath(chosen, dataDir)).toEqual({
      ok: true,
      path: chosen,
      captions: path.join(root, 'films', 'Area.srt'),
      amended: false,
    });
    expect(parseFilmSavePath(path.join(root, 'films', 'Area'), dataDir)).toEqual({
      ok: true,
      path: path.join(root, 'films', 'Area.mp4'),
      captions: path.join(root, 'films', 'Area.srt'),
      amended: true,
    });
  });

  it('is never inside Adle’s own data, and is a whole path', () => {
    expect(parseFilmSavePath(path.join(dataDir, 'films', 'x.mp4'), dataDir).ok).toBe(false);
    expect(parseFilmSavePath('films/x.mp4', dataDir).ok).toBe(false);
    expect(parseFilmSavePath('', dataDir).ok).toBe(false);
    expect(parseFilmSavePath(`${root}${path.sep}a\0.mp4`, dataDir).ok).toBe(false);
    expect(parseFilmSavePath(42, dataDir).ok).toBe(false);
  });
});
