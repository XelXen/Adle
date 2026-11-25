// GENERATED FILE — do not edit.
// Source: services/core (FastAPI). Regenerate with `npm run contracts`.

import type {
  AnswerRequest,
  AnswerResult,
  AskList,
  AskRequest,
  BroughtInCourse,
  ConceptCreate,
  ConceptEvidence,
  ConceptOrder,
  ConceptUpdate,
  CopyDestination,
  CoreSettings,
  Course,
  CourseCreate,
  CourseFilePath,
  CourseFileRequest,
  CourseFileSummary,
  CourseFileToBringIn,
  CourseFilm,
  CourseList,
  CourseUpdate,
  Curriculum,
  FilmCaptions,
  FilmMakerStatus,
  FilmVideoPart,
  Health,
  ImportRequest,
  Job,
  JobList,
  LatestJob,
  LearnerPreferences,
  LearnerPreferencesUpdate,
  LearningOverview,
  LessonForPlayer,
  LessonList,
  LessonProgress,
  LessonProgressUpdate,
  LessonRequest,
  LessonRules,
  Narration,
  NarrationClip,
  ObjectivesUpdate,
  OutlineCandidates,
  OutlineSelection,
  Passages,
  PracticeRequest,
  PracticeSet,
  PrerequisitesUpdate,
  ProposalAcceptance,
  ProposalRequest,
  ProviderCheck,
  ProviderCredential,
  ProviderSelection,
  ProviderStatus,
  ProviderUsage,
  SavedCourseFile,
  SavedFilmFile,
  SceneTrialList,
  SceneTrialReport,
  SearchResults,
  SelfRating,
  SettingsBroughtIn,
  SettingsLookedAt,
  SettingsToBringIn,
  SettingsToLookAt,
  SourceDetail,
  SourceList,
  SourceRefCreate,
  UnhelpfulReport,
  VoiceChoice,
  VoiceDescription,
  VoiceDescriptionRequest,
  VoiceSampleRequest,
  VoiceSetup,
  VoiceStatus,
} from './models';

/**
 * Every operation the core exposes. `internal` operations may only be called by the
 * Electron main process; the renderer bridge refuses them.
 */
