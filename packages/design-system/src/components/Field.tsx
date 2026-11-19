import { type ComponentProps, type ReactNode, useId } from 'react';

import { cx } from '../cx';
import styles from './Field.module.css';

interface FieldChrome {
  label: string;
  /** Helper text shown below the control. */
  description?: ReactNode;
  /** Error text. When present the control is marked invalid and this is announced. */
  error?: ReactNode;
  /** Visually hide the label (it stays available to assistive technology). */
  hideLabel?: boolean;
}

interface FieldIds {
  controlId: string;
  describedBy: string | undefined;
}

function FieldShell({
  label,
  description,
  error,
  hideLabel,
  className,
  children,
}: FieldChrome & { className?: string; children: (ids: FieldIds) => ReactNode }) {
  const id = useId();
  const controlId = `${id}-control`;
  const descriptionId = description ? `${id}-description` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, descriptionId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={cx(styles.field, className)}>
      <label htmlFor={controlId} className={cx(styles.label, hideLabel && 'ad-visually-hidden')}>
        {label}
      </label>
      {children({ controlId, describedBy })}
      {error ? (
        <p id={errorId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      {description ? (
        <p id={descriptionId} className={styles.description}>
          {description}
        </p>
      ) : null}
    </div>
  );
}

export interface TextFieldProps extends Omit<ComponentProps<'input'>, 'id'>, FieldChrome {
  /** Content rendered inside the control's trailing edge, e.g. a reveal button. */
  trailing?: ReactNode;
}

export function TextField({
  label,
  description,
  error,
  hideLabel,
  trailing,
  className,
  ...input
}: TextFieldProps) {
  return (
    <FieldShell
      label={label}
      description={description}
      error={error}
      hideLabel={hideLabel}
      className={className}
    >
      {({ controlId, describedBy }) => (
        <div className={cx(styles.control, error ? styles.invalid : undefined)}>
          <input
            {...input}
            id={controlId}
            className={styles.input}
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
          />
          {trailing ? <div className={styles.trailing}>{trailing}</div> : null}
        </div>
      )}
    </FieldShell>
  );
}

export interface TextAreaProps extends Omit<ComponentProps<'textarea'>, 'id'>, FieldChrome {}

export function TextArea({
  label,
  description,
  error,
  hideLabel,
  className,
  rows = 4,
  ...textarea
}: TextAreaProps) {
  return (
    <FieldShell
      label={label}
      description={description}
      error={error}
      hideLabel={hideLabel}
      className={className}
    >
      {({ controlId, describedBy }) => (
        <div className={cx(styles.control, styles.multiline, error ? styles.invalid : undefined)}>
          <textarea
            {...textarea}
            id={controlId}
            rows={rows}
            className={cx(styles.input, styles.textarea)}
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
          />
        </div>
      )}
    </FieldShell>
  );
}

export interface SelectOption<Value extends string = string> {
  value: Value;
  label: string;
}

export interface SelectProps<Value extends string = string>
  extends Omit<ComponentProps<'select'>, 'id' | 'value' | 'onChange' | 'children'>, FieldChrome {
  value: Value;
  options: readonly SelectOption<Value>[];
  onValueChange: (value: Value) => void;
}

export function Select<Value extends string = string>({
  label,
  description,
  error,
  hideLabel,
  className,
  value,
  options,
  onValueChange,
  ...select
}: SelectProps<Value>) {
  return (
    <FieldShell
      label={label}
      description={description}
      error={error}
      hideLabel={hideLabel}
      className={className}
    >
      {({ controlId, describedBy }) => (
        <div className={cx(styles.control, error ? styles.invalid : undefined)}>
          <select
            {...select}
            id={controlId}
            className={cx(styles.input, styles.select)}
            value={value}
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
            onChange={(event) => onValueChange(event.target.value as Value)}
          >
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </FieldShell>
  );
}
