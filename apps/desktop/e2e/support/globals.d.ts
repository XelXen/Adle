import type { AdleBridge } from '../../electron/shared/ipc';

declare global {
  interface Window {
    /** The preload bridge, as seen by code evaluated inside the renderer. */
    adle?: AdleBridge;
  }
}
