// Test double for the Python core's launch protocol. Not shipped.
// Usage: node fake-core.mjs <mode>
//   ready       handshake, announce ready, exit on stdin EOF
//   fatal       report a fatal startup error
//   silent      never announce anything
//   crash       announce ready, then exit unexpectedly
//   stubborn    announce ready and ignore stdin EOF
//   echo-argv   fail if the token leaked into argv or the environment
import readline from 'node:readline';

const mode = process.argv[2] ?? 'ready';
const emit = (event) => process.stdout.write(`${JSON.stringify(event)}\n`);
const lines = readline.createInterface({ input: process.stdin });

let token = null;
lines.once('line', (line) => {
  token = JSON.parse(line).token;
  if (typeof token !== 'string' || token.length < 32) {
    emit({ event: 'fatal', message: 'bad handshake' });
    process.exit(2);
  }

  if (mode === 'fatal') {
    emit({ event: 'fatal', message: 'No data directory configured.' });
    process.exit(2);
  }
  if (mode === 'silent') return;
  if (mode === 'echo-argv') {
    const leaked =
      process.argv.some((argument) => argument.includes(token)) ||
      Object.values(process.env).some((value) => value?.includes(token));
    emit(
      leaked
        ? { event: 'fatal', message: 'token leaked' }
        : { event: 'ready', port: 4321, version: 'fake' },
    );
    return;
  }

  process.stdout.write('some unrelated noise on stdout\n');
  emit({ event: 'ready', port: 4321, version: 'fake' });
  if (mode === 'crash') setTimeout(() => process.exit(7), 50);
});

lines.on('close', () => {
  if (mode === 'stubborn') {
    setInterval(() => {}, 1000);
    return;
  }
  process.exit(0);
});
