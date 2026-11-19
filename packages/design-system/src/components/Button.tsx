import type { ComponentProps, MouseEvent, ReactNode } from 'react';

import { cx } from '../cx';
import styles from './Button.module.css';
import { Spinner } from './Spinner';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'destructive';
export type ButtonSize = 'small' | 'medium' | 'large';

export interface ButtonProps extends ComponentProps<'button'> {
  /** `primary`: the one main action of a view. Use at most one per region. */
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows progress and ignores clicks while keeping the button focusable. */
  loading?: boolean;
  /** Decorative leading icon. */
  icon?: ReactNode;
  fullWidth?: boolean;
}

export function Button({
  variant = 'secondary',
  size = 'medium',
  loading = false,
  icon,
  fullWidth = false,
  type = 'button',
  className,
  children,
  onClick,
  disabled,
  ...rest
}: ButtonProps) {
  const handleClick = (event: MouseEvent<HTMLButtonElement>): void => {
    if (loading) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };

  return (
    <button
      {...rest}
      type={type}
      className={cx(
        styles.button,
        styles[variant],
        styles[size],
        fullWidth && styles.fullWidth,
        className,
      )}
      disabled={disabled}
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      onClick={handleClick}
    >
      {loading ? (
        <Spinner size="small" />
      ) : (
        icon && (
          <span className={styles.icon} aria-hidden="true">
            {icon}
          </span>
        )
      )}
      <span className={styles.label}>{children}</span>
    </button>
  );
}

export interface IconButtonProps extends Omit<ComponentProps<'button'>, 'children' | 'aria-label'> {
  /** Required: an icon alone is not an accessible name. */
  label: string;
  icon: ReactNode;
  size?: ButtonSize;
  variant?: 'secondary' | 'tertiary';
}

export function IconButton({
  label,
  icon,
  size = 'medium',
  variant = 'tertiary',
  type = 'button',
  className,
  ...rest
}: IconButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      aria-label={label}
      title={label}
      className={cx(styles.button, styles.iconOnly, styles[variant], styles[size], className)}
    >
      <span className={styles.icon} aria-hidden="true">
        {icon}
      </span>
    </button>
  );
}
