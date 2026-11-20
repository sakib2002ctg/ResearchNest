"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api, ApiError, type AIProvider, type AIUsageStats, type Citation, type CitationStyle, type Language, type LibraryPaper, type Preferences, type WritingAction, type WritingDocument, type WritingDraft, type WritingExportFormat, type WritingSection, type WritingSuggestion, type WritingType, type WritingVersion } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadPrivateFile } from "@/lib/download";
import { useI18n } from "@/lib/i18n";
import { insertWritingSuggestion, reconcileSavedDraft } from "@/lib/writing";
import styles from "./workspace.module.css";

const typeNames: Record<WritingType, [string, string]> = { research_paper: ["Research paper", "গবেষণাপত্র"], research_proposal: ["Research proposal", "গবেষণা প্রস্তাব"], thesis: ["Thesis", "অভিসন্দর্ভ"], literature_review: ["Literature review", "সাহিত্য পর্যালোচনা"] };
const sectionNames: Record<WritingSection, [string, string]> = { abstract: ["Abstract", "সারসংক্ষেপ"], introduction: ["Introduction", "ভূমিকা"], literature_review: ["Literature review", "সাহিত্য পর্যালোচনা"], methodology: ["Methodology", "পদ্ধতি"], results_discussion: ["Results & discussion", "ফলাফল ও আলোচনা"] };
const templates: Record<WritingType, string[]> = { research_paper: ["Abstract", "Introduction", "Literature Review", "Methodology", "Results and Discussion", "Conclusion"], research_proposal: ["Abstract", "Research Problem", "Objectives", "Literature Review", "Proposed Methodology", "Timeline"], thesis: ["Abstract", "Introduction", "Literature Review", "Methodology", "Results", "Discussion", "Conclusion"], literature_review: ["Introduction", "Scope", "Themes and Findings", "Research Gaps", "Conclusion"] };
const banglaTemplates: Record<WritingType, string[]> = { research_paper: ["সারসংক্ষেপ", "ভূমিকা", "সাহিত্য পর্যালোচনা", "পদ্ধতি", "ফলাফল ও আলোচনা", "উপসংহার"], research_proposal: ["সারসংক্ষেপ", "গবেষণার সমস্যা", "উদ্দেশ্য", "সাহিত্য পর্যালোচনা", "প্রস্তাবিত পদ্ধতি", "সময়সূচি"], thesis: ["সারসংক্ষেপ", "ভূমিকা", "সাহিত্য পর্যালোচনা", "পদ্ধতি", "ফলাফল", "আলোচনা", "উপসংহার"], literature_review: ["ভূমিকা", "পরিসর", "বিষয় ও ফলাফল", "গবেষণার সুযোগ", "উপসংহার"] };
const styleNames: Record<CitationStyle, string> = { apa: "APA 7", ieee: "IEEE", mla: "MLA 9", chicago: "Chicago", harvard: "Harvard" };
function editable(doc: WritingDocument): WritingDraft { return { title: doc.title, doc_type: doc.doc_type, language: doc.language, outline: doc.outline, content_markdown: doc.content_markdown, cited_citation_ids: doc.cited_citation_ids }; }

export default function WritingPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("Writing Studio", "লেখার স্টুডিও")} description={pick("Your private academic drafts, verified references, and clearly separated AI suggestions.", "আপনার ব্যক্তিগত গবেষণার খসড়া, যাচাই করা তথ্যসূত্র এবং আলাদা এআই পরামর্শ।")} showHeading>{user && <Workspace key={user.id} />}</AppShell>;
}

