import { type CSSProperties, type KeyboardEvent, type ReactNode, useId, useRef } from 'react';

import { cx } from '../cx';
import styles from './Choice.module.css';

export interface SwitchProps {
  label: string;
  description?: ReactNode;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

/** An on/off setting that takes effect immediately. */
export function Switch({
  label,
  description,
  checked,
  onCheckedChange,
  disabled,
  className,
}: SwitchProps) {
  const id = useId();
  const descriptionId = description ? `${id}-description` : undefined;
  return (
    <div className={cx(styles.switchRow, className)}>
      <div className={styles.switchText}>
        <span id={`${id}-label`} className={styles.switchLabel}>
          {label}
        </span>
        {description ? (
          <span id={descriptionId} className={styles.switchDescription}>
            {description}
          </span>
        ) : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={`${id}-label`}
        aria-describedby={descriptionId}
        disabled={disabled}
        className={styles.switch}
        onClick={() => onCheckedChange(!checked)}
      >
        <span className={styles.thumb} />
      </button>
    </div>
  );
}

export interface CheckboxProps {
  label: ReactNode;
  description?: ReactNode;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * One of several independent choices that take effect when a form is submitted.
 * For a setting that applies the moment it is flipped, use `Switch`.
 */
export function Checkbox({
  label,
  description,
  checked,
  onCheckedChange,
  disabled,
  className,
}: CheckboxProps) {
  const id = useId();
  const descriptionId = description ? `${id}-description` : undefined;
  return (
    <div className={cx(styles.checkboxRow, className)}>
      <input
        id={id}
        type="checkbox"
        className={styles.checkbox}
        checked={checked}
        disabled={disabled}
        aria-describedby={descriptionId}
        onChange={(event) => onCheckedChange(event.target.checked)}
      />
      <div className={styles.checkboxText}>
        <label htmlFor={id} className={styles.checkboxLabel}>
          {label}
        </label>
        {description ? (
          <span id={descriptionId} className={styles.checkboxDescription}>
            {description}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export interface RadioOption<Value extends string> {
  value: Value;
  label: ReactNode;
  description?: ReactNode;
}

export interface RadioGroupProps<Value extends string> {
  /** The question the options answer. Rendered as the group's legend. */
  label: ReactNode;
  /** Keep the legend for assistive technology but do not show it. */
  hideLabel?: boolean;
  /** The chosen option, or null while nothing is chosen. */
  value: Value | null;
  options: readonly RadioOption<Value>[];
  onValueChange: (value: Value) => void;
  disabled?: boolean;
  /**
   * The choice has been made and is now only shown, as after a question has been
   * checked. It cannot be changed, and every option stays fully legible.
   */
  readOnly?: boolean;
  className?: string;
}

/**
 * One choice from a short list of options that may each be a sentence long,
 * confirmed afterwards with a button. Each option is a full-width row, so the
 * whole line is the target. For a few one-word options that apply at once, use
 * `SegmentedControl`.
 */
export function RadioGroup<Value extends string>({
  label,
  hideLabel = false,
  value,
  options,
  onValueChange,
  disabled = false,
  readOnly = false,
  className,
}: RadioGroupProps<Value>) {
  const name = useId();
  return (
    <fieldset
      className={cx(styles.radioGroup, readOnly && styles.radioGroupReadOnly, className)}
      disabled={disabled || readOnly}
    >
      <legend className={cx(styles.radioLegend, hideLabel && 'ad-visually-hidden')}>{label}</legend>
      {options.map((option) => {
        const id = `${name}-${option.value}`;
        const descriptionId = option.description ? `${id}-description` : undefined;
        return (
          <label
            key={option.value}
            htmlFor={id}
            className={cx(styles.radioRow, option.value === value && styles.radioRowSelected)}
          >
            <input
              id={id}
              type="radio"
              className={styles.radio}
              name={name}
              value={option.value}
              checked={option.value === value}
              // Named by the option's own text only; the description is announced after it.
              aria-labelledby={`${id}-label`}
              aria-describedby={descriptionId}
              onChange={() => onValueChange(option.value)}
            />
            <span className={styles.checkboxText}>
              <span id={`${id}-label`}>{option.label}</span>
              {option.description ? (
                <span id={descriptionId} className={styles.checkboxDescription}>
                  {option.description}
                </span>
              ) : null}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}

/**
 * A space between two pieces of text that are laid out apart from each other. It takes no
 * room (a flex container drops it), but it keeps the pieces from being read, by a
 * checker or a search, as one word run together.
 */
const SPACE = ' ';

export interface ChoiceButton<Value extends string> {
  value: Value;
  label: ReactNode;
  description?: ReactNode;
  /** A short label at the end of the title's line, such as "Recommended". */
  badge?: ReactNode;
}

export interface ChoiceButtonsProps<Value extends string> {
  /** Accessible name of the group. */
  label: string;
  /** The option in force, or null while none is. */
  value: Value | null;
  options: readonly ChoiceButton<Value>[];
  onValueChange: (value: Value) => void;
  /** The option being put into force at the moment, when that takes a while. */
  pending?: Value | null;
  disabled?: boolean;
  className?: string;
}

/**
 * One choice from a short list that takes effect, and is recorded, the moment it is
 * pressed. Each option is a button that says whether it is the one in force
 * (`aria-pressed`), so the arrow keys never change anything on their way past. For a
 * choice that is confirmed with a button afterwards, use `RadioGroup`.
 *
 * A button is named by everything it shows, in the order it shows it: its title, its
 * badge, then what it means. Naming it by the title alone would leave words on screen
 * that speech control cannot press; leaving the naming to the content would run the
 * pieces together into one word.
 */
export function ChoiceButtons<Value extends string>({
  label,
  value,
  options,
  onValueChange,
  pending = null,
  disabled = false,
  className,
}: ChoiceButtonsProps<Value>) {
  const name = useId();
  return (
    <div role="group" aria-label={label} className={cx(styles.radioGroup, className)}>
      {options.map((option) => {
        const id = `${name}-${option.value}`;
        const selected = option.value === value;
        const busy = option.value === pending;
        const namedBy = [
          `${id}-label`,
          option.badge ? `${id}-badge` : null,
          option.description ? `${id}-description` : null,
        ]
          .filter((part) => part !== null)
          .join(' ');
        return (
          <button
            key={option.value}
            type="button"
            className={cx(
              styles.radioRow,
              styles.choiceButton,
              selected && styles.radioRowSelected,
            )}
            aria-pressed={selected}
            aria-busy={busy || undefined}
            aria-labelledby={namedBy}
            // Kept focusable while something is pending, so the keyboard does not lose its place.
            aria-disabled={disabled || pending !== null || undefined}
            onClick={() => {
              if (!disabled && pending === null && !selected) onValueChange(option.value);
            }}
          >
            <span className={cx(styles.choiceMark, selected && styles.choiceMarkOn)} aria-hidden />
            <span className={styles.checkboxText}>
              <span className={styles.choiceTitle}>
                <span id={`${id}-label`}>{option.label}</span>
                {option.badge ? (
                  <>
                    {SPACE}
                    <span id={`${id}-badge`}>{option.badge}</span>
                  </>
                ) : null}
              </span>
              {option.description ? SPACE : null}
              {option.description ? (
                <span id={`${id}-description`} className={styles.checkboxDescription}>
                  {option.description}
                </span>
              ) : null}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export interface SegmentedOption<Value extends string> {
  value: Value;
  label: string;
  icon?: ReactNode;
}

export interface SegmentedControlProps<Value extends string> {
  /** Accessible name of the group. */
  label: string;
  value: Value;
  options: readonly SegmentedOption<Value>[];
  onValueChange: (value: Value) => void;
  className?: string;
}

/** A small set of mutually exclusive options, shown side by side. */
export function SegmentedControl<Value extends string>({
  label,
  value,
  options,
  onValueChange,
  className,
}: SegmentedControlProps<Value>) {
  const group = useRef<HTMLDivElement>(null);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>): void => {
    const index = options.findIndex((option) => option.value === value);
    let next = index;
    if (event.key === 'ArrowRight' || event.key === 'ArrowDown')
      next = (index + 1) % options.length;
    else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      next = (index - 1 + options.length) % options.length;
    } else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = options.length - 1;
    else return;
    event.preventDefault();
    const option = options[next];
    if (!option) return;
    onValueChange(option.value);
    group.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
  };

  return (
    // The radiogroup pattern: arrow keys move the selection, Tab enters and leaves the group.
    <div
      ref={group}
      role="radiogroup"
      aria-label={label}
      className={cx(styles.segmented, className)}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            className={cx(styles.segment, selected && styles.segmentSelected)}
            onClick={() => onValueChange(option.value)}
            onKeyDown={handleKeyDown}
          >
            {option.icon ? (
              <span className={styles.segmentIcon} aria-hidden="true">
                {option.icon}
              </span>
            ) : null}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onValueChange: (value: number) => void;
  /** Format the value for display and for assistive technology. */
  formatValue?: (value: number) => string;
  disabled?: boolean;
  className?: string;
}

/** A labelled range input. Fully keyboard operable; the value is always shown as text. */
export function Slider({
  label,
  value,
  min,
  max,
  step = 0.01,
  onValueChange,
  formatValue = (current) => String(current),
  disabled,
  className,
}: SliderProps) {
  const id = useId();
  const fraction = max > min ? (value - min) / (max - min) : 0;
  return (
    <div className={cx(styles.slider, className)}>
      <div className={styles.sliderHeader}>
        <label htmlFor={id} className={styles.sliderLabel}>
          {label}
        </label>
        <output htmlFor={id} className={cx(styles.sliderValue, 'ad-tabular')}>
          {formatValue(value)}
        </output>
      </div>
      <input
        id={id}
        type="range"
        className={styles.range}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-valuetext={formatValue(value)}
        style={
          { '--ad-slider-fill': `${Math.min(1, Math.max(0, fraction)) * 100}%` } as CSSProperties
        }
        onChange={(event) => onValueChange(Number(event.target.value))}
      />
    </div>
  );
}
