import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  Button,
  Callout,
  Checkbox,
  ChoiceButtons,
  ColorSwatches,
  Dialog,
  Disclosure,
  EmptyState,
  ErrorState,
  IconButton,
  InfoPopover,
  LoadingState,
  Logo,
  ProgressBar,
  RadioGroup,
  SegmentedControl,
  Select,
  Slider,
  Switch,
  Tabs,
  TextField,
  ToastProvider,
  useToast,
} from '../index';

afterEach(() => {
  vi.useRealTimers();
});

describe('Button', () => {
  it('is a plain button by default so it never submits a form by accident', () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'button');
  });

  it('ignores clicks while loading but stays focusable and announces busy', async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Save' });
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(button).not.toBeDisabled();
  });

  it('does not fire when disabled', async () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('gives an icon-only button an accessible name', () => {
    render(<IconButton label="Close" icon={<svg />} />);
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });
});

describe('TextField', () => {
  it('links its label, description, and error to the input', () => {
    render(
      <TextField
        label="API key"
        description="Stored encrypted."
        error="That key looks too short."
      />,
    );
    const input = screen.getByLabelText('API key');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('That key looks too short. Stored encrypted.');
    expect(screen.getByRole('alert')).toHaveTextContent('That key looks too short.');
  });

  it('is not marked invalid without an error', () => {
    render(<TextField label="Topic" />);
    expect(screen.getByLabelText('Topic')).not.toHaveAttribute('aria-invalid');
  });
});

describe('Select', () => {
  it('reports the chosen value', async () => {
    const onValueChange = vi.fn();
    render(
      <Select
        label="Pace"
        value="steady"
        options={[
          { value: 'steady', label: 'Steady' },
          { value: 'brisk', label: 'Brisk' },
        ]}
        onValueChange={onValueChange}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText('Pace'), 'brisk');
    expect(onValueChange).toHaveBeenCalledWith('brisk');
  });
});

describe('Disclosure', () => {
  it('keeps what is behind it out of the way until it is opened, by a press or the keyboard', async () => {
    const user = userEvent.setup();
    render(
      <Disclosure label="Advanced">
        <Checkbox label="Progress" checked onCheckedChange={() => undefined} />
      </Disclosure>,
    );
    const summary = screen.getByText('Advanced');
    const details = summary.closest('details');
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute('open');
    // It is the browser's own: what is inside is in the page either way.
    expect(screen.getByRole('checkbox', { name: 'Progress', hidden: true })).toBeChecked();
    await user.click(summary);
    expect(details).toHaveAttribute('open');
    await user.click(summary);
    expect(details).not.toHaveAttribute('open');
  });

  it('can begin open', () => {
    render(
      <Disclosure label="Advanced" defaultOpen>
        <p>Choices</p>
      </Disclosure>,
    );
    expect(screen.getByText('Advanced').closest('details')).toHaveAttribute('open');
  });
});

describe('InfoPopover', () => {
  it('is a named button that opens the note it points at', () => {
    render(
      <InfoPopover label="What is sent" icon={<span>i</span>} title="What is sent">
        <p>The course name and this concept.</p>
      </InfoPopover>,
    );
    const button = screen.getByRole('button', { name: 'What is sent' });
    const note = screen.getByText('The course name and this concept.').closest('[popover]');
    // The browser opens and closes it, and says so on the button: all this needs is
    // that the button points at the note and the note is one.
    expect(note).toHaveAttribute('popover', 'auto');
    expect(button).toHaveAttribute('popovertarget', note?.id);
    expect(note?.id).toBeTruthy();
  });
});

describe('Switch', () => {
  it('exposes its state and toggles from the keyboard', async () => {
    function Example() {
      const [on, setOn] = useState(false);
      return (
        <Switch
          label="Narration"
          description="Read lessons aloud."
          checked={on}
          onCheckedChange={setOn}
        />
      );
    }
    render(<Example />);
    const control = screen.getByRole('switch', { name: 'Narration' });
    expect(control).toHaveAttribute('aria-checked', 'false');
    expect(control).toHaveAccessibleDescription('Read lessons aloud.');
    control.focus();
    await userEvent.keyboard(' ');
    expect(control).toHaveAttribute('aria-checked', 'true');
  });
});

