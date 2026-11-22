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
  /** The scene is holding: on a live page, or at the end of a slide's step. */
  holding: boolean;
  /** The last step of a slide that has taken a cue: it takes no second one. */
  taken: number;
}

/**
 * Carries cues from the narration to whichever scene is on screen.
 *
 * The two are not in step: the narration can reach its cue while the scene is
 * still loading, or before the interface has even shown the new segment, and a
 * slide (ADR-049) can still be drawing one step when the words of the next are
 * said. So cues are counted, by segment, and each is given to that segment's
 * scene when it is next holding: one cue, one step. A cue is delivered at most
 * once, and never to another segment.
 */
export class SceneCues {
  private pendingFor: string | null = null;
  /** How many cues the segment's scene has still to take. */
  private pending = 0;
  private attached: Attached | null = null;

  /** A scene is on screen for this segment. Returns how to take it away again. */
  attach(segmentId: string, controls: SceneControls): () => void {
    const entry: Attached = { segmentId, controls, holding: false, taken: -1 };
    this.attached = entry;
    return () => {
      if (this.attached !== entry) return;
      this.attached = null;
      // A cue the scene never took does not wait for the next visit.
      if (this.pendingFor === segmentId) this.clear();
    };
  }

  /**
   * The scene of this segment says whether it is holding: on a live page, or, for a slide,
   * at the end of step `step`. A step that has taken its cue is not held at again.
   */
  setHolding(segmentId: string, holding: boolean, step?: number): void {
    if (this.attached?.segmentId !== segmentId) return;
    if (step !== undefined && step <= this.attached.taken) return;
    this.attached.holding = holding;
    this.deliver(step);
  }

  /** The narration has reached the point where this segment's scene should move on. */
  advance(segmentId: string): void {
    if (this.pendingFor !== segmentId) this.pending = 0;
    this.pendingFor = segmentId;
    this.pending += 1;
    this.deliver();
  }

  /** Run the scene on screen again from its start, as when a segment is replayed. */
  restart(): void {
    if (!this.attached) return;
    this.clear();
    this.attached.holding = false;
    this.attached.taken = -1;
    this.attached.controls.reset();
  }

  private clear(): void {
    this.pendingFor = null;
    this.pending = 0;
  }

  private deliver(step?: number): void {
    const scene = this.attached;
    if (!scene?.holding || scene.segmentId !== this.pendingFor || this.pending === 0) return;
    this.pending -= 1;
    if (this.pending === 0) this.pendingFor = null;
    scene.holding = false;
    if (step !== undefined) scene.taken = step;
    scene.controls.next();
  }
}
