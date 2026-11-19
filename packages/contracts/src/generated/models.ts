// GENERATED FILE — do not edit.
// Source: services/core (FastAPI). Regenerate with `npm run contracts`.

/**
 * An answer to a question. Fill in the one field that matches the question's form.
 *
 */
export interface AnswerRequest {
  covered?: string[] | null;
  hinted?: boolean;
  number?: number | null;
  option_id?: string | null;
  order?: string[] | null;
  skipped?: boolean;
  text?: string | null;
  truth?: boolean | null;
  unsure?: boolean;
}
export interface AnswerResult {
  attempt_number: number;
  change: string;
  correct_answer: string;
  correct_option: string | null;
  explanation: string;
  feedback: string | null;
  knowledge: Knowledge;
  outcome: 'correct' | 'partial' | 'incorrect' | 'skipped';
}
/**
 * What the evidence says about the learner and one concept. Deliberately no score.
 *
 */
export interface Knowledge {
  answered: number;
  label: string;
  missing: string[];
  review_due_at: string | null;
  self_report: ('new' | 'some' | 'confident') | null;
  state: 'not_assessed' | 'building' | 'needs_evidence' | 'demonstrated';
}
/**
 * One breath of narration, and what appears on screen as it starts.
 *
 */
export interface Beat {
  advance_scene?: boolean;
  show?: string | null;
  text: string;
}
export interface Concept {
  complexity: number;
  course_id: string;
  id: string;
  knowledge: Knowledge;
  layer: number | null;
  objectives: Objective[];
  origin: 'learner' | 'outline' | 'model' | 'sample';
  position: number;
  prerequisites: Prerequisite[];
  source_refs: SourceRef[];
  summary: string;
  tags: ('conceptual' | 'calculation' | 'visual' | 'procedural')[];
  title: string;
}
export interface Objective {
  id: string;
  statement: string;
}
export interface Prerequisite {
  concept_id: string;
  reason: string;
  title: string;
}
export interface SourceRef {
  id: number;
  page_number: number | null;
  section_id: string;
  section_title: string | null;
  source_id: string;
  source_name: string;
}
export interface ConceptCreate {
  /**
   * @maxItems 12
   */
  objectives?: string[];
  summary?: string;
  title: string;
}
export interface ConceptEvidence {
  concept_id: string;
  history: ObservationSummary[];
  knowledge: Knowledge;
}
export interface ObservationSummary {
  explanation: string;
  id: number;
  kind: 'answer' | 'self_report';
  occurred_at: string;
  state_after: 'not_assessed' | 'building' | 'needs_evidence' | 'demonstrated';
  state_before: 'not_assessed' | 'building' | 'needs_evidence' | 'demonstrated';
}
export interface ConceptOrder {
  /**
   * @maxItems 200
   */
  concept_ids: string[];
}
export interface ConceptUpdate {
  complexity?: number | null;
  summary?: string | null;
  tags?: ('conceptual' | 'calculation' | 'visual' | 'procedural')[] | null;
  title?: string | null;
}
export interface Course {
  created_at: string;
  description: string;
  id: string;
  last_opened_at: string | null;
  origin: 'sample' | 'topic' | 'materials';
  source_count: number;
  title: string;
  topic: string | null;
  updated_at: string;
}
export interface CourseCreate {
  description?: string;
  origin: 'topic' | 'materials';
  title: string;
  topic?: string | null;
}
export interface CourseList {
  courses: Course[];
}
export interface CourseUpdate {
  description?: string | null;
  title?: string | null;
}
export interface Curriculum {
  concepts: Concept[];
  course_id: string;
  issues: CurriculumIssue[];
  learning_order: string[];
  startable: boolean;
}
export interface CurriculumIssue {
  code: string;
  concept_ids: string[];
  message: string;
  severity: 'error' | 'warning';
}
export interface ErrorBody {
  code: string;
  detail?: unknown;
  message: string;
  retry_after_seconds?: number | null;
}
export interface ErrorResponse {
  error: ErrorBody;
}
/**
 * Narration with key points on the board, and optionally a scene beside it.
 *
 */
