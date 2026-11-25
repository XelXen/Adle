import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '@adle/design-system';

import type { AdleBridge, SettingsFileFound } from '../../lib/bridge';
import { ImportSettingsDialog, SaveSettingsDialog } from './SettingsFileDialogs';

/**
 * The two dialogs about settings as a file (ADR-064), against a stand-in for the bridge.
 * What they send is the whole of what the page can say: which parts, a password, and
 * whether to set a voice up. A key never comes to the page, and neither does a place.
 */

const ALL = { appearance: true, learning: true, voice: true, provider: true, keys: true };
const PASSWORD = 'correct horse battery';

const FOUND: SettingsFileFound = {
  token: 'b'.repeat(32),
  fileName: 'Adle settings 2026-11-24.json',
  parts: ALL,
  keysFor: ['aihubmix', 'nvidia'],
  voice: null,
};

const NAMES: Record<string, string> = { aihubmix: 'AIHubMix', nvidia: 'NVIDIA NIM' };
const nameOf = (id: string): string => NAMES[id] ?? id;

const settings = {
  saveFile: vi.fn<AdleBridge['settings']['saveFile']>(),
  chooseFile: vi.fn<AdleBridge['settings']['chooseFile']>(),
  bringIn: vi.fn<AdleBridge['settings']['bringIn']>(),
};

