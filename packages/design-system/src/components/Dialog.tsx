import { X } from 'lucide-react';
import {
  type ReactNode,
  type SyntheticEvent,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
} from 'react';

import { cx } from '../cx';
import { IconButton } from './Button';
import styles from './Dialog.module.css';

export interface DialogProps {
  open: boolean;
  /** Called when the learner dismisses the dialog (Escape, close button, backdrop). */
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  /** Footer buttons. Put the primary action last. */
  actions?: ReactNode;
  /** Prevent dismissal while an irreversible operation is running. */
  dismissible?: boolean;
  size?: 'small' | 'medium';
}

function giveFocusBack(to: HTMLElement | null): void {
  // Only if nothing else has taken it meanwhile, and what had it is still there.
  const lost = document.activeElement === null || document.activeElement === document.body;
  if (lost && to?.isConnected) to.focus({ preventScroll: true });
}

/**
 * A modal dialog built on the native `<dialog>` element, which provides the
 * focus trap, Escape handling, and inert background for free.
 *
 * Focus starts on the close button, the safe choice for a confirmation. In a
 * form, put `data-autofocus` on the field the learner should start typing in.
 * When the dialog goes, focus goes back to whatever had it before, also when the
 * dialog is simply taken off the page while open.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  actions,
  dismissible = true,
  size = 'small',
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  /** What had the focus when the dialog opened. */
  const opener = useRef<HTMLElement | null>(null);
  /** Whether the press that is about to become a click began on the backdrop. */
  const pressedOutside = useRef(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      opener.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
      // The browser focuses the first focusable element, which is the close button.
      // A form dialog marks the field to start in with `data-autofocus` instead.
      dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
      giveFocusBack(opener.current);
    }
  }, [open]);

  // A dialog that is mounted only while open is never closed: it is taken off the page.
  // The browser gives the focus back when a dialog closes, not when it disappears, so
  // without this the focus would be left on nothing. A layout effect, because by the time
  // an ordinary one is cleaned up the element is already gone.
  useLayoutEffect(() => {
    const dialog = ref.current;
    return () => {
      if (dialog?.open) dialog.close();
      giveFocusBack(opener.current);
    };
  }, []);

  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>): void => {
    // Keep React in charge of the open state.
    event.preventDefault();
    if (dismissible) onClose();
  };

  return (
    // The dialog element handles Escape natively (the `cancel` event); the click
    // handler only implements backdrop dismissal, which has a keyboard equivalent.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={ref}
      className={cx(styles.dialog, styles[size])}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={handleCancel}
      onClose={() => {
        if (open) onClose();
      }}
      onPointerDown={(event) => {
        pressedOutside.current = event.target === ref.current;
      }}
      onClick={(event) => {
        // Only a press that also began on the backdrop: selecting text in a field and
        // letting go outside is not asking for the dialog, and what was typed, to go.
        const outside = event.target === ref.current && pressedOutside.current;
        pressedOutside.current = false;
        if (dismissible && outside) onClose();
      }}
    >
      <div className={styles.content}>
        <header className={styles.header}>
          <h2 id={titleId} className={styles.title}>
            {title}
          </h2>
          {dismissible ? (
            <IconButton label="Close" icon={<X />} size="small" onClick={onClose} />
          ) : null}
        </header>
        {description ? (
          <p id={descriptionId} className={styles.description}>
            {description}
          </p>
        ) : null}
        {children ? <div className={styles.body}>{children}</div> : null}
        {actions ? <footer className={styles.actions}>{actions}</footer> : null}
      </div>
    </dialog>
  );
}
