import { Info } from 'lucide-react';

import { InfoPopover } from '@adle/design-system';

export interface WhatIsSentProps {
  /** What the request carries, as a phrase to follow "Sends": see `lib/generation.ts`. */
  what: string;
  /** Where it goes, as the core plans it: `destination(status, work)`, never a fixed name. */
  to: string;
  /** How long it usually takes, in words, where the core could say. */
  wait?: string | null;
  /** Anything else worth knowing about what comes back, as a sentence. */
  after?: string;
}

/**
 * What a request to an AI provider carries and where it goes, one press away from the
 * control that sends it (ADR-036).
 *
 * It is said in full once, where a key is given, and listed under Privacy & data. Beside
 * every button it was a paragraph nobody reads twice; behind this it is there for whoever
 * wants to know, in the same words, before anything is sent.
 */
export function WhatIsSent({ what, to, wait, after }: WhatIsSentProps) {
  return (
    <InfoPopover label="What is sent" icon={<Info />} title="What is sent">
      <p>
        Sends {what} to {to}.
      </p>
      {wait || after ? (
        <p>
          {wait ? `Usually takes ${wait}.` : ''}
          {wait && after ? ' ' : ''}
          {after ?? ''}
        </p>
      ) : null}
      <p>AI can make mistakes.</p>
    </InfoPopover>
  );
}
