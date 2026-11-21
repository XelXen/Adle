/** The most files one drop may bring: one more than the main process accepts, so it can say so. */
const MOST_FILES = 51;

/**
 * The paths behind the files of a drop.
 *
 * `files` comes from the page, so nothing about it is taken on trust and no method of it
 * is called. A value from the page can carry functions of its own: a `map` that returns
 * any strings it likes would turn "the files that were dropped" into "any path the page
 * names". So it must be a real list, each entry must be a real `File`, and the path is
 * asked of the browser, which has one only for a file the learner dropped or chose.
 */
export function droppedPaths(files: unknown, pathOf: (file: File) => string): string[] {
  if (!Array.isArray(files)) return [];
  const paths: string[] = [];
  const count = Math.min(files.length, MOST_FILES);
  for (let index = 0; index < count; index += 1) {
    const file: unknown = files[index];
    if (!(file instanceof File)) continue;
    let found: unknown;
    try {
      found = pathOf(file);
    } catch {
      continue;
    }
    if (typeof found === 'string' && found !== '') paths.push(found);
  }
  return paths;
}
