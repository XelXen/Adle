/**
 * Shared API contract between the Python core and the desktop app.
 *
 * Everything here is generated from the FastAPI application. See
 * `scripts/generate-contracts.mjs`.
 */
export type * from './generated/models';
export { OPERATIONS } from './generated/operations';
export type { OperationId, OperationTypes } from './generated/operations';