describe('Checkbox', () => {
  function Example({ disabled = false }: { disabled?: boolean }) {
    const [checked, setChecked] = useState(false);
    return (
      <Checkbox
        label="Chain rule"
        description="Needed for backpropagation."
        checked={checked}
        onCheckedChange={setChecked}
        disabled={disabled}
      />
    );
  }

  it('is a real checkbox with a name, a description, and keyboard support', async () => {
    render(<Example />);
    const box = screen.getByRole('checkbox', { name: 'Chain rule' });
    expect(box).not.toBeChecked();
    expect(box).toHaveAccessibleDescription('Needed for backpropagation.');
    box.focus();
    await userEvent.keyboard(' ');
    expect(box).toBeChecked();
    // Clicking the label works too.
    await userEvent.click(screen.getByText('Chain rule'));
    expect(box).not.toBeChecked();
  });

  it('cannot be changed while disabled', async () => {
    render(<Example disabled />);
    const box = screen.getByRole('checkbox', { name: 'Chain rule' });
    await userEvent.click(box);
    expect(box).toBeDisabled();
    expect(box).not.toBeChecked();
  });
});

describe('RadioGroup', () => {
  function Example({ disabled = false }: { disabled?: boolean }) {
    const [value, setValue] = useState<'a' | 'b' | 'c' | null>(null);
    return (
      <RadioGroup
        label="Which input matters more?"
        value={value}
        disabled={disabled}
        options={[
          { value: 'a', label: 'The first input' },
          { value: 'b', label: 'The second input', description: 'Its weight is 0.2.' },
          { value: 'c', label: 'Both the same' },
        ]}
        onValueChange={setValue}
      />
    );
  }

  it('is a named group of real radio buttons with nothing chosen at first', () => {
    render(<Example />);
    const group = screen.getByRole('group', { name: 'Which input matters more?' });
    expect(group).toBeInTheDocument();
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(3);
    for (const radio of radios) expect(radio).not.toBeChecked();
    expect(screen.getByRole('radio', { name: 'The second input' })).toHaveAccessibleDescription(
      'Its weight is 0.2.',
    );
  });

  it('chooses by click on the whole row and moves with the arrow keys', async () => {
    render(<Example />);
    await userEvent.click(screen.getByText('The first input'));
    expect(screen.getByRole('radio', { name: 'The first input' })).toBeChecked();
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('radio', { name: 'The second input' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'The first input' })).not.toBeChecked();
  });

  it('cannot be changed while disabled', async () => {
    render(<Example disabled />);
    await userEvent.click(screen.getByText('The first input'));
    expect(screen.getByRole('radio', { name: 'The first input' })).not.toBeChecked();
  });

  it('shows a settled choice that can be read but no longer changed', async () => {
    const onValueChange = vi.fn();
    render(
      <RadioGroup
        label="Which input matters more?"
        value="b"
        readOnly
        options={[
          { value: 'a', label: 'The first input', description: 'Correct answer' },
          { value: 'b', label: 'The second input', description: 'Your answer' },
        ]}
        onValueChange={onValueChange}
      />,
    );
    await userEvent.click(screen.getByText('The first input'));
    expect(onValueChange).not.toHaveBeenCalled();
    expect(screen.getByRole('radio', { name: 'The second input' })).toBeChecked();
    // What each option turned out to be is part of what is announced for it.
    expect(screen.getByRole('radio', { name: 'The first input' })).toHaveAccessibleDescription(
      'Correct answer',
    );
  });
});

