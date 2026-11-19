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
