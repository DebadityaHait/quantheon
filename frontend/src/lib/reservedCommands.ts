// Composer slash-commands handled by their own logic, NOT the workflow picker.
// Keep in sync with the backend RESERVED_WORKFLOW_SLUGS. `goal` is owned by the
// goal-mode feature; `compact` is owned by checkpoint compaction. The workflow
// picker must never intercept either command.
export const RESERVED_COMPOSER_COMMANDS = new Set<string>(['goal', 'compact']);
