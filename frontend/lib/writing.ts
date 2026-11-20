import type { WritingDraft, WritingSuggestion } from "./api";

export function reconcileSavedDraft(local: WritingDraft, sent: WritingDraft, saved: WritingDraft): WritingDraft {
  return JSON.stringify(local) === JSON.stringify(sent) ? saved : local;
}

export function insertWritingSuggestion(draft: WritingDraft, suggestion: WritingSuggestion): WritingDraft {
  return {
    ...draft,
    content_markdown: `${draft.content_markdown.trimEnd()}\n\n${suggestion.content_markdown}\n`,
    cited_citation_ids: [...new Set([...draft.cited_citation_ids, ...(suggestion.citation_ids || [])])],
  };
}
