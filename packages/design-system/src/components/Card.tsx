import type { ComponentProps, ReactNode } from 'react';

import { cx } from '../cx';
import styles from './Card.module.css';

export interface CardProps extends ComponentProps<'div'> {
  /** Semantic element. Use `section` or `article` when the card has a heading. */
  as?: 'div' | 'section' | 'article' | 'li';
  /** `subtle` is a quiet, borderless region for secondary content. */
  tone?: 'surface' | 'subtle';
  padding?: 'none' | 'compact' | 'comfortable';
}

/**
 * A surface that groups related content.
 *
 * Do not nest cards to create hierarchy; use headings and spacing instead.
 */
export function Card({
  as = 'div',
  tone = 'surface',
  padding = 'comfortable',
  className,
  ...rest
}: CardProps) {
  // Every allowed element accepts the same props; the cast keeps `ref` typing simple.
  const Element = as as 'div';
  return (
    <Element {...rest} className={cx(styles.card, styles[tone], styles[padding], className)} />
  );
}

export interface ActionCardProps extends Omit<ComponentProps<'button'>, 'title'> {
  title: ReactNode;
  description?: ReactNode;
  /** Decorative leading visual. */
  media?: ReactNode;
  /** Small trailing content, e.g. a badge or chevron. */
  meta?: ReactNode;
}

/** A whole-card button for choosing between a few clear options. */
export function ActionCard({
  title,
  description,
  media,
  meta,
  className,
  type = 'button',
  ...rest
}: ActionCardProps) {
  return (
    <button
      {...rest}
      type={type}
      className={cx(styles.card, styles.surface, styles.action, className)}
    >
      {media ? (
        <span className={styles.media} aria-hidden="true">
          {media}
        </span>
      ) : null}
      <span className={styles.actionText}>
        <span className={styles.actionTitle}>{title}</span>
        {description ? <span className={styles.actionDescription}>{description}</span> : null}
      </span>
      {meta ? <span className={styles.meta}>{meta}</span> : null}
    </button>
  );
}
