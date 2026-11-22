import { useEffect } from 'react';

import type { RecordedNarrator } from '../lesson/recorded';
import { callCore } from './core-client';

/** How often a recording under way is looked at. */
const LOOK_EVERY_MS = 2_500;

/** The distinct lines a lesson says, as its narration gives them. */
export function linesOf(lesson: {
  segments: readonly { narration?: readonly { text: string }[] | null }[];
}): string[] {
  const lines: string[] = [];
  for (const segment of lesson.segments) {
    for (const beat of segment.narration ?? []) {
      if (!lines.includes(beat.text)) lines.push(beat.text);
    }
  }
  return lines;
}

/** A clip as the core sends it, made a sound of the page's own. */
function soundOf(clip: { mime: string; data: string }): string {
  const binary = atob(clip.data);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return URL.createObjectURL(new Blob([bytes], { type: clip.mime }));
}

/**
 * A lesson's narration in the natural voice (ADR-042). When the voice is chosen, the lines
 * already recorded are handed to the narrator as the lesson opens; if some are not, the
 * lesson is recorded, in the background, and each line is handed over as it is done. A line
 * not yet recorded is read as before: nothing waits for a recording.
 */
export function useRecordedNarration(
  lessonId: string,
  narrator: RecordedNarrator | null,
  lines: number,
): void {
  useEffect(() => {
    if (!narrator) return;
    let stopped = false;
    const urls: string[] = [];
    const handed = new Set<string>();

    const take = async (): Promise<{ lines: number; recording: boolean }> => {
      const narration = await callCore('narration.get', { path: { lesson_id: lessonId } });
      for (const line of narration.lines) {
        if (stopped) break;
        if (handed.has(line.clip)) continue;
        const clip = await callCore('narration.clip', {
          path: { lesson_id: lessonId, clip: line.clip },
        });
        if (stopped) break;
        const url = soundOf(clip);
        urls.push(url);
        handed.add(line.clip);
        narrator.add(line.text, { url, words: line.words });
      }
      return { lines: narration.lines.length, recording: narration.recording !== null };
    };

    const follow = async (): Promise<void> => {
      let found = await take();
      if (found.lines >= lines || stopped) return;
      if (!found.recording) {
        await callCore('narration.record', { path: { lesson_id: lessonId } });
      }
      while (!stopped) {
        await new Promise((resolve) => window.setTimeout(resolve, LOOK_EVERY_MS));
        if (stopped) return;
        found = await take();
        if (found.lines >= lines || !found.recording) return;
      }
    };
    // A recording that cannot be had leaves the lesson read as before: nothing to say.
    follow().catch(() => undefined);

    return () => {
      stopped = true;
      for (const url of urls) URL.revokeObjectURL(url);
    };
  }, [lessonId, narrator, lines]);
}