describe('ChoiceButtons', () => {
  const options = [
    { value: 'auto', label: 'Automatic', description: 'Use each for what it is best at.' },
    { value: 'one', label: 'One only', description: 'Everything goes to one.' },
  ] as const;

  it('says which option is in force and changes nothing on the way past', async () => {
    const onValueChange = vi.fn();
    render(
      <ChoiceButtons
        label="Which provider"
        value="auto"
        options={options}
        onValueChange={onValueChange}
      />,
    );
    const group = screen.getByRole('group', { name: 'Which provider' });
    expect(group).toBeInTheDocument();
    const automatic = screen.getByRole('button', { name: /^Automatic/ });
    const one = screen.getByRole('button', { name: /^One only/ });
    expect(automatic).toHaveAttribute('aria-pressed', 'true');
    expect(one).toHaveAttribute('aria-pressed', 'false');
    // Named by everything it shows, title first: no words on screen that cannot be said.
    expect(one).toHaveAccessibleName('One only Everything goes to one.');

    // Arrow keys move nothing: only pressing an option chooses it.
    automatic.focus();
    await userEvent.keyboard('{ArrowDown}{ArrowUp}');
    expect(onValueChange).not.toHaveBeenCalled();
    // Pressing the one already in force is not a change.
    await userEvent.click(automatic);
    expect(onValueChange).not.toHaveBeenCalled();
    await userEvent.click(one);
    expect(onValueChange).toHaveBeenCalledExactlyOnceWith('one');
  });

  it('takes no second choice while the first is being put into force', async () => {
    const onValueChange = vi.fn();
    render(
      <ChoiceButtons
        label="Which provider"
        value="auto"
        pending="one"
        options={options}
        onValueChange={onValueChange}
      />,
    );
    const one = screen.getByRole('button', { name: /^One only/ });
    expect(one).toHaveAttribute('aria-busy', 'true');
    // Still focusable, so the keyboard does not lose its place.
    expect(one).not.toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: /^Automatic/ }));
    await userEvent.click(one);
    expect(onValueChange).not.toHaveBeenCalled();
  });
});

describe('SegmentedControl', () => {
  function Example() {
    const [value, setValue] = useState<'system' | 'light' | 'dark'>('system');
    return (
      <SegmentedControl
        label="Theme"
        value={value}
        onValueChange={setValue}
        options={[
          { value: 'system', label: 'System' },
          { value: 'light', label: 'Light' },
          { value: 'dark', label: 'Dark' },
        ]}
      />
    );
  }

  it('behaves as a radio group with arrow-key selection and a single tab stop', async () => {
    render(<Example />);
    const group = screen.getByRole('radiogroup', { name: 'Theme' });
    expect(group).toBeInTheDocument();
    const [system, light, dark] = screen.getAllByRole('radio');
    expect(system).toHaveAttribute('tabindex', '0');
    expect(light).toHaveAttribute('tabindex', '-1');

    system!.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(light).toHaveAttribute('aria-checked', 'true');
    expect(light).toHaveFocus();
    await userEvent.keyboard('{End}');
    expect(dark).toHaveAttribute('aria-checked', 'true');
    await userEvent.keyboard('{ArrowRight}');
    expect(system).toHaveAttribute('aria-checked', 'true');
  });
});

describe('ColorSwatches', () => {
  const SWATCHES = [
    { hue: 355, name: 'Pink' },
    { hue: 160, name: 'Mint' },
    { hue: 295, name: 'Lavender' },
  ];

  function Example({ start }: { start: number }) {
    const [hue, setHue] = useState(start);
    return <ColorSwatches label="Color" value={hue} swatches={SWATCHES} onValueChange={setHue} />;
  }

  it('is a radio group of named colors, each drawn in its own hue', async () => {
    render(<Example start={160} />);
    expect(screen.getByRole('radiogroup', { name: 'Color' })).toBeInTheDocument();
    const [pink, mint, lavender] = screen.getAllByRole('radio');
    expect(mint).toHaveAccessibleName('Mint');
    expect(mint).toHaveAttribute('aria-checked', 'true');
    expect(mint).toHaveAttribute('tabindex', '0');
    expect(pink).toHaveAttribute('tabindex', '-1');
    expect(lavender!.style.getPropertyValue('--ad-swatch-hue')).toBe('295');

    mint!.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(lavender).toHaveAttribute('aria-checked', 'true');
    expect(lavender).toHaveFocus();
    await userEvent.keyboard('{ArrowRight}');
    expect(pink).toHaveAttribute('aria-checked', 'true');
    await userEvent.click(mint!);
    expect(mint).toHaveAttribute('aria-checked', 'true');
  });

  it('chooses none for a hue between them, and is entered at its first', async () => {
    render(<Example start={200} />);
    const [pink, mint] = screen.getAllByRole('radio');
    for (const radio of screen.getAllByRole('radio')) {
      expect(radio).toHaveAttribute('aria-checked', 'false');
    }
    expect(pink).toHaveAttribute('tabindex', '0');
    pink!.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(pink).toHaveAttribute('aria-checked', 'true');
    await userEvent.keyboard('{ArrowRight}');
    expect(mint).toHaveAttribute('aria-checked', 'true');
  });
});