beforeEach(() => {
  settings.saveFile.mockReset();
  settings.bringIn.mockReset();
  window.adle = { settings } as unknown as AdleBridge;
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

function type(label: string | RegExp, value: string): void {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
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

describe('saving settings to a file', () => {
  const show = (): ReturnType<typeof vi.fn> => {
    const onClose = vi.fn();
    render(
      <ToastProvider>
        <SaveSettingsDialog onClose={onClose} />
      </ToastProvider>,
    );
    return onClose;
  };

  it('saves everything, the keys locked with a password typed twice', async () => {
    settings.saveFile.mockResolvedValue({
      ok: true,
      data: { fileName: 'Adle settings 2026-11-24.json', parts: ALL, keys: 2 },
    });
    const onClose = show();
    expect(screen.getByRole('checkbox', { name: 'Include my API keys' })).toBeChecked();
    type('Password for the keys', PASSWORD);
    type('The password again', PASSWORD);
    await press('Save…');
    expect(settings.saveFile).toHaveBeenCalledWith(ALL, PASSWORD);
    expect(toasts()).toContain('Settings saved');
    expect(toasts()).toContain('Adle settings 2026-11-24.json');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('asks nothing until the password is long enough and typed the same twice', async () => {
    show();
    type('Password for the keys', 'short');
    type('The password again', 'short');
    await press('Save…');
    expect(screen.getByText('Use 8 characters or more.')).toBeVisible();
    expect(settings.saveFile).not.toHaveBeenCalled();
    type('Password for the keys', PASSWORD);
    type('The password again', `${PASSWORD}?`);
    await press('Save…');
    expect(screen.getByText('The two passwords are different.')).toBeVisible();
    expect(settings.saveFile).not.toHaveBeenCalled();
  });

  it('saves without the keys, and then asks for no password and sends none', async () => {
    settings.saveFile.mockResolvedValue({
      ok: true,
      data: { fileName: 'settings.json', parts: { ...ALL, keys: false }, keys: 0 },
    });
    show();
    check('Include my API keys', false);
    expect(screen.queryByLabelText('Password for the keys')).toBeNull();
    fireEvent.click(screen.getByText('Advanced'));
    check('Voice', false);
    await press('Save…');
    expect(settings.saveFile).toHaveBeenCalledWith(
      { appearance: true, learning: true, voice: false, provider: true, keys: false },
      null,
    );
  });

  it('says so when there were no keys on this computer to put in', async () => {
    settings.saveFile.mockResolvedValue({
      ok: true,
      data: { fileName: 'settings.json', parts: { ...ALL, keys: false }, keys: 0 },
    });
    show();
    type('Password for the keys', PASSWORD);
    type('The password again', PASSWORD);
    await press('Save…');
    expect(toasts()).toContain('There are no keys on this computer, so it has none.');
  });

  it('stays as it is when the learner backs out, and says why a save failed', async () => {
    settings.saveFile.mockResolvedValueOnce({ ok: true, data: null });
    const onClose = show();
    check('Include my API keys', false);
    await press('Save…');
    expect(onClose).not.toHaveBeenCalled();
    settings.saveFile.mockResolvedValueOnce({
      ok: false,
      error: { code: 'not_saved', message: 'Couldn’t save the file there.', status: 0 },
    });
    await press('Save…');
    expect(screen.getByText('Couldn’t save your settings')).toBeVisible();
    expect(screen.getByText('Couldn’t save the file there.')).toBeVisible();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('has nothing to save when nothing is chosen', () => {
    show();
    check('Include my API keys', false);
    fireEvent.click(screen.getByText('Advanced'));
    for (const name of ['Appearance', 'Learning', 'Voice', 'AI provider']) check(name, false);
    expect(screen.getByRole('button', { name: 'Save…' })).toBeDisabled();
  });
});

describe('bringing settings in from a file', () => {
  const show = (
    found = FOUND,
  ): { onClose: ReturnType<typeof vi.fn>; onDone: ReturnType<typeof vi.fn> } => {
    const onClose = vi.fn();
    const onDone = vi.fn();
    render(
      <ToastProvider>
        <ImportSettingsDialog found={found} nameOf={nameOf} onClose={onClose} onDone={onDone} />
      </ToastProvider>,
    );
    return { onClose, onDone };
  };

  it('says what the file holds and whose keys, and asks for their password', async () => {
    settings.bringIn.mockResolvedValue({
      ok: true,
      data: { parts: ALL, keys: 2, notes: [], settingUpVoice: false },
    });
    const { onDone } = show();
    const dialog = screen.getByRole('dialog', { name: 'Import these settings?' });
    expect(
      within(dialog).getByText(
        'Adle settings 2026-11-24.json holds appearance, learning, voice, AI provider and API keys. Keys for AIHubMix and NVIDIA NIM. They replace yours.',
      ),
    ).toBeVisible();
    type('Password for the keys', PASSWORD);
    await press('Import');
    expect(settings.bringIn).toHaveBeenCalledWith(FOUND.token, ALL, {
      password: PASSWORD,
      setUpVoice: false,
    });
    // What happened is read first; the app begins again when the learner says so.
    const done = screen.getByRole('dialog', { name: 'Settings imported' });
    expect(
      within(done).getByText('Brought in: appearance, learning, voice, AI provider and API keys.'),
    ).toBeVisible();
    expect(onDone).not.toHaveBeenCalled();
    await press('Done');
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('says a wrong password under its field, changes nothing, and can be tried again', async () => {
    settings.bringIn.mockResolvedValueOnce({
      ok: false,
      error: {
        code: 'wrong_password',
        message: 'That password doesn’t open the keys in this file.',
        status: 0,
      },
    });
    show();
    await press('Import');
    expect(screen.getByText('Type the password the keys were locked with.')).toBeVisible();
    expect(settings.bringIn).not.toHaveBeenCalled();
    type('Password for the keys', 'not the password');
    await press('Import');
    expect(screen.getByText('That password doesn’t open the keys in this file.')).toBeVisible();
    expect(screen.queryByRole('dialog', { name: 'Settings imported' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Import' })).toBeEnabled();
  });

  it('brings in the rest without the keys when the learner leaves them out', async () => {
    settings.bringIn.mockResolvedValue({
      ok: true,
      data: { parts: { ...ALL, keys: false }, keys: 0, notes: [], settingUpVoice: false },
    });
    show();
    fireEvent.click(screen.getByText('Advanced'));
    check('API keys', false);
    expect(screen.queryByLabelText('Password for the keys')).toBeNull();
    await press('Import');
    expect(settings.bringIn).toHaveBeenCalledWith(
      FOUND.token,
      { ...ALL, keys: false },
      { password: null, setUpVoice: false },
    );
  });

  it('says before anything changes what a voice that is not here would be, and what it downloads', async () => {
    settings.bringIn.mockResolvedValue({
      ok: true,
      data: {
        parts: { ...ALL, keys: false },
        keys: 0,
        notes: [
          'The Expressive voice can’t run on this computer, so the Natural voice is used.',
          'The Natural voice is being set up. Lessons are read in it once it is ready.',
        ],
        settingUpVoice: true,
      },
    });
    show({
      ...FOUND,
      parts: { ...ALL, keys: false },
      keysFor: [],
      voice: {
        name: 'Natural',
        setUp: true,
        downloadBytes: 561_000_000,
        sources: ['Hugging Face', 'the Python Package Index', 'GitHub'],
        note: 'The Expressive voice can’t run on this computer, so the Natural voice is used.',
      },
    });
    expect(
      screen.getByText(
        'The Expressive voice can’t run on this computer, so the Natural voice is used.',
      ),
    ).toBeVisible();
    const setUp = screen.getByRole('checkbox', { name: 'Set up the Natural voice' });
    expect(setUp).toBeChecked();
    expect(
      screen.getByText(
        'Downloads about 0.6 GB from Hugging Face, the Python Package Index and GitHub.',
      ),
    ).toBeVisible();
    await press('Import');
    expect(settings.bringIn).toHaveBeenCalledWith(
      FOUND.token,
      { ...ALL, keys: false },
      { password: null, setUpVoice: true },
    );
    const notes = within(screen.getByRole('list', { name: 'What is different here' }));
    expect(notes.getAllByRole('listitem')).toHaveLength(2);
  });

  it('downloads nothing when the learner unticks setting the voice up, or leaves the voice out', async () => {
    settings.bringIn.mockResolvedValue({
      ok: true,
      data: { parts: ALL, keys: 0, notes: [], settingUpVoice: false },
    });
    const found: SettingsFileFound = {
      ...FOUND,
      parts: { ...ALL, keys: false },
      keysFor: [],
      voice: { name: 'Natural', setUp: true, downloadBytes: 561_000_000, sources: [], note: '' },
    };
    show(found);
    check('Set up the Natural voice', false);
    await press('Import');
    expect(settings.bringIn).toHaveBeenLastCalledWith(
      found.token,
      { ...ALL, keys: false },
      { password: null, setUpVoice: false },
    );
  });

  it('offers no keys when the file has none for a provider offered here', () => {
    show({ ...FOUND, keysFor: [] });
    expect(screen.queryByLabelText('Password for the keys')).toBeNull();
    fireEvent.click(screen.getByText('Advanced'));
    expect(screen.queryByRole('checkbox', { name: 'API keys' })).toBeNull();
    expect(screen.getByRole('checkbox', { name: 'Appearance' })).toBeChecked();
  });

  it('says why settings could not be brought in', async () => {
    settings.bringIn.mockResolvedValue({
      ok: false,
      error: { code: 'file_not_chosen', message: 'Choose the file again.', status: 0 },
    });
    show({ ...FOUND, parts: { ...ALL, keys: false }, keysFor: [] });
    await press('Import');
    expect(screen.getByText('Couldn’t import the settings')).toBeVisible();
    expect(screen.getByText('Choose the file again.')).toBeVisible();
  });
});
