import { type KeyboardEvent, type ReactNode, useId, useRef } from 'react';

import { cx } from '../cx';
import styles from './Tabs.module.css';

export interface TabItem<Value extends string> {
  value: Value;
  label: string;
  icon?: ReactNode;
}

export interface TabsProps<Value extends string> {
  /** Accessible name of the tab list. */
  label: string;
  tabs: readonly TabItem<Value>[];
  value: Value;
  onValueChange: (value: Value) => void;
  /** Renders the panel for the selected tab. */
  children: (value: Value) => ReactNode;
  className?: string;
}

/** Tabs following the WAI-ARIA pattern: arrows move between tabs, Tab moves into the panel. */
export function Tabs<Value extends string>({
  label,
  tabs,
  value,
  onValueChange,
  children,
  className,
}: TabsProps<Value>) {
  const id = useId();
  const list = useRef<HTMLDivElement>(null);
  const tabId = (tab: Value): string => `${id}-tab-${tab}`;
  const panelId = `${id}-panel`;

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>): void => {
    const index = tabs.findIndex((tab) => tab.value === value);
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    const tab = tabs[next];
    if (!tab) return;
    onValueChange(tab.value);
    list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  };

  return (
    <div className={cx(styles.tabs, className)}>
      <div ref={list} role="tablist" aria-label={label} className={styles.list}>
        {tabs.map((tab) => {
          const selected = tab.value === value;
          return (
            <button
              key={tab.value}
              id={tabId(tab.value)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId}
              tabIndex={selected ? 0 : -1}
              className={cx(styles.tab, selected && styles.selected)}
              onClick={() => onValueChange(tab.value)}
              onKeyDown={handleKeyDown}
            >
              {tab.icon ? (
                <span className={styles.icon} aria-hidden="true">
                  {tab.icon}
                </span>
              ) : null}
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        id={panelId}
        role="tabpanel"
        aria-labelledby={tabId(value)}
        tabIndex={0}
        className={styles.panel}
      >
        {children(value)}
      </div>
    </div>
  );
}
