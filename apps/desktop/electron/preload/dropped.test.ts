/**
 * What the preload makes of "the files that were dropped", which is a value from the page.
 * The journey through the real bridge is in `e2e/security.spec.ts`.
 */
import { describe, expect, it, vi } from 'vitest';

import { droppedPaths } from './dropped';

const real = (name: string): File => new File(['x'], name);

describe('droppedPaths', () => {
  it('asks the browser for the path of each real file, and keeps the ones that have one', () => {
    const notes = real('notes.txt');
    const made = real('made-by-script.txt');
    const pathOf = vi.fn((file: File) => (file === notes ? 'C:\\Users\\me\\notes.txt' : ''));
    expect(droppedPaths([notes, made], pathOf)).toEqual(['C:\\Users\\me\\notes.txt']);
    expect(pathOf).toHaveBeenCalledTimes(2);
  });

  it('never calls a method of what the page handed over', () => {
    // What a compromised page would pass: something list-like whose methods are its own.
    const map = vi.fn(() => ['C:\\Users\\me\\Documents\\tax.pdf']);
    const filter = vi.fn(() => ['C:\\Users\\me\\Documents\\tax.pdf']);
    const forged = { length: 1, 0: 'C:\\Users\\me\\Documents\\tax.pdf', map, filter };
    const pathOf = vi.fn(() => 'C:\\anything');

    expect(droppedPaths(forged, pathOf)).toEqual([]);
    expect(map).not.toHaveBeenCalled();
    expect(filter).not.toHaveBeenCalled();
    expect(pathOf).not.toHaveBeenCalled();
  });

  it('takes no path that is merely written down', () => {
    const pathOf = vi.fn(() => 'C:\\anything');
    const entries = ['C:\\Windows\\win.ini', { path: '/etc/passwd' }, null, 7, ['x']];
    expect(droppedPaths(entries, pathOf)).toEqual([]);
    expect(pathOf).not.toHaveBeenCalled();
  });

  it('is not put off by a browser that refuses, or answers with something else', () => {
    const first = real('a.txt');
    const second = real('b.txt');
    const third = real('c.txt');
    const pathOf = (file: File): string => {
      if (file === first) throw new Error('not a file from disk');
      if (file === second) return 42 as unknown as string;
      return '/home/me/c.txt';
    };
    expect(droppedPaths([first, second, third], pathOf)).toEqual(['/home/me/c.txt']);
  });

  it('looks at no more files than one more than can be imported at once', () => {
    const pathOf = vi.fn((file: File) => `/home/me/${file.name}`);
    const many = Array.from({ length: 500 }, (_unused, index) => real(`${index}.txt`));
    expect(droppedPaths(many, pathOf)).toHaveLength(51);
    expect(pathOf).toHaveBeenCalledTimes(51);
  });

  it.each([undefined, null, 'C:\\file.txt', 3, {}])('takes %j for no files at all', (value) => {
    expect(droppedPaths(value, () => 'C:\\anything')).toEqual([]);
  });
});
