// GENERATED FILE — do not edit.
// Source: services/core (FastAPI). Regenerate with `npm run contracts`.

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
