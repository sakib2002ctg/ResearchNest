import type { api, BeginnerExplanation, LearningGuide, TeamRole } from "./api";

export function sourceContainsQuote(source: string, quote: string): boolean {
  const normalize = (text: string) => text.replace(/\s+/gu, " ").trim();
  const expected = normalize(quote);
  return expected.length > 0 && normalize(source).includes(expected);
}

export async function readVerifiedEducationPage(
  client: Pick<typeof api, "getDocument" | "getDocumentPages">,
  evidence: BeginnerExplanation["supported_evidence"][number],
  signal?: AbortSignal,
): Promise<string> {
  const before = await client.getDocument(evidence.document_id, signal);
  if (before.status !== "completed" || before.version !== evidence.document_version) throw new Error("Changed source");
  const pages = await client.getDocumentPages(evidence.document_id, evidence.page_number, 1, signal);
  const text = pages.items.find((item) => item.page_number === evidence.page_number)?.raw_text;
  if (!text || !sourceContainsQuote(text, evidence.quoted_snippet)) throw new Error("Changed quote");
  // Page responses omit the index version, so recheck after fetching page text.
  const after = await client.getDocument(evidence.document_id, signal);
  if (after.status !== "completed" || after.version !== before.version) throw new Error("Changed source");
  return text;
}

export function completedLearningSteps(guide: Pick<LearningGuide, "steps">, current: string[], step: string, checked: boolean): string[] {
  const selected = new Set(current);
  if (checked) selected.add(step); else selected.delete(step);
  return guide.steps.map((item) => item.id).filter((id) => selected.has(id));
}

export function teamPermissions(role: TeamRole) {
  return { canWrite: role === "owner" || role === "editor", canManageMembers: role === "owner", canDelete: role === "owner" };
}

export function safePublicLink(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function learningModulePath(value: string): string | null {
  return ["/discover", "/library", "/analysis", "/writing"].includes(value) ? value : null;
}