function Workspace() {
  const { pick, language } = useI18n();
  const [documents, setDocuments] = useState<WritingDocument[]>([]);
  const [current, setCurrent] = useState<WritingDocument | null>(null);
  const [openSerial, setOpenSerial] = useState(0);
  const [offset, setOffset] = useState(0);
  const [more, setMore] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [docType, setDocType] = useState<WritingType>("research_paper");
  const [pending, setPending] = useState(false);
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState("");
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true; let active = true;
    api.getWritingDocuments().then((result) => { if (active) { setDocuments(result); setMore(result.length === 30); } }).catch(() => { if (active) setError("Unable to load documents / নথি লোড হয়নি।"); });
    return () => { alive.current = false; active = false; };
  }, []);
  const saved = useCallback((doc: WritingDocument) => { setDocuments((old) => [doc, ...old.filter((item) => item.id !== doc.id)]); setCurrent(doc); }, []);
  async function action(work: () => Promise<void>) {
    setPending(true); setError("");
    try { await work(); } catch { if (alive.current) setError(pick("The document request failed. Please retry.", "নথির অনুরোধ ব্যর্থ হয়েছে। আবার চেষ্টা করুন।")); }
    finally { if (alive.current) setPending(false); }
  }
  return <>{error && <p role="alert" className="notice error">{error}</p>}<div className={styles.workspace}>
    <aside className={`card ${styles.sidebar}`}>
      <h2>{pick("New document", "নতুন নথি")}</h2>
      <form className={styles.form} onSubmit={(event) => { event.preventDefault(); void action(async () => { const outline = (language === "bn" ? banglaTemplates : templates)[docType]; const result = await api.createWritingDocument({ title: newTitle.trim(), doc_type: docType, language, outline }); if (alive.current) { setCurrent(result); setDocuments((old) => [result, ...old]); setNewTitle(""); } }); }}>
        <label>{pick("Title", "শিরোনাম")}<input required maxLength={200} disabled={pending || locked} value={newTitle} onChange={(event) => setNewTitle(event.target.value)} /></label>
        <label>{pick("Template", "নমুনা")}<select disabled={pending || locked} value={docType} onChange={(event) => setDocType(event.target.value as WritingType)}>{Object.entries(typeNames).map(([value, names]) => <option key={value} value={value}>{pick(...names)}</option>)}</select></label>
        <button className="button primary" disabled={pending || locked}>{pick("Create draft", "খসড়া তৈরি করুন")}</button>
      </form>
      <h2>{pick("My drafts", "আমার খসড়া")}</h2>
      <ul className={styles.saved}>{documents.map((doc) => <li key={doc.id}><button type="button" disabled={pending || locked} aria-pressed={current?.id === doc.id} onClick={() => action(async () => { const result = await api.getWritingDocument(doc.id); if (alive.current) { setCurrent(result); setOpenSerial((value) => value + 1); } })}>{doc.title}<small>{pick(...typeNames[doc.doc_type])} · {doc.language === "bn" ? "বাংলা" : "English"}</small></button><button type="button" aria-label={`${pick("Delete", "মুছুন")} ${doc.title}`} disabled={pending || locked} onClick={() => action(async () => { await api.deleteWritingDocument(doc.id); if (alive.current) { setDocuments((old) => old.filter((item) => item.id !== doc.id)); if (current?.id === doc.id) setCurrent(null); } })}>×</button></li>)}</ul>
      {more && <button type="button" disabled={pending || locked} onClick={() => action(async () => { const result = await api.getWritingDocuments(30, offset + 30); if (alive.current) { setDocuments((old) => [...old, ...result.filter((item) => !old.some((doc) => doc.id === item.id))]); setOffset(offset + 30); setMore(result.length === 30); } })}>{pick("Load more", "আরও দেখুন")}</button>}
      {locked && <p className="muted text-xs">{pick("Save changes before switching drafts.", "খসড়া বদলানোর আগে পরিবর্তন সংরক্ষণ করুন।")}</p>}
    </aside>
    {current ? <Editor key={`${current.id}-${openSerial}`} initial={current} onSaved={saved} onLocked={setLocked} /> : <section className="card empty-state"><h2>{pick("A place for your research writing", "আপনার গবেষণার লেখার জায়গা")}</h2><p>{pick("Create a document or open a saved draft. AI suggestions remain separate until you explicitly insert them.", "নথি তৈরি করুন বা সংরক্ষিত খসড়া খুলুন। নিজে যুক্ত করার আগে এআই পরামর্শ আলাদা থাকবে।")}</p></section>}
  </div></>;
}