describe('Slider', () => {
  it('can show every hue along its track, for a color of Pastel', () => {
    render(
      <Slider
        label="Any color"
        value={120}
        min={0}
        max={359}
        step={1}
        track="spectrum"
        onValueChange={() => undefined}
        formatValue={() => 'Near sage'}
      />,
    );
    const input = screen.getByRole('slider', { name: 'Any color' });
    expect(input).toHaveAttribute('aria-valuetext', 'Near sage');
    expect(input.className).toMatch(/rangeSpectrum/);
  });

  it('shows its value as text and reports changes', () => {
    const onValueChange = vi.fn();
    render(
      <Slider
        label="Weight"
        value={0.5}
        min={-2}
        max={2}
        onValueChange={onValueChange}
        formatValue={(value) => value.toFixed(1)}
      />,
    );
    const input = screen.getByRole('slider', { name: 'Weight' });
    expect(input).toHaveAttribute('aria-valuetext', '0.5');
    expect(screen.getByText('0.5')).toBeInTheDocument();
    fireEvent.change(input, { target: { value: '1.5' } });
    expect(onValueChange).toHaveBeenCalledWith(1.5);
  });
});

describe('Tabs', () => {
  function Example() {
    const [tab, setTab] = useState<'a' | 'b' | 'c'>('a');
    return (
      <Tabs
        label="Sections"
        value={tab}
        onValueChange={setTab}
        tabs={[
          { value: 'a', label: 'First' },
          { value: 'b', label: 'Second' },
          { value: 'c', label: 'Third' },
        ]}
      >
        {(current) => <p>Panel {current}</p>}
      </Tabs>
    );
  }

  it('connects tabs to the panel and moves with the arrow keys', async () => {
    render(<Example />);
    const first = screen.getByRole('tab', { name: 'First' });
    expect(first).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName('First');
    expect(screen.getByText('Panel a')).toBeInTheDocument();

    first.focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Second' })).toHaveFocus();
    expect(screen.getByText('Panel b')).toBeInTheDocument();
    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Third' })).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: 'First' })).toHaveAttribute('aria-selected', 'true');
  });
});

