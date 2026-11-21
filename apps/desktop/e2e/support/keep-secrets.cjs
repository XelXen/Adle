/**
 * Loaded into the app's main process by the launch helper, after the test tool's own
 * loader and before the app itself.
 *
 * The test tool starts every Chromium it drives with `--password-store=basic`. On Linux
 * that means "keep secrets as plain text", which Adle refuses to do: it says that a key
 * cannot be kept on this computer and offers no field for one. Every journey that saves a
 * key then stops at its first step, however good the keyring of the machine is (the first
 * runs on GitHub's Linux machines, 2026-11-21).
 *
 * So the switch is taken away again here, and the app chooses where to keep a secret as it
 * would for a learner: the desktop's keyring. On Windows and macOS the switch means
 * nothing, and it is taken away there too, so that every run starts the app the same way.
 *
 * Only an app run from its folder loads this. A packaged app loads neither this nor the
 * test tool's loader, so it never has the switch in the first place.
 */
const { app } = require('electron');

app.commandLine.removeSwitch('password-store');