function Editor({ initial, onSaved, onLocked }: { initial: WritingDocument; onSaved: (doc: WritingDocument) => void; onLocked: (locked: boolean) => void }) {
  const { pick, locale } = useI18n();
  const [server, setServer] = useState(initial);
  const [draft, setDraft] = useState<WritingDraft>(() => editable(initial));
  const [snapshot, setSnapshot] = useState(() => JSON.stringify(editable(initial)));
  const [saving, setSaving] = useState(false);
  const [working, setWorking] = useState(false);
  const [autosave, setAutosave] = useState(true);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [versions, setVersions] = useState<WritingVersion[]>([]);
  const [summary, setSummary] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [citationPage, setCitationPage] = useState(0);
  const [moreCitations, setMoreCitations] = useState(false);
  const [citation, setCitation] = useState("");
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [usage, setUsage] = useState<AIUsageStats | null>(null);
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [format, setFormat] = useState<WritingExportFormat>("docx");
  const [action, setAction] = useState<WritingAction>("draft_section");
  const [section, setSection] = useState<WritingSection>("introduction");
  const [rewrite, setRewrite] = useState("");
  const [provider, setProvider] = useState<AIProvider>("auto");
  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [paperQuery, setPaperQuery] = useState("");
  const [paperPage, setPaperPage] = useState(1);
  const [paperPages, setPaperPages] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [suggestions, setSuggestions] = useState<WritingSuggestion[]>(initial.ai_suggestions_log);
  const [assisting, setAssisting] = useState(false);
  const alive = useRef(true);
  const saveInFlight = useRef(false);
  const retry = useRef<{ fingerprint: string; id: string } | null>(null);
  const textArea = useRef<HTMLTextAreaElement>(null);
  const dirty = JSON.stringify(draft) !== snapshot;
  const busy = saving || working || assisting;

  useEffect(() => {
    alive.current = true; let active = true;
    Promise.all([api.getWritingVersions(initial.id), api.getCitations(50), api.getPreferences(), api.getAIUsage()]).then(([history, references, preferences, stats]) => { if (active) { setVersions(history); setCitations(references); setMoreCitations(references.length === 50); setPrefs(preferences); setUsage(stats); } }).catch(() => { if (active) setError("Unable to load editor tools / সম্পাদনার সরঞ্জাম লোড হয়নি।"); });
    const refresh = () => { api.getPreferences().then((result) => { if (active) setPrefs(result); }).catch(() => {}); };
    window.addEventListener("focus", refresh);
    return () => { active = false; alive.current = false; window.removeEventListener("focus", refresh); onLocked(false); };
  }, [initial.id, onLocked]);
  useEffect(() => { onLocked(dirty || busy); }, [dirty, busy, onLocked]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    const keepUnsavedDraft = (event: MouseEvent) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || !(event.target instanceof Element)) return;
      const link = event.target.closest("a[href]");
      if (!(link instanceof HTMLAnchorElement) || link.target === "_blank") return;
      const destination = new URL(link.href, window.location.href);
      if (destination.origin !== window.location.origin || destination.pathname !== window.location.pathname) {
        event.preventDefault(); event.stopPropagation();
        setNotice("Save your changes before leaving / বের হওয়ার আগে পরিবর্তন সংরক্ষণ করুন।");
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", keepUnsavedDraft, true);
    return () => { window.removeEventListener("beforeunload", warn); document.removeEventListener("click", keepUnsavedDraft, true); };
  }, [dirty]);
  useEffect(() => {
    let active = true;
    api.getLibrary({ q: paperQuery || undefined, page: paperPage, size: 30 }).then((result) => { if (active) { setPapers(result.items); setPaperPages(result.pages); } }).catch(() => { if (active) setError("Unable to load sources / উৎস লোড হয়নি।"); });
    return () => { active = false; };
  }, [paperQuery, paperPage]);

  const save = useCallback(async (checkpoint: boolean): Promise<WritingDocument | null> => {
    if (saveInFlight.current || !draft.title.trim()) return null;
    if (!checkpoint && JSON.stringify(draft) === snapshot) return server;
    saveInFlight.current = true; setSaving(true); setError(""); setNotice("");
    const sent = { ...draft, title: draft.title.trim(), outline: draft.outline.map((heading) => heading.trim()).filter(Boolean) };
    try {
      const result = await api.updateWritingDocument(server.id, { ...sent, expected_revision: server.revision, create_version: checkpoint, change_summary: checkpoint ? summary.trim() || undefined : undefined });
      if (!alive.current) return null;
      setServer(result); setSnapshot(JSON.stringify(editable(result))); setPaused(false); onSaved(result);
      // Preserve edits typed while autosave was in flight.
      setDraft((current) => reconcileSavedDraft(current, draft, editable(result)));
      setNotice(checkpoint ? pick("Version checkpoint saved.", "সংস্করণের চেকপয়েন্ট সংরক্ষিত।") : pick("All changes saved.", "সব পরিবর্তন সংরক্ষিত।"));
      if (checkpoint) { const history = await api.getWritingVersions(server.id); if (alive.current) setVersions(history); }
      return result;
    } catch (cause) {
      if (alive.current) { setPaused(true); setError(cause instanceof ApiError && cause.status === 409 ? pick("This draft changed elsewhere. Autosave is paused. Your local text remains here; copy it before reloading the saved draft.", "অন্য কোথাও খসড়াটি বদলেছে। স্বয়ংক্রিয় সংরক্ষণ বন্ধ আছে। আপনার লেখা এখানে আছে; সংরক্ষিত খসড়া লোড করার আগে কপি করুন।") : pick("Save failed. Your local changes remain here. Retry before leaving.", "সংরক্ষণ ব্যর্থ। আপনার পরিবর্তন এখানে আছে। বের হওয়ার আগে আবার চেষ্টা করুন।")); }
      return null;
    } finally { saveInFlight.current = false; if (alive.current) setSaving(false); }
  }, [draft, snapshot, server, summary, onSaved, pick]);

  useEffect(() => {
    if (!dirty || !autosave || paused || busy || !draft.title.trim()) return;
    const timer = globalThis.setTimeout(() => { void save(false); }, 1500);
    return () => globalThis.clearTimeout(timer);
  }, [dirty, autosave, paused, busy, draft, save]);

  async function run(work: () => Promise<void>) {
    setWorking(true); setError(""); setNotice("");
    try { await work(); } catch (cause) { if (alive.current) setError(cause instanceof ApiError && cause.status === 409 ? pick("The saved document changed. Reload it after copying your local text.", "সংরক্ষিত নথি বদলেছে। আপনার লেখা কপি করে আবার লোড করুন।") : pick("The operation failed. Please try again.", "কাজটি ব্যর্থ হয়েছে। আবার চেষ্টা করুন।")); }
    finally { if (alive.current) setWorking(false); }
  }

  function insertReference() {
    const item = citations.find((reference) => reference.id === Number(citation)); if (!item) return;
    const start = textArea.current?.selectionStart ?? draft.content_markdown.length;
    const end = textArea.current?.selectionEnd ?? start;
    setDraft((current) => ({ ...current, content_markdown: current.content_markdown.slice(0, start) + `[@${item.cite_key}]` + current.content_markdown.slice(end), cited_citation_ids: [...new Set([...current.cited_citation_ids, item.id])] }));
    textArea.current?.focus();
  }

  async function assist() {
    setAssisting(true); setError("");
    const fingerprint = JSON.stringify([server.id, action, section, rewrite, selected, provider]);
    const request_id = retry.current?.fingerprint === fingerprint ? retry.current.id : crypto.randomUUID();
    retry.current = { fingerprint, id: request_id };
    try {
      const saved = await save(false); if (!saved) return;
      const result = await api.assistWriting(server.id, { action, section, text: action === "draft_section" ? undefined : rewrite.trim(), user_paper_ids: selected, provider, request_id });
      if (!alive.current) return;
      setSuggestions((old) => [result, ...old.filter((item) => item.id !== result.id)]); retry.current = null;
      const [fresh, stats] = await Promise.all([api.getWritingDocument(server.id), api.getAIUsage()]);
      if (alive.current) { setServer(fresh); setUsage(stats); onSaved(fresh); }
    } catch (cause) {
      if (alive.current) {
        if (cause instanceof ApiError && cause.status === 409) retry.current = null;
        setError(cause instanceof ApiError && cause.status === 403 ? pick("Enable external AI consent in Settings to use cloud assistance.", "ক্লাউড সহায়তার জন্য সেটিংসে বাহ্যিক এআই অনুমতি দিন।") : cause instanceof ApiError && cause.status === 429 ? pick("AI usage quota reached. Wait before retrying.", "এআই ব্যবহারের সীমা পূর্ণ হয়েছে। কিছুক্ষণ পর চেষ্টা করুন।") : cause instanceof ApiError && cause.status === 409 ? pick("Check that each selected paper has an indexed PDF and a saved library reference, then retry.", "প্রতিটি নির্বাচিত গবেষণাপত্রের ইনডেক্স করা পিডিএফ ও সংরক্ষিত তথ্যসূত্র আছে কি না দেখে আবার চেষ্টা করুন।") : pick("Assistance failed. Select indexed sources and check the input.", "সহায়তা ব্যর্থ হয়েছে। ইনডেক্স করা উৎস বাছুন ও লেখা যাচাই করুন।"));
      }
    } finally { if (alive.current) setAssisting(false); }
  }

  const localWords = draft.content_markdown.trim() ? draft.content_markdown.trim().split(/\s+/u).length : 0;
  return <section className={styles.editor} aria-label={pick("Academic editor", "গবেষণার লেখার সম্পাদক")}>
    {error && <p role="alert" className="notice error">{error}</p>}{notice && <p role="status" className="notice">{notice}</p>}
    <div className={`card ${styles.form}`}>
      <div className={styles.row}><span className="tag">{saving ? pick("Saving…", "সংরক্ষণ চলছে…") : dirty ? pick("Unsaved changes", "অসংরক্ষিত পরিবর্তন") : pick("Saved", "সংরক্ষিত")}</span><span className="muted text-xs">{localWords.toLocaleString(locale)} {pick("words", "শব্দ")} · {pick("Revision", "সংশোধন")} {server.revision}</span></div>
      <label>{pick("Document title", "নথির শিরোনাম")}<input required maxLength={200} disabled={working || assisting} value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
      <div className={styles.grid}><label>{pick("Document type", "নথির ধরন")}<select disabled={busy} value={draft.doc_type} onChange={(event) => setDraft({ ...draft, doc_type: event.target.value as WritingType })}>{Object.entries(typeNames).map(([value, names]) => <option key={value} value={value}>{pick(...names)}</option>)}</select></label><label>{pick("Writing language", "লেখার ভাষা")}<select value={draft.language} disabled={busy} onChange={(event) => setDraft({ ...draft, language: event.target.value as Language })}><option value="en">English</option><option value="bn">বাংলা</option></select></label></div>
      <details><summary>{pick("Document outline", "নথির রূপরেখা")}</summary><label>{pick("One section per line", "প্রতি লাইনে একটি বিভাগ")}<textarea rows={5} maxLength={5000} disabled={busy} value={draft.outline.join("\n")} onChange={(event) => setDraft({ ...draft, outline: event.target.value.split("\n") })} /></label><button type="button" disabled={busy} onClick={() => setDraft({ ...draft, outline: (draft.language === "bn" ? banglaTemplates : templates)[draft.doc_type] })}>{pick("Use document template outline", "নথির নমুনা রূপরেখা ব্যবহার করুন")}</button></details>
      <div className={styles.citationTools}><label>{pick("Insert a reference", "তথ্যসূত্র যুক্ত করুন")}<select value={citation} disabled={busy} onChange={(event) => setCitation(event.target.value)}><option value="">{pick("Choose reference…", "তথ্যসূত্র বাছুন…")}</option>{citations.map((item) => <option key={item.id} value={item.id}>{item.cite_key} · {item.title}</option>)}</select></label><button type="button" disabled={busy || !citation} onClick={insertReference}>{pick("Insert citation", "তথ্যসূত্র যুক্ত করুন")}</button></div>
      {moreCitations && <button type="button" disabled={busy} onClick={() => run(async () => { const result = await api.getCitations(50, citationPage + 50); if (alive.current) { setCitations((old) => [...old, ...result.filter((item) => !old.some((reference) => reference.id === item.id))]); setCitationPage((v) => v + 50); setMoreCitations(result.length === 50); } })}>{pick("Load more references", "আরও তথ্যসূত্র দেখুন")}</button>}
      <Link href="/citations" className="muted text-xs">{pick("Manage reference metadata", "তথ্যসূত্রের মেটাডেটা সম্পাদনা")}</Link>
      <label>{pick("Your manuscript (Markdown)", "আপনার পাণ্ডুলিপি (মার্কডাউন)")}<textarea ref={textArea} className={styles.manuscript} rows={22} maxLength={200000} value={draft.content_markdown} disabled={working || assisting} onChange={(event) => setDraft({ ...draft, content_markdown: event.target.value })} spellCheck /></label>
      <div className={styles.row}><label className={styles.choice}><input type="checkbox" checked={autosave} disabled={busy} onChange={(event) => setAutosave(event.target.checked)} />{pick("Autosave after typing", "লেখার পর স্বয়ংক্রিয় সংরক্ষণ")}</label><button type="button" className="button primary" disabled={busy || !draft.title.trim()} onClick={() => void save(false)}>{pick("Save now", "এখন সংরক্ষণ করুন")}</button></div>
      {paused && <button type="button" className="button secondary" disabled={busy} onClick={() => run(async () => { const result = await api.getWritingDocument(server.id); if (alive.current) { setDraft(editable(result)); setSnapshot(JSON.stringify(editable(result))); setServer(result); setSuggestions(result.ai_suggestions_log); setPaused(false); onSaved(result); } })}>{pick("Reload saved draft (discard local changes)", "সংরক্ষিত খসড়া লোড করুন (স্থানীয় পরিবর্তন বাদ যাবে)")}</button>}
      <details><summary>{pick("Version checkpoints", "সংস্করণের চেকপয়েন্ট")}</summary><div className={styles.form}><label>{pick("Change summary", "পরিবর্তনের সারাংশ")}<input value={summary} maxLength={300} disabled={busy} onChange={(event) => setSummary(event.target.value)} /></label><button type="button" className="button secondary" disabled={busy || !draft.title.trim()} onClick={() => void save(true)}>{pick("Save a version checkpoint", "সংস্করণের চেকপয়েন্ট সংরক্ষণ করুন")}</button><ul className={styles.versionList}>{versions.map((version) => <li key={version.id}><div><strong>#{version.version_number} · {version.title}</strong><small>{version.change_summary || new Date(version.created_at).toLocaleString(locale)}</small></div><button type="button" disabled={busy} onClick={() => run(async () => { const saved = await save(false); if (!saved) return; const result = await api.restoreWritingVersion(server.id, version.id, saved.revision); if (alive.current) { setServer(result); setDraft(editable(result)); setSnapshot(JSON.stringify(editable(result))); onSaved(result); setNotice(pick("Version restored. Previous writing remains in version history.", "সংস্করণ ফিরিয়ে আনা হয়েছে। আগের লেখা সংস্করণের ইতিহাসে আছে।")); } const history = await api.getWritingVersions(server.id); if (alive.current) setVersions(history); })}>{pick("Restore", "ফিরিয়ে আনুন")}</button></li>)}</ul></div></details>
      <div className={styles.export}><label>{pick("Export format", "রপ্তানির বিন্যাস")}<select value={format} disabled={busy} onChange={(event) => setFormat(event.target.value as WritingExportFormat)}><option value="md">Markdown</option><option value="tex">LaTeX</option><option value="docx">Word (.docx)</option><option value="pdf">PDF</option></select></label><label>{pick("Bibliography style", "গ্রন্থপঞ্জির রীতি")}<select value={style} disabled={busy} onChange={(event) => setStyle(event.target.value as CitationStyle)}>{Object.entries(styleNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label><button type="button" className="button secondary" disabled={busy} onClick={() => run(async () => { const saved = await save(false); if (!saved) return; const file = await api.exportWriting(server.id, format, style); if (alive.current) downloadPrivateFile(file, `${draft.title}.${format}`); })}>{pick("Save & export", "সংরক্ষণ ও রপ্তানি")}</button></div>
    </div>
    <section className={`card ${styles.form}`} aria-label={pick("AI drafting assistance", "এআই লেখার সহায়তা")}>
      <h2>{pick("AI drafting assistant", "এআই লেখার সহকারী")}</h2>
      <p className="notice">{pick("AI suggestions never replace your text automatically. Review evidence and academic integrity before choosing Insert suggestion.", "এআই পরামর্শ কখনো নিজে থেকে আপনার লেখা বদলায় না। পরামর্শ যুক্ত করার আগে প্রমাণ ও গবেষণার সততা যাচাই করুন।")}</p>
      {!prefs?.allow_external_ai && <p className="muted text-xs">{pick("External AI is disabled. Local/offline assistance is available.", "বাহ্যিক এআই বন্ধ। স্থানীয়/অফলাইন সহায়তা পাওয়া যাবে।")} <Link href="/settings">{pick("Settings", "সেটিংস")}</Link></p>}
      {usage && <p className="muted text-xs">{usage.hourly.remaining_requests} {pick("requests remaining this hour", "অনুরোধ এই ঘণ্টায় অবশিষ্ট")} · {usage.hourly.remaining_tokens.toLocaleString(locale)} {pick("tokens", "টোকেন")}</p>}
      <div className={styles.grid}><label>{pick("Task", "কাজ")}<select value={action} disabled={busy} onChange={(event) => setAction(event.target.value as WritingAction)}><option value="draft_section">{pick("Draft section from evidence", "প্রমাণ থেকে বিভাগের খসড়া")}</option><option value="tone">{pick("Academic tone", "গবেষণার ভাষাশৈলী")}</option><option value="grammar">{pick("Grammar check", "ব্যাকরণ যাচাই")}</option><option value="paraphrase">{pick("Paraphrase", "ভাষান্তরে পুনর্লিখন")}</option></select></label><label>{pick("Section", "বিভাগ")}<select value={section} disabled={busy} onChange={(event) => setSection(event.target.value as WritingSection)}>{Object.entries(sectionNames).map(([value, names]) => <option key={value} value={value}>{pick(...names)}</option>)}</select></label></div>
      {action !== "draft_section" && <><label>{pick("Text to improve (up to 1,500 characters, kept separate)", "যে লেখা উন্নত করবেন (সর্বোচ্চ ১,৫০০ অক্ষর, আলাদা থাকবে)")}<textarea value={rewrite} rows={4} maxLength={1500} disabled={busy} onChange={(event) => setRewrite(event.target.value)} /></label><p className="muted text-xs">{pick("Offline editing may return your original wording. Review the suggestion before inserting it.", "অফলাইন সম্পাদনায় আপনার মূল লেখাই ফিরে আসতে পারে। যুক্ত করার আগে পরামর্শ যাচাই করুন।")}</p></>}
      <fieldset disabled={busy}><legend>{action === "draft_section" ? pick("Choose 1–5 indexed sources with library references", "লাইব্রেরির তথ্যসূত্রসহ ১–৫টি ইনডেক্স করা উৎস বাছুন") : pick("Optional indexed sources (up to 5)", "ঐচ্ছিক ইনডেক্স করা উৎস (সর্বোচ্চ ৫টি)")}</legend><label>{pick("Find papers", "গবেষণাপত্র খুঁজুন")}<input value={paperQuery} onChange={(event) => { setPaperQuery(event.target.value); setPaperPage(1); }} /></label><div className={styles.paperList}>{papers.map((paper) => <label className={styles.choice} key={paper.id}><input type="checkbox" disabled={paper.document?.status !== "completed" || (!selected.includes(paper.id) && selected.length >= 5)} checked={selected.includes(paper.id)} onChange={() => setSelected((ids) => ids.includes(paper.id) ? ids.filter((id) => id !== paper.id) : [...ids, paper.id])} /><span>{paper.title}<small>{paper.document?.status === "completed" ? pick("Indexed", "ইনডেক্স সম্পন্ন") : pick("PDF not indexed", "পিডিএফ ইনডেক্স হয়নি")}</small></span></label>)}</div><div className={styles.row}><button type="button" disabled={paperPage <= 1} onClick={() => setPaperPage((v) => v - 1)}>{pick("Previous", "আগের")}</button><span>{paperPage} / {Math.max(1, paperPages)}</span><button type="button" disabled={paperPage >= paperPages} onClick={() => setPaperPage((v) => v + 1)}>{pick("Next", "পরের")}</button></div></fieldset>
      <label>{pick("Inference", "উত্তর তৈরির ব্যবস্থা")}<select value={provider} disabled={busy} onChange={(event) => setProvider(event.target.value as AIProvider)}><option value="auto">{pick("Default", "ডিফল্ট")}</option><option value="offline">{pick("Offline source excerpts", "অফলাইন উৎসের উদ্ধৃতি")}</option><option value="local">{pick("Local AI", "স্থানীয় এআই")}</option><option value="cloud" disabled={!prefs?.allow_external_ai}>{pick("Cloud AI (consent required)", "ক্লাউড এআই (অনুমতি প্রয়োজন)")}</option></select></label>
      <button type="button" className="button primary" disabled={busy || (action === "draft_section" ? !selected.length : !rewrite.trim())} onClick={assist}>{assisting ? pick("Preparing suggestion…", "পরামর্শ তৈরি হচ্ছে…") : pick("Generate separate suggestion", "আলাদা পরামর্শ তৈরি করুন")}</button>
      <div aria-live="polite" className={styles.suggestions}>{suggestions.map((suggestion, index) => <article key={`${suggestion.id}-${index}`} className={styles.suggestion}><span className="tag">{pick("AI-generated suggestion", "এআই-তৈরি পরামর্শ")}</span><p className={styles.pre}>{suggestion.content_markdown}</p><small className="muted">{suggestion.provider_used} · {suggestion.model_used}</small><div>{suggestion.evidence_links.map((link, i) => <details key={i}><summary>{link.paper_title} · {pick("p.", "পৃষ্ঠা")} {link.page_number}</summary><blockquote>{link.quoted_snippet}</blockquote></details>)}</div><button type="button" className="button secondary small" disabled={busy} onClick={() => { setDraft((old) => insertWritingSuggestion(old, suggestion)); setNotice(pick("Suggestion inserted for your review. Save when ready.", "আপনার যাচাইয়ের জন্য পরামর্শ যুক্ত হয়েছে। প্রস্তুত হলে সংরক্ষণ করুন।")); }}>{pick("Insert suggestion into my draft", "আমার খসড়ায় পরামর্শ যুক্ত করুন")}</button></article>)}</div>
    </section>
  </section>;
}
