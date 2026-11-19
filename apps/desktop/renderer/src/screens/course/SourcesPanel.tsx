import { FileText, FileType2, FileUp, Search, Trash2, TriangleAlert } from 'lucide-react';
import { type DragEvent, useEffect, useState } from 'react';

import type { Job, SearchHit, Source } from '@adle/contracts';
import {
  Badge,
  Button,
  Callout,
  Card,
  cx,
  Dialog,
  EmptyState,
  ErrorState,
  IconButton,
  LoadingState,
  ProgressBar,
  Section,
  Spinner,
  Stack,
  TextField,
  useToast,
} from '@adle/design-system';

import { type CoreResult, getBridge } from '../../lib/bridge';
import { callCore, describeError, unwrap } from '../../lib/core-client';
import { formatFileSize, pluralise } from '../../lib/format';
import { isJobActive, useJob } from '../../lib/use-job';
import { useResource } from '../../lib/use-resource';
import styles from './CourseScreen.module.css';

const KIND_LABEL: Record<Source['kind'], string> = {
  pdf: 'PDF',
  docx: 'Word document',
  markdown: 'Markdown',
  text: 'Text',
  authored: 'Written by Adle',
};

interface ImportedFile {
  file_name: string;
  outcome: 'imported' | 'duplicate' | 'rejected';
  message: string | null;
  warnings: string[];
}

/** Read the per-file outcomes from a finished import job. The result is untyped JSON. */
function importedFiles(job: Job | null): ImportedFile[] {
  const files = (job?.result as { files?: unknown } | null | undefined)?.files;
  if (!Array.isArray(files)) return [];
  return files.flatMap((entry: unknown): ImportedFile[] => {
    if (typeof entry !== 'object' || entry === null) return [];
    const record = entry as Record<string, unknown>;
    const outcome = record.outcome;
    if (
      typeof record.file_name !== 'string' ||
      (outcome !== 'imported' && outcome !== 'duplicate' && outcome !== 'rejected')
    ) {
      return [];
    }
    return [
      {
        file_name: record.file_name,
        outcome,
        message: typeof record.message === 'string' ? record.message : null,
        warnings: Array.isArray(record.warnings)
          ? record.warnings.filter((warning): warning is string => typeof warning === 'string')
          : [],
      },
    ];
  });
}

function sourceFacts(source: Source): string {
  const parts = [KIND_LABEL[source.kind]];
  if (source.page_count > 0) parts.push(pluralise(source.page_count, 'page'));
  else if (source.section_count > 1) parts.push(pluralise(source.section_count, 'section'));
  parts.push(pluralise(source.chunk_count, 'passage'));
  if (source.size_bytes > 0) parts.push(formatFileSize(source.size_bytes));
  return parts.join(' · ');
}

