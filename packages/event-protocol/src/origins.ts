/**
 * Origins of the two halves of the app.
 *
 * - `adle://app` is the trusted renderer.
 * - `adle://<instance>.player` is an isolated scene player. Every player frame
 *   instance gets its own origin, which gives each one its own process and its
 *   own (empty) storage. A scene that hangs or crashes its process can therefore
 *   never affect the next frame, and nothing a scene stores can be read by a
 *   later one. See docs/decisions/ADR-004-scene-isolation.md.
 */

export const ADLE_SCHEME = 'adle';
export const APP_HOST = 'app';
export const APP_ORIGIN = `${ADLE_SCHEME}://${APP_HOST}`;

const PLAYER_HOST_SUFFIX = '.player';
const INSTANCE_PATTERN = /^[a-z0-9]{1,24}$/;

/** CSP source expression matching every player origin. */
export const PLAYER_ORIGIN_CSP_SOURCE = `${ADLE_SCHEME}://*${PLAYER_HOST_SUFFIX}`;

export function isPlayerInstanceId(value: string): boolean {
  return INSTANCE_PATTERN.test(value);
}

export function isPlayerHost(host: string): boolean {
  return (
    host.endsWith(PLAYER_HOST_SUFFIX) &&
    isPlayerInstanceId(host.slice(0, -PLAYER_HOST_SUFFIX.length))
  );
}

export function playerOrigin(instanceId: string): string {
  if (!isPlayerInstanceId(instanceId)) throw new TypeError('Invalid player instance id.');
  return `${ADLE_SCHEME}://${instanceId}${PLAYER_HOST_SUFFIX}`;
}

export function playerEntryUrl(instanceId: string): string {
  return `${playerOrigin(instanceId)}/index.html`;
}

/** True for an origin string such as `adle://k3f9.player`. */
export function isPlayerOrigin(origin: string): boolean {
  const prefix = `${ADLE_SCHEME}://`;
  return origin.startsWith(prefix) && isPlayerHost(origin.slice(prefix.length));
}

const ADLE_URL_PATTERN = /^adle:\/\/([a-z0-9.-]{1,64})(?:[/?#]|$)/;

/**
 * The origin of an `adle://` URL, or `null` for anything else.
 *
 * Use this instead of `new URL(value).origin`: Node's URL parser treats custom
 * schemes as "non-special" and reports their origin as the string `"null"`,
 * even though Chromium (where the scheme is registered as standard) does not.
 */
export function adleOriginOf(rawUrl: string): string | null {
  const match = ADLE_URL_PATTERN.exec(rawUrl);
  return match ? `${ADLE_SCHEME}://${match[1]}` : null;
}

/** A fresh instance id for a new player frame. */
export function createPlayerInstanceId(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}