describe('Dialog', () => {
  it('opens modally with a labelled title and closes through its controls', async () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Dialog
        open={false}
        onClose={onClose}
        title="Remove the saved key?"
        description="This cannot be undone."
      />,
    );
    const dialog = screen.getByRole('dialog', { hidden: true });
    expect(dialog).not.toHaveAttribute('open');

    rerender(
      <Dialog
        open
        onClose={onClose}
        title="Remove the saved key?"
        description="This cannot be undone."
      />,
    );
    expect(dialog).toHaveAttribute('open');
    expect(dialog).toHaveAccessibleName('Remove the saved key?');
    expect(dialog).toHaveAccessibleDescription('This cannot be undone.');

    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('starts in the field a form marks, instead of on the close button', () => {
    render(
      <Dialog open onClose={() => undefined} title="Add a concept">
        <TextField label="Name" data-autofocus />
        <TextField label="Summary" />
      </Dialog>,
    );
    expect(screen.getByLabelText('Name')).toHaveFocus();
  });

  it('cannot be dismissed while an operation must finish', () => {
    const onClose = vi.fn();
    render(<Dialog open onClose={onClose} title="Restoring…" dismissible={false} />);
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument();
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('is dismissed by a press on the backdrop, not by a drag that ends there', () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Ask about this part">
        <TextField label="Your question" />
      </Dialog>,
    );
    const dialog = screen.getByRole('dialog');
    const field = screen.getByLabelText('Your question');

    // Selecting what was typed and letting go outside the dialog: the click that follows
    // lands on the backdrop, but it did not begin there.
    fireEvent.pointerDown(field);
    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();

    // A click inside changes nothing either.
    fireEvent.pointerDown(field);
    fireEvent.click(field);
    expect(onClose).not.toHaveBeenCalled();

    // Pressed and released on the backdrop: that is asking for it to go.
    fireEvent.pointerDown(dialog);
    fireEvent.click(dialog);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('gives the focus back to what had it, also when it is taken off the page while open', () => {
    function Asking() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button onClick={() => setOpen(true)}>Ask a question</button>
          {/* Mounted only while open, as a dialog with a form in it is. */}
          {open ? (
            <Dialog open onClose={() => setOpen(false)} title="Ask about this part">
              <button onClick={() => setOpen(false)}>Done</button>
            </Dialog>
          ) : null}
        </>
      );
    }
    render(<Asking />);
    const opener = screen.getByRole('button', { name: 'Ask a question' });
    opener.focus();
    fireEvent.click(opener);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    // Wherever the focus went inside, it is nowhere once the dialog has gone.
    (document.activeElement as HTMLElement | null)?.blur();

    fireEvent.click(screen.getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});

describe('Toast', () => {
  function Trigger({ tone }: { tone: 'success' | 'danger' }) {
    const toast = useToast();
    return (
      <button onClick={() => toast.show({ tone, title: 'Key saved', description: 'Encrypted.' })}>
        go
      </button>
    );
  }

  it('announces a confirmation and dismisses it automatically', () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger tone="success" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText('go'));
    expect(screen.getByRole('status')).toHaveTextContent('Key saved');
    act(() => {
      vi.advanceTimersByTime(5100);
    });
    expect(screen.queryByText('Key saved')).not.toBeInTheDocument();
  });

  it('keeps an error on screen until it is dismissed', () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger tone="danger" />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByText('go'));
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole('alert')).toHaveTextContent('Key saved');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('Logo', () => {
  it('is one image named for the product, with the wordmark as decoration', () => {
    const { container } = render(<Logo />);
    // The name is announced once: by the mark, not again by the word beside it.
    expect(screen.getByRole('img', { name: 'Adle' })).toBeInTheDocument();
    expect(screen.getByText('Adle')).toHaveAttribute('aria-hidden', 'true');
    // Two letters: the "a" as one shape, the "d" as a ring and a stem.
    expect(container.querySelectorAll('svg path, svg circle')).toHaveLength(3);
  });

  it('can be shown as the mark alone', () => {
    render(<Logo wordmark={false} size="large" />);
    expect(screen.getByRole('img', { name: 'Adle' })).toBeInTheDocument();
    expect(screen.queryByText('Adle')).not.toBeInTheDocument();
  });
});

describe('status components', () => {
  it('describes determinate and indeterminate progress', () => {
    const { rerender } = render(<ProgressBar label="Importing notes.pdf" value={0.4} />);
    const bar = screen.getByRole('progressbar', { name: 'Importing notes.pdf' });
    expect(bar).toHaveAttribute('aria-valuenow', '40');
    rerender(<ProgressBar label="Importing notes.pdf" />);
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow');
  });

  it('clamps out-of-range progress', () => {
    render(<ProgressBar label="Progress" value={7} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
  });

  it('uses the right live-region role for each kind of message', () => {
    render(
      <>
        <LoadingState title="Loading provider settings…" />
        <ErrorState title="Couldn’t load provider settings" description="Try again." />
        <EmptyState title="No courses yet" description="They will appear here." />
        <Callout tone="danger" urgent title="Import failed">
          The file is encrypted.
        </Callout>
      </>,
    );
    expect(screen.getByRole('status')).toHaveTextContent('Loading provider settings…');
    const alerts = screen.getAllByRole('alert');
    expect(alerts.map((alert) => alert.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining('Couldn’t load provider settings')]),
    );
    expect(screen.getByRole('heading', { name: 'No courses yet' })).toBeInTheDocument();
  });
});
