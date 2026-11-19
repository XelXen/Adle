import type { ComponentProps, ReactNode } from 'react';

import { cx } from '../cx';
import styles from './Layout.module.css';

export interface AppShellProps {
  /** Brand area at the top of the navigation rail. */
  brand: ReactNode;
  /** Primary destinations. */
  navigation: ReactNode;
  /** Content pinned to the bottom of the rail, e.g. service status. */
  footer?: ReactNode;
  children: ReactNode;
}

/** The application frame: a persistent navigation rail and one scrolling main region. */
export function AppShell({ brand, navigation, footer, children }: AppShellProps) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#ad-main">
        Skip to content
      </a>
      <aside className={styles.rail}>
        <div className={styles.brand}>{brand}</div>
        <nav className={styles.nav} aria-label="Primary">
          {navigation}
        </nav>
        {footer ? <div className={styles.railFooter}>{footer}</div> : null}
      </aside>
      <main id="ad-main" className={styles.main} tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

export interface NavItemProps extends Omit<ComponentProps<'button'>, 'children'> {
  label: string;
  icon: ReactNode;
  /** Marks the destination the learner is currently on. */
  current?: boolean;
}

export function NavItem({ label, icon, current = false, className, ...rest }: NavItemProps) {
  return (
    <button
      {...rest}
      type="button"
      aria-current={current ? 'page' : undefined}
      className={cx(styles.navItem, current && styles.navItemCurrent, className)}
    >
      <span className={styles.navIcon} aria-hidden="true">
        {icon}
      </span>
      {label}
    </button>
  );
}

export interface PageProps {
  title: string;
  /** One sentence that orients the learner. */
  description?: ReactNode;
  /** Primary page-level actions, shown beside the title. */
  actions?: ReactNode;
  /** Content shown above the title, e.g. a back link. */
  eyebrow?: ReactNode;
  /** `reading` narrows the column for long-form text. */
  width?: 'wide' | 'reading';
  children: ReactNode;
}

/** A page inside the shell: a heading block followed by content sections. */
export function Page({
  title,
  description,
  actions,
  eyebrow,
  width = 'wide',
  children,
}: PageProps) {
  return (
    <div className={cx(styles.page, styles[width])}>
      <header className={styles.pageHeader}>
        <div className={styles.pageHeading}>
          {eyebrow ? <div className={styles.eyebrow}>{eyebrow}</div> : null}
          <h1 className={styles.pageTitle}>{title}</h1>
          {description ? <p className={styles.pageDescription}>{description}</p> : null}
        </div>
        {actions ? <div className={styles.pageActions}>{actions}</div> : null}
      </header>
      {children}
    </div>
  );
}

export interface SectionProps {
  title?: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** A titled group of content within a page. Prefer sections over nested cards. */
export function Section({ title, description, actions, children, className }: SectionProps) {
  return (
    <section className={cx(styles.section, className)}>
      {title ? (
        <div className={styles.sectionHeader}>
          <div className={styles.sectionHeading}>
            <h2 className={styles.sectionTitle}>{title}</h2>
            {description ? <p className={styles.sectionDescription}>{description}</p> : null}
          </div>
          {actions ? <div className={styles.pageActions}>{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export interface StackProps extends ComponentProps<'div'> {
  /** Spacing token step between children. */
  gap?: 1 | 2 | 3 | 4 | 5 | 6;
  direction?: 'column' | 'row';
  align?: 'start' | 'center' | 'end' | 'stretch';
  wrap?: boolean;
}

/** Lays children out with a consistent token gap. */
export function Stack({
  gap = 4,
  direction = 'column',
  align,
  wrap = false,
  className,
  ...rest
}: StackProps) {
  return (
    <div
      {...rest}
      className={cx(
        styles.stack,
        styles[`gap${gap}`],
        direction === 'row' && styles.row,
        align && styles[`align-${align}`],
        wrap && styles.wrap,
        className,
      )}
    />
  );
}