export const OPERATIONS = {
  'courses.bring_in_file': { method: 'POST', path: '/v1/course-files/bring-in', internal: true },
  'courses.create': { method: 'POST', path: '/v1/courses', internal: false },
  'courses.delete': { method: 'DELETE', path: '/v1/courses/{course_id}', internal: false },
  'courses.get': { method: 'GET', path: '/v1/courses/{course_id}', internal: false },
  'courses.install_sample': { method: 'POST', path: '/v1/courses/sample', internal: false },
  'courses.list': { method: 'GET', path: '/v1/courses', internal: false },
  'courses.look_at_file': { method: 'POST', path: '/v1/course-files/look', internal: true },
  'courses.save_file': { method: 'POST', path: '/v1/courses/{course_id}/file', internal: true },
  'courses.update': { method: 'PATCH', path: '/v1/courses/{course_id}', internal: false },
  'curriculum.add_from_outline': {
    method: 'POST',
    path: '/v1/courses/{course_id}/outline',
    internal: false,
  },
  'curriculum.add_source_ref': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/source-refs',
    internal: false,
  },
  'curriculum.create_concept': {
    method: 'POST',
    path: '/v1/courses/{course_id}/concepts',
    internal: false,
  },
  'curriculum.delete_concept': {
    method: 'DELETE',
    path: '/v1/concepts/{concept_id}',
    internal: false,
  },
  'curriculum.get': { method: 'GET', path: '/v1/courses/{course_id}/curriculum', internal: false },
  'curriculum.outline_candidates': {
    method: 'GET',
    path: '/v1/courses/{course_id}/outline',
    internal: false,
  },
  'curriculum.related_passages': {
    method: 'GET',
    path: '/v1/concepts/{concept_id}/passages',
    internal: false,
  },
  'curriculum.remove_source_ref': {
    method: 'DELETE',
    path: '/v1/concepts/{concept_id}/source-refs/{ref_id}',
    internal: false,
  },
  'curriculum.reorder': {
    method: 'PUT',
    path: '/v1/courses/{course_id}/concept-order',
    internal: false,
  },
  'curriculum.set_objectives': {
    method: 'PUT',
    path: '/v1/concepts/{concept_id}/objectives',
    internal: false,
  },
  'curriculum.set_prerequisites': {
    method: 'PUT',
    path: '/v1/concepts/{concept_id}/prerequisites',
    internal: false,
  },
  'curriculum.update_concept': {
    method: 'PATCH',
    path: '/v1/concepts/{concept_id}',
    internal: false,
  },
  'data.save_copy': { method: 'POST', path: '/v1/data/copy', internal: true },
  'films.captions': { method: 'GET', path: '/v1/films/{film_id}/captions', internal: false },
  'films.get': { method: 'GET', path: '/v1/courses/{course_id}/film', internal: false },
  'films.make': { method: 'POST', path: '/v1/courses/{course_id}/film', internal: false },
  'films.maker_status': { method: 'GET', path: '/v1/film-maker', internal: false },
  'films.making': { method: 'GET', path: '/v1/films/making', internal: false },
  'films.remove': { method: 'DELETE', path: '/v1/courses/{course_id}/film', internal: false },
  'films.remove_maker': { method: 'DELETE', path: '/v1/film-maker', internal: false },
  'films.save_file': { method: 'POST', path: '/v1/films/{film_id}/file', internal: true },
  'films.set_up_maker': { method: 'POST', path: '/v1/film-maker/setup', internal: false },
  'films.video_part': { method: 'GET', path: '/v1/films/{film_id}/video/{part}', internal: false },
  'generation.accept_proposal': {
    method: 'POST',
    path: '/v1/jobs/{job_id}/accept',
    internal: false,
  },
  'generation.dismiss_proposal': {
    method: 'POST',
    path: '/v1/jobs/{job_id}/dismiss',
    internal: false,
  },
  'generation.generate_lesson': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/lessons',
    internal: false,
  },
  'generation.latest_proposal': {
    method: 'GET',
    path: '/v1/courses/{course_id}/curriculum/proposal',
    internal: false,
  },
  'generation.propose_curriculum': {
    method: 'POST',
    path: '/v1/courses/{course_id}/curriculum/proposal',
    internal: false,
  },
  'jobs.cancel': { method: 'POST', path: '/v1/jobs/{job_id}/cancel', internal: false },
  'jobs.get': { method: 'GET', path: '/v1/jobs/{job_id}', internal: false },
  'jobs.list_active': { method: 'GET', path: '/v1/courses/{course_id}/jobs', internal: false },
  'jobs.list_writing': { method: 'GET', path: '/v1/jobs', internal: false },
  'learner.concept_evidence': {
    method: 'GET',
    path: '/v1/concepts/{concept_id}/evidence',
    internal: false,
  },
  'learner.get_preferences': { method: 'GET', path: '/v1/learner/preferences', internal: false },
  'learner.self_rate': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/self-rating',
    internal: false,
  },
  'learner.update_preferences': {
    method: 'PATCH',
    path: '/v1/learner/preferences',
    internal: false,
  },
  'learning.dismiss_hypothesis': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/hypotheses/{kind}/dismiss',
    internal: false,
  },
  'learning.overview': { method: 'GET', path: '/v1/courses/{course_id}/learning', internal: false },
  'learning.start_practice': {
    method: 'POST',
    path: '/v1/concepts/{concept_id}/practice',
    internal: false,
  },
  'lessons.answer': {
    method: 'POST',
    path: '/v1/lessons/{lesson_id}/questions/{question_id}/answer',
    internal: false,
  },
  'lessons.ask': { method: 'POST', path: '/v1/lessons/{lesson_id}/asks', internal: false },
  'lessons.delete': { method: 'DELETE', path: '/v1/lessons/{lesson_id}', internal: false },
  'lessons.delete_ask': {
    method: 'DELETE',
    path: '/v1/lessons/{lesson_id}/asks/{ask_id}',
    internal: false,
  },
  'lessons.get': { method: 'GET', path: '/v1/lessons/{lesson_id}', internal: false },
  'lessons.list': { method: 'GET', path: '/v1/courses/{course_id}/lessons', internal: false },
  'lessons.list_asks': { method: 'GET', path: '/v1/lessons/{lesson_id}/asks', internal: false },
  'lessons.put_back_picture': {
    method: 'DELETE',
    path: '/v1/lessons/{lesson_id}/asks/{ask_id}/picture',
    internal: false,
  },
  'lessons.report_unhelpful': {
    method: 'POST',
    path: '/v1/lessons/{lesson_id}/unhelpful',
    internal: false,
  },
  'lessons.rules': { method: 'GET', path: '/v1/lesson-rules', internal: false },
  'lessons.save_progress': {
    method: 'PUT',
    path: '/v1/lessons/{lesson_id}/progress',
    internal: false,
  },
  'lessons.use_ask_picture': {
    method: 'POST',
    path: '/v1/lessons/{lesson_id}/asks/{ask_id}/picture',
    internal: false,
  },
  'lessons.withdraw_unhelpful': {
    method: 'DELETE',
    path: '/v1/lessons/{lesson_id}/unhelpful/{segment_id}',
    internal: false,
  },
  'narration.clip': {
    method: 'GET',
    path: '/v1/lessons/{lesson_id}/narration/{clip}',
    internal: false,
  },
  'narration.get': { method: 'GET', path: '/v1/lessons/{lesson_id}/narration', internal: false },
  'narration.record': {
    method: 'POST',
    path: '/v1/lessons/{lesson_id}/narration',
    internal: false,
  },
  'provider.check': { method: 'POST', path: '/v1/provider/check', internal: false },
  'provider.clear_credential': {
    method: 'DELETE',
    path: '/v1/provider/credential',
    internal: true,
  },
  'provider.select': { method: 'PUT', path: '/v1/provider/selection', internal: true },
  'provider.set_credential': { method: 'PUT', path: '/v1/provider/credential', internal: true },
  'provider.status': { method: 'GET', path: '/v1/provider', internal: false },
  'provider.usage': { method: 'GET', path: '/v1/provider/usage', internal: false },
  'scenes.report_trial': { method: 'POST', path: '/v1/scene-trials/{trial_id}', internal: false },
  'scenes.trials': { method: 'GET', path: '/v1/scene-trials', internal: false },
  'settings.bring_in_file': { method: 'POST', path: '/v1/settings-file', internal: true },
  'settings.look_at_file': { method: 'POST', path: '/v1/settings-file/look', internal: true },
  'settings.save_file': { method: 'GET', path: '/v1/settings-file', internal: true },
  'sources.delete': { method: 'DELETE', path: '/v1/sources/{source_id}', internal: false },
  'sources.get': { method: 'GET', path: '/v1/sources/{source_id}', internal: false },
  'sources.import_paths': {
    method: 'POST',
    path: '/v1/courses/{course_id}/sources/import',
    internal: true,
  },
  'sources.list': { method: 'GET', path: '/v1/courses/{course_id}/sources', internal: false },
  'sources.read_pictures': {
    method: 'POST',
    path: '/v1/sources/{source_id}/read-pictures',
    internal: false,
  },
  'sources.search': { method: 'GET', path: '/v1/courses/{course_id}/search', internal: false },
  'system.health': { method: 'GET', path: '/v1/health', internal: false },
  'voice.choose': { method: 'PUT', path: '/v1/voice', internal: false },
  'voice.describe': { method: 'POST', path: '/v1/voice/design', internal: false },
  'voice.install': { method: 'POST', path: '/v1/voice/setup', internal: false },
  'voice.remove': { method: 'DELETE', path: '/v1/voice/{tier}', internal: false },
  'voice.sample': { method: 'POST', path: '/v1/voice/samples', internal: false },
  'voice.sample_clip': { method: 'GET', path: '/v1/voice/samples/{name}', internal: false },
  'voice.status': { method: 'GET', path: '/v1/voice', internal: false },
} as const;

