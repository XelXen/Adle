import { type ReactNode, type Ref, useEffect, useImperativeHandle, useRef, useState } from 'react';

import { Play } from 'lucide-react';

import { Button, cx, Slider, Spinner, Switch } from '@adle/design-system';
import type { ControlDescriptor } from '@adle/event-protocol';

import {
  type PlayerStatus,
  type SceneEvent,
  type SceneFailure,
  WanimPlayerAdapter,
} from '../../../player/host/WanimPlayerAdapter';
import { useResolvedTheme } from '../lib/theme';
import styles from './ScenePlayer.module.css';
import { StageFrame } from './StageFrame';

export interface ScenePlayerHandle {
  play: () => void;
  pause: () => void;
  /** Continue past an interactive page. */
  next: () => void;
  /** Run the scene again from the start. */
  reset: () => void;
}

export interface ScenePlayerProps {
  /** One complete Python scene file. */
  source: string;
  sceneName?: string;
  /** Accessible name of the visualization. */
  title: string;
  autoplay?: boolean;
  /**
   * What to show if the scene cannot run: a text explanation of the same idea.
   * A broken animation must never take the lesson down with it.
   */
  fallback: ReactNode;
  /** Human labels for mirrored controls, keyed by the scene's control name. */
  controlLabels?: Record<string, string>;
  onStatusChange?: (status: PlayerStatus) => void;
  onSceneEvent?: (event: SceneEvent) => void;
  onFailure?: (failure: SceneFailure) => void;
  /**
   * Given while the scene is waiting to be started: pressing the picture starts it. A
   * convenience for the pointer; the screen keeps a named, keyboard-operable control.
   */
  onStart?: () => void;
  /**
   * Show the picture on the lesson's screen (`StageFrame`): one dark surface in either
   * theme, for which the picture is drawn with the dark palette whatever the theme is.
   */
  onStage?: boolean;
  /** With `onStage`: the words being said, along the foot of the screen. */
  caption?: ReactNode;
  /** With `onStage`: the line along the top of the screen. */
  header?: ReactNode;
  ref?: Ref<ScenePlayerHandle>;
}

function humanise(name: string): string {
  const words = name.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function formatNumber(value: number): string {
  return value.toFixed(Math.abs(value) >= 100 ? 0 : 2);
}

/**
 * Shows a Wanim scene in the isolated player, with:
 *  - a visible loading state,
 *  - the scene's controls mirrored as native, keyboard-operable inputs,
 *  - a text fallback (and a retry) when the scene fails for any reason.
 */
export function ScenePlayer({
  source,
  sceneName,
  title,
  autoplay = true,
  fallback,
  controlLabels,
  onStatusChange,
  onSceneEvent,
  onFailure,
  onStart,
  onStage = false,
  caption,
  header,
  ref,
}: ScenePlayerProps) {
  const host = useRef<HTMLDivElement>(null);
  const adapter = useRef<WanimPlayerAdapter | null>(null);
  const [status, setStatus] = useState<PlayerStatus>('loading');
  const [controls, setControls] = useState<ControlDescriptor[]>([]);
  const appTheme = useResolvedTheme();
  const theme = onStage ? 'dark' : appTheme;

  // Keep the latest callbacks without re-creating the adapter when they change.
  const callbacks = useRef({ onStatusChange, onSceneEvent, onFailure });
  useEffect(() => {
    callbacks.current = { onStatusChange, onSceneEvent, onFailure };
  });

  const themeAtMount = useRef(theme);
  useEffect(() => {
    if (!host.current) return;
    const player = new WanimPlayerAdapter(host.current, { title, className: styles.frame });
    adapter.current = player;
    player.on('status', (next) => {
      setStatus(next);
      if (next === 'loading' || next === 'failed') setControls([]);
      callbacks.current.onStatusChange?.(next);
    });
    player.on('controls', setControls);
    player.on('scene-event', (event) => callbacks.current.onSceneEvent?.(event));
    player.on('failure', (failure) => callbacks.current.onFailure?.(failure));
    player.load({ source, sceneName, theme: themeAtMount.current, autoplay });
    return () => {
      player.dispose();
      adapter.current = null;
    };
  }, [source, sceneName, autoplay, title]);

  useEffect(() => {
    themeAtMount.current = theme;
    adapter.current?.setTheme(theme);
  }, [theme]);

  useImperativeHandle(
    ref,
    () => ({
      play: () => adapter.current?.play(),
      pause: () => adapter.current?.pause(),
      next: () => adapter.current?.next(),
      reset: () => adapter.current?.reset(),
    }),
    [],
  );

  const failed = status === 'failed';
  const interactive = status === 'interactive' && controls.length > 0;
  // Loaded, and waiting to be started: the picture has nothing in it yet.
  const poster = onStart !== undefined && !failed && status !== 'loading';

  const picture = (
    <div className={cx(styles.stage, onStage && styles.onScreen)}>
      <div ref={host} className={styles.frameHost} hidden={failed} />
      {status === 'loading' ? (
        <div className={styles.overlay} role="status">
          <Spinner size="large" />
          <span>Loading animation…</span>
        </div>
      ) : null}
      {poster ? (
        // For the pointer only: the control that starts a lesson, with its name and its
        // place in the keyboard's order, is the Start button beside the picture.
        <button
          type="button"
          className={styles.poster}
          tabIndex={-1}
          aria-hidden="true"
          onClick={onStart}
        >
          <span className={styles.posterMark}>
            <Play />
          </span>
          <span className={styles.posterTitle}>{title}</span>
        </button>
      ) : null}
      {failed ? (
        <div className={styles.fallback}>
          <div className={styles.fallbackBody}>{fallback}</div>
          <div className={styles.fallbackActions}>
            <p className={styles.fallbackNote}>
              Couldn’t show the animation. Here’s the same idea in words.
            </p>
            <Button size="small" onClick={() => adapter.current?.reset()}>
              Retry animation
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );

  return (
    <figure className={styles.player} aria-label={title}>
      {onStage ? (
        <StageFrame header={header} caption={caption}>
          {picture}
        </StageFrame>
      ) : (
        picture
      )}

      {interactive ? (
        <figcaption className={styles.controls}>
          <p className={styles.controlsHint}>Use these controls, or the ones on the picture.</p>
          <div className={styles.controlGrid}>
            {controls.map((control) => {
              // The name is the scene's: only a label written down for it counts, never
              // something every object happens to have.
              const label =
                controlLabels && Object.hasOwn(controlLabels, control.name)
                  ? (controlLabels[control.name] ?? humanise(control.name))
                  : humanise(control.name);
              if (control.kind === 'switch' && typeof control.value === 'boolean') {
                return (
                  <Switch
                    key={control.name}
                    label={label}
                    checked={control.value}
                    onCheckedChange={(checked) =>
                      adapter.current?.setControl(control.name, checked)
                    }
                  />
                );
              }
              if (
                typeof control.value === 'number' &&
                control.min !== undefined &&
                control.max !== undefined
              ) {
                return (
                  <Slider
                    key={control.name}
                    label={label}
                    value={control.value}
                    min={control.min}
                    max={control.max}
                    step={(control.max - control.min) / 100}
                    formatValue={formatNumber}
                    onValueChange={(value) => adapter.current?.setControl(control.name, value)}
                  />
                );
              }
              return null;
            })}
          </div>
        </figcaption>
      ) : null}
    </figure>
  );
}
