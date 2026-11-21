import { type ComponentProps, type ReactNode, useEffect } from 'react';

import { cx } from '../cx';
import styles from './Layout.module.css';

export interface AppShellProps {
  /** Brand area at the top of the navigation rail. */
  brand: ReactNode;
  /** Primary destinations. */
  navigation: ReactNode;
  /** Content pinned to the bottom of the rail, e.g. service status. */
  footer?: ReactNode;
  /**
   * Give the whole window to the main region and leave the rail out. For the one kind of
   * screen that is a single thing to attend to (a lesson). That screen must then offer its
   * own way back.
   */
  focus?: boolean;
  children: ReactNode;
}

/**
 * The application frame: a navigation rail lying on the canvas, and one scrolling main
 * region set into it as a panel.
 */
export function AppShell({ brand, navigation, footer, focus = false, children }: AppShellProps) {
  // Said on the document, so that what lies outside the shell (toasts) can keep clear of
  // the controls such a screen puts along its foot.
  useEffect(() => {
    document.documentElement.toggleAttribute('data-ad-focus', focus);
    return () => document.documentElement.removeAttribute('data-ad-focus');
  }, [focus]);

  return (
    <div className={cx(styles.shell, focus && styles.focus)}>
      <a className={styles.skipLink} href="#ad-main">
        Skip to content
      </a>
      {focus ? null : (
        <aside className={styles.rail}>
          <div className={styles.brand}>{brand}</div>
          <nav className={styles.nav} aria-label="Primary">
            {navigation}
          </nav>
          {footer ? <div className={styles.railFooter}>{footer}</div> : null}
        </aside>
      )}
      <main id="ad-main" className={styles.main} tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

/**
 * The strip along the top that the window is moved by, where the app has a title bar of
 * its own (ADR-030). Rendered once, above every screen. It has no height unless the page
 * was told the window has no title bar of the operating system's (`data-ad-titlebar` on
 * the document), so it is harmless anywhere else.
 */
export function WindowStrip() {
  return <div className={styles.windowStrip} aria-hidden="true" />;
}

export interface NavSectionProps {
  /** What the items in this group are, e.g. "Courses". */
  label: string;
  /**
   * Keep the group when the rail narrows to icons. For items that say something by their
   * icon alone (work in progress); a list of names is left out there, as it would say
   * nothing.
   */
  keepWhenNarrow?: boolean;
  children: ReactNode;
}

/** A labelled group of destinations in the rail, below the primary ones. */
export function NavSection({ label, keepWhenNarrow = false, children }: NavSectionProps) {
  return (
    <div
      className={cx(styles.navSection, keepWhenNarrow && styles.navSectionKept)}
      role="group"
      aria-label={label}
    >
      <span className={styles.navSectionLabel} aria-hidden="true">
        {label}
      </span>
      {children}
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
      <span className={styles.navLabel}>{label}</span>
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
  /**
   * `compact`: a smaller title and less air around it, for a page that gives its room to
   * one thing, such as a lesson's screen.
   */
  density?: 'regular' | 'compact';
  children: ReactNode;
}

/** A page inside the shell: a heading block followed by content sections. */
export function Page({
  title,
  description,
  actions,
  eyebrow,
  width = 'wide',
  density = 'regular',
  children,
}: PageProps) {
  return (
    <div className={cx(styles.page, styles[width], density === 'compact' && styles.compact)}>
      <header className={styles.pageHeader}>
        {eyebrow ? <div className={styles.eyebrow}>{eyebrow}</div> : null}
        <div className={styles.pageTitleRow}>
          <h1 className={styles.pageTitle}>{title}</h1>
          {actions ? <div className={styles.pageActions}>{actions}</div> : null}
        </div>
        {description ? <div className={styles.pageDescription}>{description}</div> : null}
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
