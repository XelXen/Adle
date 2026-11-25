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
 * A question the learner asked about a part of a lesson, and the answer.
 *
 */
export interface Ask {
  citations: AskCitation[];
  created_at: string;
  id: string;
  lesson_id: string;
  paragraphs: string[];
  picture?: AskPicture | null;
  question: string;
  segment_id: string;
  written_by: WrittenBy;
}
export interface AskCitation {
  locator: string;
  source_name: string;
}
/**
 * The part's picture, drawn again because the learner asked (ADR-067).
 *
 */
export interface AskPicture {
  description: string;
  state: 'offered' | 'in_use';
}
/**
 * Who wrote something a model wrote.
 *
 */
export interface WrittenBy {
  authors?: Author[];
  models?: string[];
  note?: string;
  provider?: string;
}
export interface Author {
  model: string;
  provider: string;
}
export interface AskList {
  asks: Ask[];
  limit: number;
}
/**
 * Something the learner wants to ask about one part of a lesson.
 *
 */
export interface AskRequest {
  question: string;
  redraw?: boolean;
  segment_id: string;
}
/**
 * One breath of narration, and what appears on screen as it starts.
 *
 */
export interface Beat {
  advance_scene?: boolean;
  /**
   * @maxItems 12
   */
  cues?: number[];
  show?: string | null;
  text: string;
}
export interface BroughtInCourse {
  concepts: number;
  course_id: string;
  lessons: number;
  lessons_left_out: number;
  materials: number;
  notes: number;
  progress: boolean;
  title: string;
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
  kind: 'answer' | 'self_report' | 'dismissal';
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
export interface ConceptProgress {
  concept_id: string;
  fresh_questions: number;
  hypotheses: Hypothesis[];
  knowledge: Knowledge;
  lessons_completed: number;
  lessons_total: number;
  next_fresh_at: string | null;
  review_due: boolean;
  title: string;
}
/**
 * A possible explanation for a pattern of answers. A hypothesis, never a verdict.
 *
 */
export interface Hypothesis {
  can_dismiss: boolean;
  description: string;
  is_slip: boolean;
  kind:
    | 'prerequisite_gap'
    | 'definition_confusion'
    | 'notation_confusion'
    | 'procedure_order'
    | 'causal_confusion'
    | 'arithmetic_slip'
    | 'misread_question'
    | 'overgeneralization';
  status: 'tentative' | 'supported' | 'rejected' | 'resolved';
}
export interface ConceptUpdate {
  complexity?: number | null;
  summary?: string | null;
  tags?: ('conceptual' | 'calculation' | 'visual' | 'procedural')[] | null;
  title?: string | null;
}
export interface CopyDestination {
  path: string;
}
/**
 * What the core keeps of the learner's settings, as a file holds it.
 *
 */
export interface CoreSettings {
  learning: {
    [k: string]: unknown | undefined;
  };
  voice: {
    [k: string]: unknown | undefined;
  };
}
export interface Course {
  brought_in?: boolean;
  concept_count: number;
  created_at: string;
  description: string;
  id: string;
  last_opened_at: string | null;
  named_by_adle?: boolean;
  origin: 'sample' | 'topic' | 'materials';
  source_count: number;
  subject?:
    | 'mathematics'
    | 'physics'
    | 'chemistry'
    | 'biology'
    | 'earth_science'
    | 'computer_science'
    | 'language'
    | 'literature'
    | 'history'
    | 'economics'
    | 'social_science'
    | 'arts'
    | 'general';
  subject_by_adle?: boolean;
  title: string;
  topic: string | null;
  updated_at: string;
}
export interface CourseCreate {
  description?: string;
  origin: 'topic' | 'materials';
  title?: string | null;
  topic?: string | null;
}
export interface CourseFileCounts {
  concepts: number;
  files: number;
  lessons: number;
  materials: number;
  notes: number;
  progress: boolean;
}
/**
 * What goes into a file, or is brought in from one. The curriculum always is.
 *
 */
export interface CourseFileHolds {
  lessons?: boolean;
  materials?: boolean;
  notes?: boolean;
  progress?: boolean;
}
export interface CourseFilePath {
  path: string;
}
export interface CourseFileRequest {
  holds?: CourseFileHolds | null;
  kind: 'template' | 'transfer';
}
/**
 * What a file says it is, for asking the learner before anything is brought in.
 *
 */
export interface CourseFileSummary {
  counts: CourseFileCounts;
  kind: 'template' | 'transfer';
  made_at: string;
  made_by: string;
  title: string;
}
export interface CourseFileToBringIn {
  holds: CourseFileHolds;
  path: string;
}
export interface CourseFilm {
  film: Film | null;
  plan: FilmPlanOut;
}
export interface Film {
  chapters: FilmChapter[];
  created_at: string | null;
  finished_at: string | null;
  id: string;
  making: Job | null;
  notes: string[];
  reason: string | null;
  seconds: number | null;
  size: number | null;
  status: 'making' | 'unfinished' | 'ready';
  title: string;
  voice: string | null;
  written_by: {
    [k: string]: unknown | undefined;
  };
}
export interface FilmChapter {
  problems: number;
  start: number | null;
  state: 'waiting' | 'written' | 'in_words';
  title: string;
}
export interface Job {
  course_id: string | null;
  created_at?: string | null;
  error_code: string | null;
  error_message: string | null;
  id: string;
  kind: string;
  progress_detail?: JobProgressDetail | null;
  progress_done: number;
  progress_message: string;
  progress_total: number;
  result: unknown;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  subject_id: string | null;
}
/**
 * What long work is doing just now, for a learner who is waiting for it.
 *
 * Nothing here is the answer itself: a stage, and the titles of what has been written.
 *
 */
export interface JobProgressDetail {
  outline?: string[];
  stage?: ('waiting' | 'thinking' | 'writing' | 'drawing' | 'voicing') | null;
  title?: string | null;
}
/**
 * What a film of the course would be, before it is begun or continued.
 *
 */
export interface FilmPlanOut {
  blocked: string | null;
  chapters: string[];
  checks_pictures: boolean;
  requests_at_most: number;
  voice: string | null;
}
export interface CourseList {
  courses: Course[];
}
export interface CourseUpdate {
  description?: string | null;
  subject?:
    | (
        | 'mathematics'
        | 'physics'
        | 'chemistry'
        | 'biology'
        | 'earth_science'
        | 'computer_science'
        | 'language'
        | 'literature'
        | 'history'
        | 'economics'
        | 'social_science'
        | 'arts'
        | 'general'
      )
    | 'auto'
    | null;
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
export interface FilmCaptions {
  cues: FilmCue[];
}
export interface FilmCue {
  end: number;
  start: number;
  text: string;
}
/**
 * Whether the film maker is on this computer, and what setting it up takes.
 *
 */
export interface FilmMakerStatus {
  borrowed: boolean;
  download_bytes: number;
  fits: boolean;
  installed_bytes: number;
  ready: boolean;
  setting_up: Job | null;
  sources: string[];
}
/**
 * A part of a film's video, for the page to put together and play.
 *
 */
export interface FilmVideoPart {
  data: string;
  mime: 'video/mp4';
  part: number;
  parts: number;
  size: number;
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
export interface JobList {
  jobs: Job[];
}
export interface LatestJob {
  job: Job | null;
}
export interface LearnerPreferences {
  captions: boolean;
  explanation_density: 'concise' | 'balanced' | 'detailed';
  goal: string;
  narration: boolean;
  pace: 'relaxed' | 'standard' | 'brisk';
  voice: string;
  volume: number;
}
export interface LearnerPreferencesUpdate {
  captions?: boolean | null;
  explanation_density?: ('concise' | 'balanced' | 'detailed') | null;
  goal?: string | null;
  narration?: boolean | null;
  pace?: ('relaxed' | 'standard' | 'brisk') | null;
  voice?: string | null;
  volume?: number | null;
}
export interface LearningOverview {
  concepts: ConceptProgress[];
  course_id: string;
  plan: LearningPlan;
  session: SessionSummary | null;
  summary: ProgressSummary;
}
export interface LearningPlan {
  alternatives: NextStep[];
  note: string | null;
  recommended: NextStep;
}
/**
 * Something worth doing now, with the reason for it. Never an instruction.
 *
 */
export interface NextStep {
  about:
    | (
        | 'prerequisite_gap'
        | 'definition_confusion'
        | 'notation_confusion'
        | 'procedure_order'
        | 'causal_confusion'
        | 'arithmetic_slip'
        | 'misread_question'
        | 'overgeneralization'
      )
    | null;
  concept_id: string | null;
  kind:
    | 'add_concepts'
    | 'resume_lesson'
    | 'revisit_prerequisite'
    | 'check'
    | 'another_explanation'
    | 'review'
    | 'practise'
    | 'start_lesson'
    | 'repeat_lesson'
    | 'create_lesson'
    | 'nothing_due';
  lesson_id: string | null;
  needs_key: boolean;
  reason: string;
  title: string;
}
/**
 * The latest sitting on a course and what it showed.
 *
 * A sitting is a run of activity with no long pause in it. Nobody starts or ends one;
 * it is read off the record. Counts of answers and words for states: never a score.
 *
 */
export interface SessionSummary {
  answered: number;
  current: boolean;
  ended_at: string;
  lessons_completed: number;
  reviews: SessionReview[];
  shown: SessionShown[];
  started_at: string;
  still_needed: SessionStillNeeded[];
}
export interface SessionReview {
  concept_id: string;
  due_at: string;
  title: string;
}
export interface SessionShown {
  concept_id: string;
  demonstrated: boolean;
  right: number;
  right_unaided: number;
  title: string;
}
export interface SessionStillNeeded {
  concept_id: string;
  label: string;
  missing: string[];
  title: string;
}
/**
 * Counts of concepts by what the evidence says. Counts of states, never a score.
 *
 */
export interface ProgressSummary {
  concepts: number;
  demonstrated: number;
  in_progress: number;
  next_review_at: string | null;
  not_assessed: number;
  reviews_due: number;
}
/**
 * Who wrote a lesson, by the names they went by when it was written.
 *
 */
export interface LessonAuthor {
  models: string[];
  note: string;
  provider: string;
}
/**
 * Everything the player needs: the validated lesson and the scenes it plays.
 *
 */
export interface LessonForPlayer {
  lesson: PlayerLesson;
  origin: 'sample' | 'generated';
  pending_scene_ids?: string[];
  progress: LessonProgress;
  scenes: SceneArtifact[];
  unhelpful_parts?: string[];
  writing?: boolean;
  written_by?: LessonAuthor | null;
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
 * A problem solved step by step: each beat says a step and shows it, on the board or
 * in its picture (a slide that grows with the solution, ADR-049).
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
/**
 * The key points, shown on the board or in a picture that brings them back (ADR-049).
 *
 */
export interface SummarySegment {
  estimated_seconds: number;
  id: string;
  /**
   * @minItems 1
   * @maxItems 12
   */
  narration: Beat[];
  scene?: SceneRef | null;
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
   * @maxItems 5
   */
  events?: ('passed' | 'explored' | 'progress' | 'step' | 'layout')[];
  id: string;
  interactive: boolean;
  purpose: string;
  scene_class: string;
  source: string;
  steps?: number;
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
  pictures_pending?: number;
  progress: LessonProgress;
  segment_count: number;
  title: string;
  writing?: boolean;
}
export interface LessonProgressUpdate {
  completed?: boolean;
  position: number;
}
/**
 * How the learner would like a new lesson to teach, when they have a preference.
 *
 */
export interface LessonRequest {
  strategy?:
    | ('visual' | 'worked_example' | 'analogy' | 'mathematical' | 'socratic' | 'computational')
    | null;
}
/**
 * How Adle forms a lesson (ADR-061): the rules of every lesson, in the order a lesson
 * obeys them, and what each subject needs besides.
 *
 */
export interface LessonRules {
  rules: string[];
  subjects: SubjectWay[];
}
/**
 * One kind of subject, and how a lesson of it goes.
 *
 */
export interface SubjectWay {
  key:
    | 'mathematics'
    | 'physics'
    | 'chemistry'
    | 'biology'
    | 'earth_science'
    | 'computer_science'
    | 'language'
    | 'literature'
    | 'history'
    | 'economics'
    | 'social_science'
    | 'arts'
    | 'general';
  name: string;
  steps: string[];
  strategies: (
    'visual' | 'worked_example' | 'analogy' | 'mathematical' | 'socratic' | 'computational'
  )[];
}
/**
 * What of a lesson has been recorded in the voice chosen now, and the recording under way.
 *
 */
export interface Narration {
  lines: NarrationLine[];
  recording: Job | null;
}
export interface NarrationLine {
  clip: string;
  seconds: number;
  text: string;
  words: NarrationWord[];
}
export interface NarrationWord {
  end: number;
  index: number;
  length: number;
  start: number;
}
export interface NarrationClip {
  data: string;
  mime: string;
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
export interface PracticeQuestion {
  lesson_id: string;
  question: PlayerQuestion;
}
export interface PracticeRequest {
  about?:
    | (
        | 'prerequisite_gap'
        | 'definition_confusion'
        | 'notation_confusion'
        | 'procedure_order'
        | 'causal_confusion'
        | 'arithmetic_slip'
        | 'misread_question'
        | 'overgeneralization'
      )
    | null;
  count?: number;
}
export interface PracticeSet {
  concept_id: string;
  concept_title: string;
  course_id: string;
  next_fresh_at: string | null;
  purpose: 'review' | 'check' | 'practise';
  questions: PracticeQuestion[];
  reason: string;
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
/**
 * Which concepts of a proposal to add, by their position in it.
 *
 */
export interface ProposalAcceptance {
  /**
   * @minItems 1
   * @maxItems 40
   */
  selected: number[];
}
export interface ProposalRequest {
  setup?: boolean;
}
export interface ProviderCheck {
  provider_id: string;
}
/**
 * One provider there is.
 *
 */
export interface ProviderChoice {
  base_url: string;
  display_name: string;
  first_for: (
    'ask' | 'curriculum' | 'lesson' | 'scene' | 'check' | 'read' | 'film' | 'storyboard'
  )[];
  in_use: boolean;
  key_configured: boolean;
  limits_published: boolean;
  models: ProviderModel[];
  provider_id: string;
  reads_pictures: boolean;
  selected: boolean;
  usage: ProviderUsage;
}
export interface ProviderModel {
  id: string;
  name: string;
}
/**
 * Adle's own count of today's requests to one provider.
 *
 * An estimate: the provider keeps the real one.
 *
 */
export interface ProviderUsage {
  limits_published: boolean;
  provider_id: string;
  requests_last_minute: number;
  requests_per_day: number;
  requests_per_minute: number;
  requests_today: number;
  resets_at: string;
  tokens_per_day: number;
  tokens_today: number;
}
export interface ProviderCredential {
  api_key: string;
  provider_id?: string | null;
}
/**
 * Where one kind of request would go at this moment, and how long it may take.
 *
 */
export interface ProviderRoute {
  model_name: string;
  names: string[];
  provider_ids: string[];
  reason: string;
  sentence: string;
  wait_measured: boolean;
  wait_seconds: number;
}
/**
 * Where each kind of request would go. Read just before saying where one will go.
 *
 */
export interface ProviderRoutes {
  ask: ProviderRoute;
  curriculum: ProviderRoute;
  film: ProviderRoute;
  lesson: ProviderRoute;
  read: ProviderRoute;
  scene: ProviderRoute;
  storyboard: ProviderRoute;
}
export interface ProviderSelection {
  selection: string;
}
/**
 * The learner's choice, every provider there is, and where requests would go.
 *
 */
export interface ProviderStatus {
  base_url: string;
  display_name: string;
  key_configured: boolean;
  model: string;
  model_name: string;
  provider_id: string;
  providers: ProviderChoice[];
  routes: ProviderRoutes;
  selection: string;
}
export interface SavedCourseFile {
  counts: CourseFileCounts;
  lessons_left_out: number;
  name: string;
  suggested_name: string;
}
/**
 * A film written for the desktop shell to move where the learner chose.
 *
 */
export interface SavedFilmFile {
  captions_name: string | null;
  file_name: string;
  suggested_name: string;
}
/**
 * A picture to try in the player before a learner is shown it (ADR-038).
 *
 */
export interface SceneTrial {
  controls: string[];
  id: string;
  interactive: boolean;
  scene_class: string;
  source: string;
  steps?: number;
}
export interface SceneTrialList {
  trials: SceneTrial[];
}
/**
 * How a trial went. ``passed``, or where it failed and what the player said.
 *
 */
export interface SceneTrialReport {
  message?: string;
  passed: boolean;
  stage?: ('boot' | 'compile' | 'runtime' | 'timeout' | 'unresponsive' | 'controls') | null;
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
export interface SettingsBroughtIn {
  notes: string[];
  setting_up: Job | null;
}
export interface SettingsLookedAt {
  voice: VoicePlan | null;
}
/**
 * What bringing a file's voice in would do on this computer.
 *
 */
export interface VoicePlan {
  download_bytes: number;
  name: string | null;
  note: string;
  set_up: boolean;
  sources: string[];
  tier: ('kokoro' | 'expressive') | null;
}
export interface SettingsToBringIn {
  learning?: {
    [k: string]: unknown | undefined;
  } | null;
  set_up_voice?: boolean;
  voice?: {
    [k: string]: unknown | undefined;
  } | null;
}
export interface SettingsToLookAt {
  voice?: {
    [k: string]: unknown | undefined;
  } | null;
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
  picture_pages: number[];
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
/**
 * The learner says a part of a lesson did not help.
 *
 */
export interface UnhelpfulReport {
  segment_id: string;
}
export interface VoiceChoice {
  design?: string | null;
  enabled?: boolean | null;
  parts?: {
    [k: string]: string | undefined;
  } | null;
  speaker?: string | null;
  tier?: ('kokoro' | 'expressive') | null;
}
/**
 * The description a voice of some parts is made from.
 *
 */
export interface VoiceDescription {
  text: string;
}
export interface VoiceDescriptionRequest {
  parts: {
    [k: string]: string | undefined;
  };
}
export interface VoiceDesignOption {
  key: string;
  name: string;
}
/**
 * One thing about a voice a learner can choose: who speaks, how fast, and so on.
 *
 */
export interface VoiceDesignPart {
  key: string;
  name: string;
  options: VoiceDesignOption[];
}
/**
 * A voice to start from: a choice of parts, and the description they make.
 *
 */
export interface VoiceDesignPreset {
  name: string;
  parts: {
    [k: string]: string | undefined;
  };
  text: string;
}
/**
 * A lesson being recorded in the voice chosen now (ADR-057).
 *
 */
export interface VoiceRecording {
  done: number;
  lesson_id: string;
  title: string;
  total: number;
}
/**
 * A few words in a voice set up here: a speaker of a size, or the Expressive voice of a
 * description or of parts (the one chosen when neither is given).
 *
 */
export interface VoiceSampleRequest {
  design?: string | null;
  parts?: {
    [k: string]: string | undefined;
  } | null;
  speaker?: string | null;
  tier: 'kokoro' | 'expressive';
}
export interface VoiceSetup {
  tier: 'kokoro' | 'expressive';
}
export interface VoiceSpeaker {
  description: string;
  id: string;
  name: string;
}
export interface VoiceStatus {
  borrowed: boolean;
  design: string;
  design_choices: VoiceDesignPart[];
  design_parts: {
    [k: string]: string | undefined;
  };
  design_presets: VoiceDesignPreset[];
  enabled: boolean;
  gpu: string | null;
  recommended: ('kokoro' | 'expressive') | null;
  recording: VoiceRecording[];
  setting_up: Job | null;
  speakers: {
    [k: string]: string | undefined;
  };
  tier: ('kokoro' | 'expressive') | null;
  tiers: VoiceTier[];
}
/**
 * One size of natural voice, from the lightest (Kokoro) to the richest (Qwen3-TTS 1.7B).
 *
 */
export interface VoiceTier {
  description: string;
  fits: boolean;
  id: 'kokoro' | 'expressive';
  min_memory_gb: number | null;
  model_bytes: number;
  name: string;
  program_bytes: number;
  ready: boolean;
  sources: string[];
  speakers: VoiceSpeaker[];
  speed?: ('faster' | 'slower') | null;
  why: string;
}
