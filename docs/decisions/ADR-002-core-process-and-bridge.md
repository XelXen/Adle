# ADR-002: The Python core is a supervised child, reached only through the main process

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

The core (FastAPI) holds all learner data and makes the provider calls. The renderer displays it.
PLAN.md §5.3 requires loopback-only binding, an ephemeral token, no secrets in argv or logs, and
that "the renderer must not get unrestricted access to the backend process".

## Decision

**Launch handshake** (`services/core/adle_core/__main__.py`, `electron/main/core/process.ts`):

1. Main generates 32 random bytes per launch and spawns the core with stdio pipes.
2. Main writes one JSON line to the child's **stdin**: `{"token": "..."}`.
3. The core binds `127.0.0.1:0` (the OS picks the port) and, once accepting connections, writes one
   JSON line to **stdout**: `{"event":"ready","port":N,"version":"..."}`. A startup failure is
   `{"event":"fatal","message":"..."}`. stdout carries nothing else; diagnostics go to stderr, which
   main writes to `logs/core.log`.
4. When stdin reaches EOF the core shuts down. That is both the graceful-stop signal and the
   guarantee against an orphaned backend if Electron dies.

The token is never in argv, the environment, or a log. Every route requires it as a bearer token,
compared in constant time. A `TrustedHost` check rejects non-loopback `Host` headers.

**Bridge.** The renderer never learns the port or the token. It calls
`window.adle.core.invoke(operationId, params)`; the main process:

1. accepts the call only from the top-level `adle://app` document,
2. looks the operation up in a table **generated from the core's OpenAPI document** (ADR-005),
3. refuses operations marked internal and anything not in the table,
4. bounds and shape-checks the parameters,
5. forwards the request with the token and returns `{ ok, data } | { ok, error }`.

The core validates everything again with Pydantic; it is the authority.

**Credentials.** The provider key is encrypted with Electron `safeStorage` (DPAPI, Keychain,
libsecret) in `credentials.bin`. After each core start, main decrypts it and pushes it to the core
through an internal route; the core keeps it in memory only. On Linux, the `basic_text` fallback
backend is treated as "no secure storage" and the key is refused.

## Alternatives considered

- **Renderer talks to the core directly with the token.** Simpler streaming, but any script
  injection in the renderer would get the whole API, and the renderer would need network access.
  Rejected: with mediation the Chromium session can refuse every non-`adle:` request outright.
- **Token in an environment variable.** Readable by other processes of the same user on some
  systems. stdin is not.
- **Core reads the key from its own keyring.** Two components holding secrets; rejected.

## Consequences

- The renderer has no network at all (`connect-src 'self'` plus a session-level request filter).
- Long-running work is modelled as jobs polled through the same bridge (introduced with M5).
- Loopback traffic is plaintext HTTP. An attacker who can read loopback traffic of the user's
  session already has the user's files; this is recorded in SECURITY.md.
