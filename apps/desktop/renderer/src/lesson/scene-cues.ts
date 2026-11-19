/** What the lesson can ask of the scene that is on screen. */
export interface SceneControls {
  /** Leave the live page the scene is holding on, and play what follows. */
  next: () => void;
  /** Run the scene again from its start. */
  reset: () => void;
}

interface Attached {
  segmentId: string;
  controls: SceneControls;
  /** The scene is holding on a live page that `next` would leave. */
  holding: boolean;
}

/**
 * Carries cues from the narration to whichever scene is on screen.
 *
 * The two are not in step: the narration can reach its cue while the scene is
 * still loading, or before the interface has even shown the new segment. So a
 * cue is remembered, by segment, until that segment's scene is holding and can
 * take it. A cue is delivered at most once, and never to another segment.
 */
export class SceneCues {
  private pendingFor: string | null = null;
  private attached: Attached | null = null;

  /** A scene is on screen for this segment. Returns how to take it away again. */
  attach(segmentId: string, controls: SceneControls): () => void {
    const entry: Attached = { segmentId, controls, holding: false };
    this.attached = entry;
    return () => {
      if (this.attached !== entry) return;
      this.attached = null;
      // A cue the scene never took does not wait for the next visit.
      if (this.pendingFor === segmentId) this.pendingFor = null;
    };
  }

  /** The scene of this segment says whether it is holding on a live page. */
  setHolding(segmentId: string, holding: boolean): void {
    if (this.attached?.segmentId !== segmentId) return;
    this.attached.holding = holding;
    this.deliver();
  }

  /** The narration has reached the point where this segment's scene should move on. */
  advance(segmentId: string): void {
    this.pendingFor = segmentId;
    this.deliver();
  }

  /** Run the scene on screen again from its start, as when a segment is replayed. */
  restart(): void {
    if (!this.attached) return;
    this.attached.holding = false;
    this.attached.controls.reset();
  }

  private deliver(): void {
    const scene = this.attached;
    if (!scene?.holding || scene.segmentId !== this.pendingFor) return;
    this.pendingFor = null;
    scene.holding = false;
    scene.controls.next();
  }
}
