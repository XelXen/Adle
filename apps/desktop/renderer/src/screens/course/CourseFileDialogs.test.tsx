import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Course } from '@adle/contracts';
import { ToastProvider } from '@adle/design-system';

import type { AdleBridge, CourseFileFound } from '../../lib/bridge';
import { ImportCourseDialog } from '../home/ImportCourseDialog';
import { SaveCourseDialog } from './SaveCourseDialog';

/**
 * The two dialogs about a course as a file (ADR-063), against a stand-in for the bridge.
 * What they send is the whole of what the page can say: a kind, and four choices. Where a
 * file goes, and which file is opened, is never theirs to say.
 */

const COURSE = {
  id: `crs_${'1'.repeat(20)}`,
  title: 'Limits',
  origin: 'topic',
  brought_in: false,
} as unknown as Course;

const FOUND: CourseFileFound = {
  token: 'a'.repeat(32),
  fileName: 'Limits.adle-course.zip',
  title: 'Limits',
  kind: 'transfer',
  counts: { concepts: 8, lessons: 5, materials: 2, files: 2, progress: true, notes: 3 },
};

const courses = {
  saveFile: vi.fn<AdleBridge['courses']['saveFile']>(),
  chooseFile: vi.fn<AdleBridge['courses']['chooseFile']>(),
  bringIn: vi.fn<AdleBridge['courses']['bringIn']>(),
};

beforeEach(() => {
  courses.saveFile.mockReset();
  courses.bringIn.mockReset();
  window.adle = { courses } as unknown as AdleBridge;
});

afterEach(() => {
  delete window.adle;
});

async function press(name: string | RegExp): Promise<void> {
  await act(async () => {
    screen.getByRole('button', { name }).click();
    await Promise.resolve();
  });
}

function check(name: string | RegExp, checked: boolean): void {
  const box = screen.getByRole('checkbox', { name });
  if ((box as HTMLInputElement).checked !== checked) fireEvent.click(box);
}

function toasts(): string {
  return screen
    .getAllByRole('status')
    .map((item) => item.textContent)
    .join(' | ');
}