export interface ExplanationSegment {
  estimated_seconds: number;
  id: string;
  /**
   * @minItems 1
   * @maxItems 12
   */
  narration: Beat[];
  scene?: SceneRef | null;
  title: string;
  type: 'explanation';
}
export interface SceneRef {
  fallback_text: string;
  scene_id: string;
}
export interface Health {
  api_version: string;
  status: string;
  version: string;
}
export interface HighlightSegment {
  highlighted: boolean;
  text: string;
}
/**
 * Absolute paths chosen by the learner. Only the desktop shell may send this.
 *
 */
export interface ImportRequest {
  /**
   * @minItems 1
   * @maxItems 50
   */
  paths: string[];
}
/**
 * A scene the learner manipulates. Understandable without touching it.
 *
 */
export interface InteractionSegment {
  estimated_seconds: number;
  id: string;
  /**
   * @maxItems 12
   */
  narration?: Beat[];
  prompt: string;
  scene: SceneRef;
  title: string;
  type: 'interaction';
}
export interface Job {
  course_id: string | null;
  error_code: string | null;
  error_message: string | null;
  id: string;
  kind: string;
  progress_done: number;
  progress_message: string;
  progress_total: number;
  result: unknown;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
}
export interface LearnerPreferences {
  captions: boolean;
  explanation_density: 'concise' | 'balanced' | 'detailed';
  goal: string;
  narration: boolean;
  pace: 'relaxed' | 'standard' | 'brisk';
}
export interface LearnerPreferencesUpdate {
  captions?: boolean | null;
  explanation_density?: ('concise' | 'balanced' | 'detailed') | null;
  goal?: string | null;
  narration?: boolean | null;
  pace?: ('relaxed' | 'standard' | 'brisk') | null;
}
/**
 * Everything the player needs: the validated lesson and the scenes it plays.
 *
 */
export interface LessonForPlayer {
  lesson: PlayerLesson;
  origin: 'sample' | 'generated';
  progress: LessonProgress;
  scenes: SceneArtifact[];
}
export interface PlayerLesson {
  concept_ids: string[];
  course_id: string;
  estimated_minutes: number;
  grounding: 'materials' | 'general_knowledge' | 'sample';
  lesson_id: string;
  objectives: LessonObjective[];
  schema_version: '1.0';
  segments: (
    | ExplanationSegment
    | VisualizationSegment
    | InteractionSegment
    | PlayerCheckpointSegment
    | WorkedExampleSegment
    | ReflectionSegment
    | SummarySegment
  )[];
  source_refs: SourceCitation[];
  strategy: 'visual' | 'worked_example' | 'analogy' | 'mathematical' | 'socratic' | 'computational';
  title: string;
}
export interface LessonObjective {
  objective_id?: string | null;
  statement: string;
}
/**
 * An animation, narrated.
 *
 */
export interface VisualizationSegment {
  estimated_seconds: number;
  id: string;
  /**
   * @minItems 1
   * @maxItems 12
   */
  narration: Beat[];
  scene: SceneRef;
  title: string;
  type: 'visualization';
}
export interface PlayerCheckpointSegment {
  estimated_seconds: number;
  id: string;
  /**
   * @maxItems 12
   */
  narration?: Beat[];
  question: PlayerQuestion;
  title: string;
  type: 'checkpoint';
}
/**
 * A question as the learner sees it before answering.
 *
 */
export interface PlayerQuestion {
  concept_id: string;
  difficulty: number;
  form:
    | 'multiple_choice'
    | 'true_false'
    | 'numeric'
    | 'short_answer'
    | 'ordering'
    | 'prediction'
    | 'explanation';
  hint?: string | null;
  id: string;
  is_transfer: boolean;
  options?: PlayerOption[];
  rubric?: PlayerRubricPoint[];
  sample_answer?: string | null;
  stem: string;
  unit?: string | null;
}
export interface PlayerOption {
  id: string;
  text: string;
}
export interface PlayerRubricPoint {
  id: string;
  text: string;
}
/**
 * A problem solved step by step: each beat says a step and shows it.
 *
 */