/** Import materials into a course, see what was extracted, and search it. */
export function SourcesPanel({ courseId }: { courseId: string }) {
  const toast = useToast();
  const sources = useResource(`sources:${courseId}`, () =>
    callCore('sources.list', { path: { course_id: courseId } }),
  );
  const [startedJob, setStartedJob] = useState<Job | null>(null);
  const [starting, setStarting] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [removing, setRemoving] = useState<Source | null>(null);
  const [removeBusy, setRemoveBusy] = useState(false);

  const job = useJob(startedJob, () => sources.reload());
  const importing = starting || isJobActive(job);
  const results = job && !isJobActive(job) ? importedFiles(job) : [];

  const begin = async (start: () => Promise<CoreResult<Job | null>>): Promise<void> => {
    setStarting(true);
    try {
      const started = unwrap(await start());
      if (started) setStartedJob(started); // null: the learner dismissed the file dialog
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The import could not start',
        description: describeError(error),
      });
    } finally {
      setStarting(false);
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setDragging(false);
    if (importing) return;
    const files = [...event.dataTransfer.files];
    if (files.length > 0) void begin(() => getBridge().sources.importDropped(courseId, files));
  };

  const cancelImport = (): void => {
    if (job) void callCore('jobs.cancel', { path: { job_id: job.id } });
  };

  const removeSource = async (): Promise<void> => {
    if (!removing) return;
    setRemoveBusy(true);
    try {
      await callCore('sources.delete', { path: { source_id: removing.id } });
      toast.show({ tone: 'success', title: 'Source removed', description: removing.display_name });
      sources.reload();
    } catch (error) {
      toast.show({
        tone: 'danger',
        title: 'The source could not be removed',
        description: describeError(error),
      });
    } finally {
      setRemoveBusy(false);
      setRemoving(null);
    }
  };

  const list = sources.resource;
  const hasSources = list.status === 'ready' && list.data.sources.length > 0;

  return (
    <>
      <Section
        title="Course materials"
        description="Adle reads these files on this computer to build your curriculum and to ground lessons in what your course actually says. Nothing is uploaded when you import."
      >
        <div
          className={cx(styles.dropzone, dragging && styles.dropzoneActive)}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null))
              setDragging(false);
          }}
          onDrop={onDrop}
        >
          <FileUp className={styles.dropzoneIcon} aria-hidden="true" />
          <p className={styles.dropzoneTitle}>
            {dragging ? 'Drop to import' : 'Drop files here, or choose them'}
          </p>
          <p className={styles.dropzoneHint}>PDF, Word (.docx), Markdown, or plain text</p>
          <Button
            variant="primary"
            loading={starting}
            disabled={isJobActive(job)}
            onClick={() => void begin(() => getBridge().sources.importWithPicker(courseId))}
          >
            Choose files
          </Button>
        </div>

        {job && isJobActive(job) ? (
          <Card padding="compact">
            <Stack direction="row" gap={4} align="center">
              <div className={styles.grow}>
                <ProgressBar
                  label={job.progress_message ? `Importing ${job.progress_message}` : 'Preparing…'}
                  showLabel
                  value={
                    job.progress_total > 0 ? job.progress_done / job.progress_total : undefined
                  }
                  valueText={
                    job.progress_total > 0
                      ? `${Math.min(job.progress_done + 1, job.progress_total)} of ${job.progress_total}`
                      : undefined
                  }
                />
              </div>
              <Button size="small" onClick={cancelImport}>
                Stop
              </Button>
            </Stack>
          </Card>
        ) : null}

        {job && !isJobActive(job) ? <ImportSummary job={job} files={results} /> : null}
      </Section>

      <Section title="In this course">
        {list.status === 'loading' ? (
          <LoadingState title="Reading the course materials…" />
        ) : list.status === 'error' ? (
          <ErrorState
            title="The materials could not be listed"
            description={describeError(list.error)}
            actions={<Button onClick={sources.reload}>Try again</Button>}
          />
        ) : !hasSources ? (
          <EmptyState
            visual={<FileText />}
            title="No materials yet"
            description="Add a syllabus, lecture notes, or readings. You can also continue without any: Adle can teach a topic from general knowledge and will say when it is doing so."
          />
        ) : (
          <ul className={styles.sources} aria-label="Materials in this course">
            {list.data.sources.map((source) => (
              <li key={source.id} className={styles.source}>
                <span className={styles.sourceIcon} aria-hidden="true">
                  {source.kind === 'pdf' ? <FileType2 /> : <FileText />}
                </span>
                <div className={styles.sourceBody}>
                  <div className={styles.sourceHeading}>
                    <span className={styles.sourceName}>{source.display_name}</span>
                    {source.status === 'needs_attention' ? (
                      <Badge tone="warning" icon={<TriangleAlert />}>
                        Check extraction
                      </Badge>
                    ) : (
                      <Badge tone="success">Ready</Badge>
                    )}
                  </div>
                  <p className={styles.sourceFacts}>{sourceFacts(source)}</p>
                  {source.warnings.map((warning) => (
                    <p key={warning} className={styles.sourceWarning}>
                      {warning}
                    </p>
                  ))}
                </div>
                <IconButton
                  label={`Remove ${source.display_name}`}
                  icon={<Trash2 />}
                  onClick={() => setRemoving(source)}
                />
              </li>
            ))}
          </ul>
        )}
      </Section>

      {hasSources ? <SourceSearch courseId={courseId} /> : null}

      <Dialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={removing ? `Remove “${removing.display_name}”?` : 'Remove source?'}
        description="Its text will no longer be available to this course. The original file on your computer is not touched."
        dismissible={!removeBusy}
        actions={
          <>
            <Button onClick={() => setRemoving(null)} disabled={removeBusy}>
              Keep it
            </Button>
            <Button variant="destructive" loading={removeBusy} onClick={() => void removeSource()}>
              Remove source
            </Button>
          </>
        }
      />
    </>
  );
}