describe('saving a course as a file', () => {
  const show = (onClose = vi.fn()): ReturnType<typeof vi.fn> => {
    render(
      <ToastProvider>
        <SaveCourseDialog course={COURSE} onClose={onClose} />
      </ToastProvider>,
    );
    return onClose;
  };

  it('is a template unless the learner says otherwise: nothing about them', async () => {
    courses.saveFile.mockResolvedValue({
      ok: true,
      data: {
        fileName: 'Limits.adle-course.zip',
        counts: { ...FOUND.counts, progress: false, notes: 0, materials: 0, files: 0 },
        lessonsLeftOut: 0,
      },
    });
    const onClose = show();
    expect(screen.getByRole('dialog', { name: 'Save “Limits” as a file' })).toBeVisible();
    expect(screen.getByRole('radio', { name: /A template/ })).toBeChecked();
    await press('Save…');
    expect(courses.saveFile).toHaveBeenCalledWith(COURSE.id, {
      kind: 'template',
      holds: { lessons: true, materials: false, progress: false, notes: false },
    });
    expect(toasts()).toContain('Course saved');
    expect(toasts()).toContain('Limits.adle-course.zip');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('holds everything to move a course, and what it holds can be changed', async () => {
    courses.saveFile.mockResolvedValue({
      ok: true,
      data: { fileName: 'Limits.zip', counts: FOUND.counts, lessonsLeftOut: 2 },
    });
    show();
    fireEvent.click(screen.getByRole('radio', { name: /Everything/ }));
    // Under "Advanced", each thing a file can hold.
    const advanced = screen.getByText('Advanced').closest('details')!;
    expect(advanced).not.toHaveAttribute('open');
    expect(
      within(advanced)
        .getAllByRole('checkbox', { hidden: true })
        .map((box) => (box as HTMLInputElement).checked),
    ).toEqual([true, true, true, true]);
    fireEvent.click(screen.getByText('Advanced'));
    check('Notes', false);
    await press('Save…');
    expect(courses.saveFile).toHaveBeenCalledWith(COURSE.id, {
      kind: 'transfer',
      holds: { lessons: true, materials: true, progress: true, notes: false },
    });
    expect(toasts()).toContain('2 lessons are still being written and were left out.');
  });

  it('choosing a kind again sets what it holds back to what that kind holds', () => {
    show();
    fireEvent.click(screen.getByText('Advanced'));
    check('Progress', true);
    expect(screen.getByRole('checkbox', { name: 'Progress' })).toBeChecked();
    fireEvent.click(screen.getByRole('radio', { name: /Everything/ }));
    fireEvent.click(screen.getByRole('radio', { name: /A template/ }));
    expect(screen.getByRole('checkbox', { name: 'Progress' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Lessons' })).toBeChecked();
  });

  it('stays as it is when the learner backs out of the window that asks where', async () => {
    courses.saveFile.mockResolvedValue({ ok: true, data: null });
    const onClose = show();
    await press('Save…');
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.queryByText('Course saved')).toBeNull();
    expect(screen.getByRole('button', { name: 'Save…' })).toBeEnabled();
  });

  it('says why a file could not be saved, and can be tried again', async () => {
    courses.saveFile.mockResolvedValue({
      ok: false,
      error: { code: 'not_saved', message: 'Couldn’t save the file there.', status: 0 },
    });
    const onClose = show();
    await press('Save…');
    expect(screen.getByText('Couldn’t save the course')).toBeVisible();
    expect(screen.getByText('Couldn’t save the file there.')).toBeVisible();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Save…' })).toBeEnabled();
  });
});

describe('bringing a course in from a file', () => {
  const show = (
    found = FOUND,
  ): { onClose: ReturnType<typeof vi.fn>; onImported: ReturnType<typeof vi.fn> } => {
    const onClose = vi.fn();
    const onImported = vi.fn();
    render(
      <ToastProvider>
        <ImportCourseDialog found={found} onClose={onClose} onImported={onImported} />
      </ToastProvider>,
    );
    return { onClose, onImported };
  };

  it('says what the file holds, and brings in all of it unless told otherwise', async () => {
    courses.bringIn.mockResolvedValue({
      ok: true,
      data: {
        courseId: `crs_${'2'.repeat(20)}`,
        title: 'Limits',
        concepts: 8,
        lessons: 5,
        lessonsLeftOut: 0,
        materials: 2,
        progress: true,
        notes: 3,
      },
    });
    const { onImported } = show();
    const dialog = screen.getByRole('dialog', { name: 'Import “Limits”?' });
    expect(
      within(dialog).getByText(
        'Limits.adle-course.zip holds 8 concepts, 5 lessons, 2 sources, progress and 3 notes. It becomes a new course.',
      ),
    ).toBeVisible();
    await press('Import');
    expect(courses.bringIn).toHaveBeenCalledWith(FOUND.token, {
      lessons: true,
      materials: true,
      progress: true,
      notes: true,
    });
    expect(toasts()).toContain('Course imported');
    expect(onImported).toHaveBeenCalledWith(`crs_${'2'.repeat(20)}`);
  });

  it('leaves out what the learner unticks under "Advanced"', async () => {
    courses.bringIn.mockResolvedValue({
      ok: true,
      data: {
        courseId: `crs_${'2'.repeat(20)}`,
        title: 'Limits',
        concepts: 8,
        lessons: 4,
        lessonsLeftOut: 1,
        materials: 0,
        progress: false,
        notes: 3,
      },
    });
    show();
    fireEvent.click(screen.getByText('Advanced'));
    check('Progress', false);
    check(/^Materials/, false);
    await press('Import');
    expect(courses.bringIn).toHaveBeenCalledWith(FOUND.token, {
      lessons: true,
      materials: false,
      progress: false,
      notes: true,
    });
    expect(toasts()).toContain('1 lesson couldn’t be used and was left out.');
  });

  it('offers only what the file has', () => {
    show({
      ...FOUND,
      kind: 'template',
      counts: { concepts: 3, lessons: 2, materials: 0, files: 0, progress: false, notes: 0 },
    });
    fireEvent.click(screen.getByText('Advanced'));
    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    expect(screen.getByRole('checkbox', { name: 'Lessons (2)' })).toBeChecked();
    expect(screen.queryByRole('checkbox', { name: 'Progress' })).toBeNull();
  });

  it('has nothing to choose for a file that holds only a plan', () => {
    show({
      ...FOUND,
      counts: { concepts: 3, lessons: 0, materials: 0, files: 0, progress: false, notes: 0 },
    });
    expect(screen.queryByText('Advanced')).toBeNull();
    expect(screen.getByRole('button', { name: 'Import' })).toBeEnabled();
  });

  it('says why a file could not be brought in, and makes nothing', async () => {
    courses.bringIn.mockResolvedValue({
      ok: false,
      error: {
        code: 'course_file_invalid',
        message: 'This file isn’t an Adle course, or it is damaged. Nothing was imported.',
        status: 422,
      },
    });
    const { onImported, onClose } = show();
    await press('Import');
    expect(screen.getByText('Couldn’t import the course')).toBeVisible();
    expect(screen.getByText(/Nothing was imported/)).toBeVisible();
    expect(onImported).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });
});
