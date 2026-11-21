import { describe, expect, it } from 'vitest';

import { EXTERNAL_LINKS } from './ipc';

describe('EXTERNAL_LINKS', () => {
  it('holds only secure addresses with nothing in them that could carry anything along', () => {
    for (const [id, link] of Object.entries(EXTERNAL_LINKS)) {
      const url = new URL(link);
      expect(url.protocol, id).toBe('https:');
      expect(url.username + url.password, id).toBe('');
      // A fixed page: no query and no fragment for anything of the learner's to ride in.
      expect(url.search + url.hash, id).toBe('');
    }
  });

  it('knows where Adle’s source and its licence are', () => {
    // What the GNU GPL asks an app to tell whoever uses it (ADR-033).
    expect(EXTERNAL_LINKS.source).toBe('https://github.com/XelXen/Adle');
    expect(EXTERNAL_LINKS.licence).toBe('https://www.gnu.org/licenses/gpl-3.0.html');
  });
});