function ImportSummary({ job, files }: { job: Job; files: ImportedFile[] }) {
  if (job.status === 'failed') {
    return (
      <Callout tone="danger" urgent title="The import stopped">
        {job.error_message ?? 'Something went wrong. Nothing was lost; please try again.'}
      </Callout>
    );
  }

  const imported = files.filter((file) => file.outcome === 'imported');
  const duplicates = files.filter((file) => file.outcome === 'duplicate');
  const rejected = files.filter((file) => file.outcome === 'rejected');
  const withWarnings = imported.filter((file) => file.warnings.length > 0);

  const counts = [
    imported.length > 0 ? `${pluralise(imported.length, 'file')} imported` : null,
    duplicates.length > 0 ? `${duplicates.length} already in this course` : null,
    rejected.length > 0 ? `${rejected.length} could not be imported` : null,
  ].filter(Boolean);
  const cancelled = job.status === 'cancelled';
  const title = [cancelled ? 'Import stopped' : null, ...counts].filter(Boolean).join(' · ');

  return (
    <Callout
      tone={rejected.length > 0 ? 'warning' : 'success'}
      title={title || (cancelled ? 'Import stopped' : 'Nothing was imported')}
    >
      {rejected.length > 0 || withWarnings.length > 0 ? (
        <ul className={styles.outcomes}>
          {rejected.map((file) => (
            <li key={`rejected:${file.file_name}`}>
              <strong>{file.file_name}</strong>: {file.message}
            </li>
          ))}
          {withWarnings.map((file) => (
            <li key={`warning:${file.file_name}`}>
              <strong>{file.file_name}</strong> was imported, with a note: {file.warnings[0]}
            </li>
          ))}
        </ul>
      ) : (
        <p>The text was extracted and is ready to use.</p>
      )}
    </Callout>
  );
}

interface SearchAnswer {
  query: string;
  hits: SearchHit[];
  error: string | null;
}

type SearchState =
  | { status: 'idle' }
  | { status: 'searching' }
  | { status: 'done'; query: string; hits: SearchHit[] }
  | { status: 'error'; message: string };

function hitLocation(hit: SearchHit): string {
  if (hit.page_number !== null) return `page ${hit.page_number}`;
  return hit.section_title ?? 'whole document';
}

/** Find where the course materials talk about something, with the exact location. */
function SourceSearch({ courseId }: { courseId: string }) {
  const [query, setQuery] = useState('');
  // The answer to the most recent completed search, kept with the query it answers.
  const [answer, setAnswer] = useState<SearchAnswer | null>(null);
  const trimmed = query.trim();

  useEffect(() => {
    if (!trimmed) return;
    let cancelled = false;
    // Wait for a pause in typing before asking.
    const timer = window.setTimeout(() => {
      callCore('sources.search', { path: { course_id: courseId }, query: { q: trimmed } }).then(
        (result) => {
          if (!cancelled) setAnswer({ query: trimmed, hits: result.hits, error: null });
        },
        (error: unknown) => {
          if (!cancelled) setAnswer({ query: trimmed, hits: [], error: describeError(error) });
        },
      );
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [courseId, trimmed]);

  // What to show follows from the query and the latest answer; nothing to keep in sync.
  let state: SearchState;
  if (!trimmed) state = { status: 'idle' };
  else if (answer?.query !== trimmed) state = { status: 'searching' };
  else if (answer.error !== null) state = { status: 'error', message: answer.error };
  else state = { status: 'done', query: answer.query, hits: answer.hits };

  return (
    <Section
      title="Search your materials"
      description="Find where your sources discuss something. Each result shows the file and the place it comes from."
    >
      <TextField
        label="Search your materials"
        hideLabel
        type="search"
        value={query}
        maxLength={200}
        placeholder="For example: learning rate"
        onChange={(event) => setQuery(event.target.value)}
        trailing={
          state.status === 'searching' ? (
            <span className={styles.searchAdornment}>
              <Spinner size="small" label="Searching" />
            </span>
          ) : (
            <span className={styles.searchAdornment} aria-hidden="true">
              <Search />
            </span>
          )
        }
      />
      <div aria-live="polite">
        {state.status === 'error' ? (
          <Callout tone="danger" title="The search did not work">
            {state.message}
          </Callout>
        ) : state.status === 'done' && state.hits.length === 0 ? (
          <p className={styles.noResults}>
            Nothing in your materials matches “{state.query}”. Try a different word.
          </p>
        ) : state.status === 'done' ? (
          <ol className={styles.hits} aria-label={`Results for ${state.query}`}>
            {state.hits.map((hit) => (
              <li key={hit.chunk_id} className={styles.hit}>
                <p className={styles.hitSource}>
                  <span className={styles.hitName}>{hit.source_name}</span>
                  <span className={styles.hitLocation}>{hitLocation(hit)}</span>
                </p>
                <p className={styles.hitExcerpt}>
                  {hit.excerpt.map((segment, index) =>
                    segment.highlighted ? (
                      <mark key={index} className={styles.match}>
                        {segment.text}
                      </mark>
                    ) : (
                      <span key={index}>{segment.text}</span>
                    ),
                  )}
                </p>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </Section>
  );
}
