import { CircleAlert, CircleCheck, Info, X } from 'lucide-react';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { cx } from '../cx';
import { IconButton } from './Button';
import styles from './Toast.module.css';

export type ToastTone = 'success' | 'info' | 'danger';

export interface ToastOptions {
  tone?: ToastTone;
  title: string;
  description?: string;
  /** Milliseconds before auto-dismissal. Errors stay until dismissed. */
  durationMs?: number;
}

interface ToastRecord extends Required<Pick<ToastOptions, 'tone' | 'title'>> {
  id: number;
  description?: string;
  durationMs: number | null;
}

interface ToastApi {
  show: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const DEFAULT_DURATION_MS = 5000;
const MAX_VISIBLE = 3;
const ICONS = { success: CircleCheck, info: Info, danger: CircleAlert } as const;

/** Brief, non-blocking confirmation of something the learner just did. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback((options: ToastOptions) => {
    const tone = options.tone ?? 'info';
    const record: ToastRecord = {
      id: nextId.current++,
      tone,
      title: options.title,
      description: options.description,
      // An error must not disappear before it has been read.
      durationMs: tone === 'danger' ? null : (options.durationMs ?? DEFAULT_DURATION_MS),
    };
    setToasts((current) => [...current, record].slice(-MAX_VISIBLE));
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className={styles.region} role="region" aria-label="Notifications">
        {toasts.map((toast) => (
          <ToastView key={toast.id} toast={toast} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastView({ toast, onDismiss }: { toast: ToastRecord; onDismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false);
  const Icon = ICONS[toast.tone];

  useEffect(() => {
    if (toast.durationMs === null || paused) return;
    const timer = window.setTimeout(() => onDismiss(toast.id), toast.durationMs);
    return () => window.clearTimeout(timer);
  }, [toast.id, toast.durationMs, paused, onDismiss]);

  return (
    <div
      className={cx(styles.toast, styles[toast.tone])}
      role={toast.tone === 'danger' ? 'alert' : 'status'}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <Icon className={styles.icon} aria-hidden="true" />
      <div className={styles.text}>
        <p className={styles.title}>{toast.title}</p>
        {toast.description ? <p className={styles.description}>{toast.description}</p> : null}
      </div>
      <IconButton
        label="Dismiss notification"
        icon={<X />}
        size="small"
        onClick={() => onDismiss(toast.id)}
      />
    </div>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error('useToast must be used inside <ToastProvider>.');
  return api;
}