export type OperationId = keyof typeof OPERATIONS;

/** Parameter and result types for each operation. */
export interface OperationTypes {
  'courses.bring_in_file': {
    path: undefined;
    query: undefined;
    body: CourseFileToBringIn;
    result: BroughtInCourse;
  };
  'courses.create': {
    path: undefined;
    query: undefined;
    body: CourseCreate;
    result: Course;
  };
  'courses.delete': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'courses.get': {
    path: { course_id: string };
    query: { opened?: boolean } | undefined;
    body: undefined;
    result: Course;
  };
  'courses.install_sample': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: Course;
  };
  'courses.list': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: CourseList;
  };
  'courses.look_at_file': {
    path: undefined;
    query: undefined;
    body: CourseFilePath;
    result: CourseFileSummary;
  };
  'courses.save_file': {
    path: { course_id: string };
    query: undefined;
    body: CourseFileRequest;
    result: SavedCourseFile;
  };
  'courses.update': {
    path: { course_id: string };
    query: undefined;
    body: CourseUpdate;
    result: Course;
  };
  'curriculum.add_from_outline': {
    path: { course_id: string };
    query: undefined;
    body: OutlineSelection;
    result: Curriculum;
  };
  'curriculum.add_source_ref': {
    path: { concept_id: string };
    query: undefined;
    body: SourceRefCreate;
    result: Curriculum;
  };
  'curriculum.create_concept': {
    path: { course_id: string };
    query: undefined;
    body: ConceptCreate;
    result: Curriculum;
  };
  'curriculum.delete_concept': {
    path: { concept_id: string };
    query: undefined;
    body: undefined;
    result: Curriculum;
  };
  'curriculum.get': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: Curriculum;
  };
  'curriculum.outline_candidates': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: OutlineCandidates;
  };
  'curriculum.related_passages': {
    path: { concept_id: string };
    query: { limit?: number } | undefined;
    body: undefined;
    result: Passages;
  };
  'curriculum.remove_source_ref': {
    path: { concept_id: string; ref_id: number };
    query: undefined;
    body: undefined;
    result: Curriculum;
  };
  'curriculum.reorder': {
    path: { course_id: string };
    query: undefined;
    body: ConceptOrder;
    result: Curriculum;
  };
  'curriculum.set_objectives': {
    path: { concept_id: string };
    query: undefined;
    body: ObjectivesUpdate;
    result: Curriculum;
  };
  'curriculum.set_prerequisites': {
    path: { concept_id: string };
    query: undefined;
    body: PrerequisitesUpdate;
    result: Curriculum;
  };
  'curriculum.update_concept': {
    path: { concept_id: string };
    query: undefined;
    body: ConceptUpdate;
    result: Curriculum;
  };
  'data.save_copy': {
    path: undefined;
    query: undefined;
    body: CopyDestination;
    result: null;
  };
  'films.captions': {
    path: { film_id: string };
    query: undefined;
    body: undefined;
    result: FilmCaptions;
  };
  'films.get': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: CourseFilm;
  };
  'films.make': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'films.maker_status': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: FilmMakerStatus;
  };
  'films.making': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: JobList;
  };
  'films.remove': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'films.remove_maker': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: FilmMakerStatus;
  };
  'films.save_file': {
    path: { film_id: string };
    query: undefined;
    body: undefined;
    result: SavedFilmFile;
  };
  'films.set_up_maker': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: Job;
  };
  'films.video_part': {
    path: { film_id: string; part: number };
    query: undefined;
    body: undefined;
    result: FilmVideoPart;
  };
  'generation.accept_proposal': {
    path: { job_id: string };
    query: undefined;
    body: ProposalAcceptance;
    result: Curriculum;
  };
  'generation.dismiss_proposal': {
    path: { job_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'generation.generate_lesson': {
    path: { concept_id: string };
    query: undefined;
    body: LessonRequest | null;
    result: Job;
  };
  'generation.latest_proposal': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: LatestJob;
  };
  'generation.propose_curriculum': {
    path: { course_id: string };
    query: undefined;
    body: ProposalRequest | null;
    result: Job;
  };
  'jobs.cancel': {
    path: { job_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'jobs.get': {
    path: { job_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'jobs.list_active': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: JobList;
  };
  'jobs.list_writing': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: JobList;
  };
  'learner.concept_evidence': {
    path: { concept_id: string };
    query: undefined;
    body: undefined;
    result: ConceptEvidence;
  };
  'learner.get_preferences': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: LearnerPreferences;
  };
  'learner.self_rate': {
    path: { concept_id: string };
    query: undefined;
    body: SelfRating;
    result: ConceptEvidence;
  };
  'learner.update_preferences': {
    path: undefined;
    query: undefined;
    body: LearnerPreferencesUpdate;
    result: LearnerPreferences;
  };
  'learning.dismiss_hypothesis': {
    path: {
      concept_id: string;
      kind:
        | 'prerequisite_gap'
        | 'definition_confusion'
        | 'notation_confusion'
        | 'procedure_order'
        | 'causal_confusion'
        | 'arithmetic_slip'
        | 'misread_question'
        | 'overgeneralization';
    };
    query: undefined;
    body: undefined;
    result: LearningOverview;
  };
  'learning.overview': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: LearningOverview;
  };
  'learning.start_practice': {
    path: { concept_id: string };
    query: undefined;
    body: PracticeRequest;
    result: PracticeSet;
  };
  'lessons.answer': {
    path: { lesson_id: string; question_id: string };
    query: undefined;
    body: AnswerRequest;
    result: AnswerResult;
  };
  'lessons.ask': {
    path: { lesson_id: string };
    query: undefined;
    body: AskRequest;
    result: Job;
  };
  'lessons.delete': {
    path: { lesson_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'lessons.delete_ask': {
    path: { lesson_id: string; ask_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'lessons.get': {
    path: { lesson_id: string };
    query: undefined;
    body: undefined;
    result: LessonForPlayer;
  };
  'lessons.list': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: LessonList;
  };
  'lessons.list_asks': {
    path: { lesson_id: string };
    query: undefined;
    body: undefined;
    result: AskList;
  };
  'lessons.put_back_picture': {
    path: { lesson_id: string; ask_id: string };
    query: undefined;
    body: undefined;
    result: LessonForPlayer;
  };
  'lessons.report_unhelpful': {
    path: { lesson_id: string };
    query: undefined;
    body: UnhelpfulReport;
    result: null;
  };
  'lessons.rules': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: LessonRules;
  };
  'lessons.save_progress': {
    path: { lesson_id: string };
    query: undefined;
    body: LessonProgressUpdate;
    result: LessonProgress;
  };
  'lessons.use_ask_picture': {
    path: { lesson_id: string; ask_id: string };
    query: undefined;
    body: undefined;
    result: LessonForPlayer;
  };
  'lessons.withdraw_unhelpful': {
    path: { lesson_id: string; segment_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'narration.clip': {
    path: { lesson_id: string; clip: string };
    query: undefined;
    body: undefined;
    result: NarrationClip;
  };
  'narration.get': {
    path: { lesson_id: string };
    query: undefined;
    body: undefined;
    result: Narration;
  };
  'narration.record': {
    path: { lesson_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'provider.check': {
    path: undefined;
    query: undefined;
    body: ProviderCheck;
    result: Job;
  };
  'provider.clear_credential': {
    path: undefined;
    query: { provider_id?: string | null } | undefined;
    body: undefined;
    result: null;
  };
  'provider.select': {
    path: undefined;
    query: undefined;
    body: ProviderSelection;
    result: null;
  };
  'provider.set_credential': {
    path: undefined;
    query: undefined;
    body: ProviderCredential;
    result: null;
  };
  'provider.status': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: ProviderStatus;
  };
  'provider.usage': {
    path: undefined;
    query: { provider_id?: string | null } | undefined;
    body: undefined;
    result: ProviderUsage;
  };
  'scenes.report_trial': {
    path: { trial_id: string };
    query: undefined;
    body: SceneTrialReport;
    result: null;
  };
  'scenes.trials': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: SceneTrialList;
  };
  'settings.bring_in_file': {
    path: undefined;
    query: undefined;
    body: SettingsToBringIn;
    result: SettingsBroughtIn;
  };
  'settings.look_at_file': {
    path: undefined;
    query: undefined;
    body: SettingsToLookAt;
    result: SettingsLookedAt;
  };
  'settings.save_file': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: CoreSettings;
  };
  'sources.delete': {
    path: { source_id: string };
    query: undefined;
    body: undefined;
    result: null;
  };
  'sources.get': {
    path: { source_id: string };
    query: undefined;
    body: undefined;
    result: SourceDetail;
  };
  'sources.import_paths': {
    path: { course_id: string };
    query: undefined;
    body: ImportRequest;
    result: Job;
  };
  'sources.list': {
    path: { course_id: string };
    query: undefined;
    body: undefined;
    result: SourceList;
  };
  'sources.read_pictures': {
    path: { source_id: string };
    query: undefined;
    body: undefined;
    result: Job;
  };
  'sources.search': {
    path: { course_id: string };
    query: { q: string; limit?: number };
    body: undefined;
    result: SearchResults;
  };
  'system.health': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: Health;
  };
  'voice.choose': {
    path: undefined;
    query: undefined;
    body: VoiceChoice;
    result: VoiceStatus;
  };
  'voice.describe': {
    path: undefined;
    query: undefined;
    body: VoiceDescriptionRequest;
    result: VoiceDescription;
  };
  'voice.install': {
    path: undefined;
    query: undefined;
    body: VoiceSetup;
    result: Job;
  };
  'voice.remove': {
    path: { tier: string };
    query: undefined;
    body: undefined;
    result: VoiceStatus;
  };
  'voice.sample': {
    path: undefined;
    query: undefined;
    body: VoiceSampleRequest;
    result: Job;
  };
  'voice.sample_clip': {
    path: { name: string };
    query: undefined;
    body: undefined;
    result: NarrationClip;
  };
  'voice.status': {
    path: undefined;
    query: undefined;
    body: undefined;
    result: VoiceStatus;
  };
}
