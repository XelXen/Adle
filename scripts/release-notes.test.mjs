import { describe, expect, it } from 'vitest';

import { isAlpha, notes, opening } from './release-notes.mjs';

const CHANGELOG = `# Changelog

## [Unreleased]

## [0.2.0] - 2026-11-25

The first version that is not an alpha.

### Added

- Something.

## [0.1.0-alpha.10] - 2026-11-25

The tenth alpha.

### Added
`;

describe('what a release says about itself (ADR-043)', () => {
  it('opens with the lines under its version in the changelog, before its first list', () => {
    expect(opening(CHANGELOG, '0.2.0')).toBe('The first version that is not an alpha.');
    expect(opening(CHANGELOG, '0.1.0-alpha.10')).toBe('The tenth alpha.');
    expect(opening(CHANGELOG, '0.3.0')).toBeNull();
  });

  it('calls an alpha an alpha, and a version nothing of the kind', () => {
    expect(isAlpha('0.2.0-alpha.1')).toBe(true);
    expect(isAlpha('0.2.0')).toBe(false);
    const alpha = notes('0.2.0-alpha.1', 'An alpha.');
    expect(alpha).toContain('This is an alpha:');
    const stable = notes('0.2.0', 'A version.');
    expect(stable).not.toMatch(/alpha/i);
    expect(stable).toContain(
      'If something breaks,\n[tell us](https://github.com/XelXen/Adle/issues).',
    );
    // Every file it names is this version's.
    expect(stable).toContain('`Adle-0.2.0-windows-x64-setup.exe`');
    expect(stable).toContain('/blob/v0.2.0/CHANGELOG.md');
  });
});