export interface WorkedExampleSegment {
  estimated_seconds: number;
  id: string;
  /**
   * @minItems 1
   * @maxItems 12
   */
  narration: Beat[];
  problem: string;
  scene?: SceneRef | null;
  title: string;
  type: 'worked_example';
}
/**
 * A question to think about. Not scored; the learner may write a note or move on.
 *
 */
export interface ReflectionSegment {
  estimated_seconds: number;
  id: string;
  /**
   * @maxItems 12
   */
  narration?: Beat[];
  prompt: string;
  title: string;
  type: 'reflection';
}
export interface SummarySegment {
  estimated_seconds: number;
  id: string;
  /**
   * @minItems 1
   * @maxItems 12
   */
  narration: Beat[];
  title: string;
  type: 'summary';
}
/**
 * A place in the learner's materials that the lesson draws on.
 *
 */
export interface SourceCitation {
  locator: string;
  section_id: string;
  source_id: string;
  source_name: string;
}
export interface LessonProgress {
  completed: boolean;
  position: number;
  started: boolean;
}
/**
 * One complete Wanim scene file, with what the static policy found in it.
 *
 */
export interface SceneArtifact {
  content_hash: string;
  /**
   * @maxItems 16
   */
  controls?: string[];
  /**
   * @maxItems 3
   */
  events?: ('passed' | 'explored' | 'progress')[];
  id: string;
  interactive: boolean;
  purpose: string;
  scene_class: string;
  source: string;
  wanim_version: string;
}
export interface LessonList {
  lessons: LessonSummary[];
}
export interface LessonSummary {
  concept_id: string;
  course_id: string;
  estimated_minutes: number;
  id: string;
  origin: 'sample' | 'generated';
  progress: LessonProgress;
  segment_count: number;
  title: string;
}
export interface LessonProgressUpdate {
  completed?: boolean;
  position: number;
}
export interface ObjectiveInput {
  id?: string | null;
  statement: string;
}
export interface ObjectivesUpdate {
  /**
   * @maxItems 12
   */
  objectives: ObjectiveInput[];
}
export interface OutlineCandidate {
  section_id: string;
  source_id: string;
  source_name: string;
  title: string;
}
export interface OutlineCandidates {
  candidates: OutlineCandidate[];
}
export interface OutlineSelection {
  /**
   * @minItems 1
   * @maxItems 40
   */
  section_ids: string[];
}
export interface Passage {
  chunk_id: number;
  page_number: number | null;
  section_id: string;
  section_title: string | null;
  source_id: string;
  source_name: string;
  text: string;
}
export interface Passages {
  passages: Passage[];
}
export interface PrerequisiteInput {
  concept_id: string;
  reason?: string;
}
export interface PrerequisitesUpdate {
  /**
   * @maxItems 12
   */
  prerequisites: PrerequisiteInput[];
}
export interface ProviderCredential {
  api_key: string;
}
export interface ProviderStatus {
  base_url: string;
  display_name: string;
  key_configured: boolean;
  model: string;
  provider_id: string;
}
export interface SearchHit {
  chunk_id: number;
  excerpt: HighlightSegment[];
  page_number: number | null;
  section_title: string | null;
  source_id: string;
  source_name: string;
}
export interface SearchResults {
  hits: SearchHit[];
  query: string;
}
export interface SelfRating {
  level: 'new' | 'some' | 'confident';
}
export interface Source {
  char_count: number;
  chunk_count: number;
  course_id: string;
  created_at: string;
  display_name: string;
  id: string;
  kind: 'pdf' | 'docx' | 'markdown' | 'text' | 'authored';
  page_count: number;
  section_count: number;
  size_bytes: number;
  status: 'extracted' | 'needs_attention';
  warnings: string[];
}
export interface SourceDetail {
  sections: SourceSection[];
  source: Source;
}
export interface SourceSection {
  char_count: number;
  confidence: number;
  id: string;
  kind: 'document' | 'page' | 'heading';
  level: number | null;
  ordinal: number;
  page_number: number | null;
  title: string | null;
}
export interface SourceList {
  sources: Source[];
}
export interface SourceRefCreate {
  section_id: string;
}
