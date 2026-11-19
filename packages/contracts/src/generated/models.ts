// GENERATED FILE — do not edit.
// Source: services/core (FastAPI). Regenerate with `npm run contracts`.

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
  paths: [string, ...string[]];
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
