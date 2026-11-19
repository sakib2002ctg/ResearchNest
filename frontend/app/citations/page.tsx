"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { AppShell } from "@/components/AppShell";
import { api, ApiError, type Citation, type CitationEntryType, type CitationInput, type CitationStyle, type FormattedReferences, type LibraryPaper, type ReferenceFormat } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadPrivateFile } from "@/lib/download";
import { useI18n } from "@/lib/i18n";
import { LibraryDialog } from "../library/DocumentViewer";
import styles from "./workspace.module.css";

const styleNames: Record<CitationStyle, string> = { apa: "APA 7", ieee: "IEEE", mla: "MLA 9", chicago: "Chicago", harvard: "Harvard" };
const empty = { cite_key: "", entry_type: "article" as CitationEntryType, title: "", authors: "", year: "", venue: "", volume: "", issue: "", pages: "", doi: "", url: "", publisher: "" };
type FormValues = typeof empty;

export default function CitationsPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("Reference manager", "তথ্যসূত্র ব্যবস্থাপক")} description={pick("Organize references, review metadata, and export your bibliography.", "তথ্যসূত্র সাজান, মেটাডেটা যাচাই করুন এবং গ্রন্থপঞ্জি রপ্তানি করুন।")} showHeading>{user && <Workspace key={user.id} />}</AppShell>;
}

function Workspace() {
  const { pick } = useI18n();
  const [items, setItems] = useState<Citation[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [query, setQuery] = useState("");
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<number[]>([]);
  const [style, setStyle] = useState<CitationStyle>("apa");
  const [formatted, setFormatted] = useState<FormattedReferences | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState<"metadata" | "import" | "library" | null>(null);
  const [editing, setEditing] = useState<Citation | null>(null);
  const [draft, setDraft] = useState<FormValues>(empty);
  const [doi, setDoi] = useState("");
  const [importFormat, setImportFormat] = useState<ReferenceFormat>("bibtex");
  const [importText, setImportText] = useState("");
  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [paperQuery, setPaperQuery] = useState("");
  const [paperPage, setPaperPage] = useState(1);
  const [paperPages, setPaperPages] = useState(1);
  const alive = useRef(true);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    let current = true;
    api.getCitations(50, offset, query || undefined).then((result) => { if (current) { setItems(result); setHasMore(result.length === 50); } })
      .catch(() => { if (current) setError("Unable to load references / তথ্যসূত্র লোড হয়নি।"); });
    return () => { current = false; };
  }, [offset, query, revision]);
  useEffect(() => {
    if (modal !== "library") return;
    let current = true;
    api.getLibrary({ page: paperPage, size: 30, q: paperQuery || undefined }).then((result) => { if (current) { setPapers(result.items); setPaperPages(result.pages); } })
      .catch(() => { if (current) setError("Unable to load library / লাইব্রেরি লোড হয়নি।"); });
    return () => { current = false; };
  }, [modal, paperPage, paperQuery]);

  async function action(work: () => Promise<void>) {
    setPending(true); setError(""); setNotice("");
    try { await work(); } catch (cause) {
      if (alive.current) setError(cause instanceof ApiError && cause.status === 409
        ? pick("This reference conflicts with existing metadata or is in use. Review it before retrying.", "এই তথ্যসূত্রের তথ্য মিলে যাচ্ছে অথবা এটি ব্যবহৃত হচ্ছে। যাচাই করে আবার চেষ্টা করুন।")
        : pick("The request could not be completed. Check the metadata and try again.", "অনুরোধ সম্পন্ন হয়নি। তথ্য দেখে আবার চেষ্টা করুন।"));
    } finally { if (alive.current) setPending(false); }
  }

  function edit(item?: Citation) {
    setError("");
    setEditing(item || null);
    setDraft(item ? { cite_key: item.cite_key, entry_type: item.entry_type, title: item.title, authors: item.authors.join("\n"), year: item.year === null ? "" : String(item.year), venue: item.venue || "", volume: item.volume || "", issue: item.issue || "", pages: item.pages || "", doi: item.doi || "", url: item.url || "", publisher: item.publisher || "" } : empty);
    setModal("metadata");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await action(async () => {
      const body: CitationInput = { ...draft, authors: draft.authors.split("\n").map((value) => value.trim()).filter(Boolean), year: draft.year ? Number(draft.year) : null,
        venue: draft.venue || null, volume: draft.volume || null, issue: draft.issue || null, pages: draft.pages || null, doi: draft.doi || null, url: draft.url || null, publisher: draft.publisher || null };
      if (!body.cite_key) delete body.cite_key;
      const result = editing ? await api.updateCitation(editing.id, body) : await api.createCitation(body);
      if (alive.current) { setModal(null); setRevision((v) => v + 1); setFormatted(null); setNotice(result.warnings.length ? result.warnings.join(" ") : pick("Reference saved.", "তথ্যসূত্র সংরক্ষিত।")); }
    });
  }

  async function exportFile(format: ReferenceFormat) {
    await action(async () => { const result = await api.exportCitations(format, selected); if (alive.current) downloadPrivateFile(result, `references.${format === "bibtex" ? "bib" : "ris"}`); });
  }

  return <>
    {error && <p role="alert" className="notice error">{error}</p>}{notice && <p role="status" className="notice">{notice}</p>}
    <div className={styles.toolbar}>
      <button type="button" className="button primary" disabled={pending} onClick={() => edit()}>{pick("Add reference", "তথ্যসূত্র যোগ করুন")}</button>
      <button type="button" className="button secondary" disabled={pending} onClick={() => setModal("library")}>{pick("From my library", "আমার লাইব্রেরি থেকে")}</button>
      <button type="button" className="button secondary" disabled={pending} onClick={() => setModal("import")}>{pick("Import BibTeX / RIS", "BibTeX / RIS আমদানি")}</button>
      <button type="button" className="button secondary" disabled={pending} onClick={() => exportFile("bibtex")}>{pick("Export BibTeX", "BibTeX রপ্তানি")}</button>
      <button type="button" className="button secondary" disabled={pending} onClick={() => exportFile("ris")}>{pick("Export RIS", "RIS রপ্তানি")}</button>
    </div>
    <form className={`card ${styles.doi}`} onSubmit={(event) => { event.preventDefault(); void action(async () => { const result = await api.createCitation({ doi: doi.trim() }); if (alive.current) { setDoi(""); setRevision((v) => v + 1); setNotice(result.warnings.join(" ") || pick("DOI reference saved.", "DOI তথ্যসূত্র সংরক্ষিত।")); } }); }}>
      <label>{pick("Resolve a DOI", "DOI দিয়ে তথ্য খুঁজুন")}<input required value={doi} maxLength={255} disabled={pending} placeholder="10.1000/example" onChange={(event) => setDoi(event.target.value)} /></label><button className="button secondary" disabled={pending}>{pick("Look up & save", "খুঁজে সংরক্ষণ করুন")}</button>
    </form>
    <div className={styles.workspace}>
      <section className="card">
        <div className={styles.heading}><h2>{pick("My references", "আমার তথ্যসূত্র")}</h2><span className="muted text-xs">{selected.length} {pick("selected", "নির্বাচিত")}</span></div>
        <label className={styles.search}>{pick("Search references", "তথ্যসূত্র খুঁজুন")}<input value={query} disabled={pending} maxLength={250} onChange={(event) => { setQuery(event.target.value); setOffset(0); }} /></label>
        <div className={styles.toolbar}><button type="button" disabled={pending} onClick={() => setSelected((ids) => [...new Set([...ids, ...items.map((item) => item.id)])].slice(0, 200))}>{pick("Select visible (up to 200)", "দৃশ্যমানগুলো বাছুন (সর্বোচ্চ ২০০)")}</button><button type="button" disabled={pending} onClick={() => setSelected([])}>{pick("Clear selection", "নির্বাচন মুছুন")}</button></div>
        {items.length === 0 ? <div className="empty-state"><h3>{pick("No references yet", "এখনো তথ্যসূত্র নেই")}</h3><p>{pick("Add a paper, resolve a DOI, or import your bibliography.", "গবেষণাপত্র যোগ করুন, DOI দিয়ে খুঁজুন, অথবা গ্রন্থপঞ্জি আমদানি করুন।")}</p></div> : <ul className={styles.list}>{items.map((item) => <li key={item.id}>
          <label className={styles.choice}><input type="checkbox" disabled={pending || (selected.length >= 200 && !selected.includes(item.id))} checked={selected.includes(item.id)} onChange={() => setSelected((ids) => ids.includes(item.id) ? ids.filter((id) => id !== item.id) : [...ids, item.id])} /><strong>{item.title}</strong></label>
          <p className="muted text-sm">{item.authors.join("; ") || pick("Authors not specified", "লেখকের নাম উল্লেখ নেই")} · {item.year ?? pick("No date", "তারিখ নেই")}</p>
          <p className="text-xs"><code>[@{item.cite_key}]</code> <span className="tag">{item.is_verified ? pick("Verified metadata", "যাচাই করা মেটাডেটা") : pick("Review metadata", "মেটাডেটা যাচাই করুন")}</span></p>
          {item.venue && <p className="muted text-xs">{item.venue}</p>}{item.doi && <p className="muted text-xs">DOI: {item.doi}</p>}
          {item.warnings.length > 0 && <p className="muted text-xs">{item.warnings.join(" ")}</p>}
          <div className={styles.toolbar}><button type="button" disabled={pending} onClick={() => edit(item)}>{pick("Edit", "সম্পাদনা")}</button><button type="button" disabled={pending} onClick={() => action(async () => { await api.deleteCitation(item.id); if (alive.current) { setSelected((ids) => ids.filter((id) => id !== item.id)); setFormatted(null); setRevision((v) => v + 1); } })}>{pick("Delete", "মুছুন")}</button></div>
        </li>)}</ul>}
        <div className={styles.heading}><button type="button" disabled={pending || offset === 0} onClick={() => setOffset((v) => Math.max(0, v - 50))}>{pick("Previous", "আগের")}</button><span>{Math.floor(offset / 50) + 1}</span><button type="button" disabled={pending || !hasMore} onClick={() => setOffset((v) => v + 50)}>{pick("Next", "পরের")}</button></div>
      </section>
      <section className={`card ${styles.formatter}`}>
        <h2>{pick("Bibliography formatter", "গ্রন্থপঞ্জি বিন্যাস")}</h2>
        <label>{pick("Citation style", "তথ্যসূত্রের রীতি")}<select value={style} disabled={pending} onChange={(event) => setStyle(event.target.value as CitationStyle)}>{Object.entries(styleNames).map(([value, name]) => <option key={value} value={value}>{name}</option>)}</select></label>
        <button type="button" className="button primary" disabled={pending || (selected.length === 0 && items.length === 0)} onClick={() => action(async () => { const result = await api.formatCitations(selected.length ? selected : items.map((item) => item.id), style); if (alive.current) setFormatted(result); })}>{selected.length ? pick("Format selected references", "নির্বাচিত তথ্যসূত্র সাজান") : pick("Format visible references", "দৃশ্যমান তথ্যসূত্র সাজান")}</button>
        <p className="muted text-xs">{pick("Exports include selected references, or your full reference library when nothing is selected. Review incomplete metadata before publication.", "রপ্তানিতে নির্বাচিত তথ্যসূত্র থাকবে; কিছু বাছাই না করলে পুরো তথ্যসূত্রের লাইব্রেরি থাকবে। প্রকাশের আগে অসম্পূর্ণ তথ্য যাচাই করুন।")}</p>
        {formatted && <div aria-live="polite"><p className="tag">{styleNames[formatted.style]}</p>{formatted.entries.map((entry) => <article className={styles.formatted} key={entry.citation_id}><code>{entry.in_text}</code><p>{entry.bibliography}</p><small className="muted">{entry.cite_key}</small></article>)}{formatted.warnings.map((warning, i) => <p key={i} className="muted text-xs">{warning}</p>)}</div>}
      </section>
    </div>
    {modal === "metadata" && <LibraryDialog title={editing ? pick("Edit reference", "তথ্যসূত্র সম্পাদনা") : pick("Add reference", "তথ্যসূত্র যোগ করুন")} onClose={() => { if (!pending) setModal(null); }} wide>
      <form className={styles.form} onSubmit={save}>
        {error && <p role="alert" className="notice error">{error}</p>}
        <label>{pick("Title", "শিরোনাম")}<input required value={draft.title} maxLength={500} disabled={pending} onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></label>
        <label>{pick("Authors (one per line)", "লেখকের নাম (প্রতি লাইনে একটি)")}<textarea value={draft.authors} rows={3} maxLength={6000} disabled={pending} onChange={(event) => setDraft({ ...draft, authors: event.target.value })} /></label>
        <div className={styles.grid}><label>{pick("Citation key", "তথ্যসূত্রের কী")}<input value={draft.cite_key} maxLength={80} pattern="[A-Za-z][A-Za-z0-9_:-]*" readOnly={Boolean(editing)} disabled={pending} onChange={(event) => setDraft({ ...draft, cite_key: event.target.value })} placeholder={pick("Generated if empty", "ফাঁকা রাখলে তৈরি হবে")} /></label><label>{pick("Type", "ধরন")}<select disabled={pending} value={draft.entry_type} onChange={(event) => setDraft({ ...draft, entry_type: event.target.value as CitationEntryType })}>{["article", "inproceedings", "book", "misc", "preprint"].map((value) => <option key={value}>{value}</option>)}</select></label></div>
        <div className={styles.grid}><label>{pick("Year", "বছর")}<input type="number" min={1000} max={2200} value={draft.year} disabled={pending} onChange={(event) => setDraft({ ...draft, year: event.target.value })} /></label><label>{pick("Journal / conference", "সাময়িকী / সম্মেলন")}<input value={draft.venue} maxLength={500} disabled={pending} onChange={(event) => setDraft({ ...draft, venue: event.target.value })} /></label></div>
        <div className={styles.grid}>{(["volume", "issue", "pages"] as const).map((field) => <label key={field}>{field === "volume" ? pick("Volume", "খণ্ড") : field === "issue" ? pick("Issue", "সংখ্যা") : pick("Pages", "পৃষ্ঠা")}<input value={draft[field]} maxLength={field === "pages" ? 100 : 50} disabled={pending} onChange={(event) => setDraft({ ...draft, [field]: event.target.value })} /></label>)}</div>
        <label>DOI<input value={draft.doi} maxLength={255} disabled={pending} onChange={(event) => setDraft({ ...draft, doi: event.target.value })} /></label><label>URL<input type="url" value={draft.url} maxLength={2048} disabled={pending} onChange={(event) => setDraft({ ...draft, url: event.target.value })} /></label><label>{pick("Publisher", "প্রকাশক")}<input value={draft.publisher} maxLength={500} disabled={pending} onChange={(event) => setDraft({ ...draft, publisher: event.target.value })} /></label>
        <button className="button primary" disabled={pending}>{pick("Save reference", "তথ্যসূত্র সংরক্ষণ করুন")}</button>
      </form>
    </LibraryDialog>}
    {modal === "import" && <LibraryDialog title={pick("Import references", "তথ্যসূত্র আমদানি")} onClose={() => { if (!pending) setModal(null); }} wide>
      <form className={styles.form} onSubmit={(event) => { event.preventDefault(); void action(async () => { const result = await api.importCitations(importFormat, importText); if (alive.current) { setModal(null); setImportText(""); setRevision((v) => v + 1); setNotice(`${result.created} ${pick("created", "তৈরি")}; ${result.duplicates} ${pick("duplicates", "আগে আছে")}. ${result.warnings.join(" ")}`); } }); }}>
        {error && <p role="alert" className="notice error">{error}</p>}
        <label>{pick("Format", "বিন্যাস")}<select value={importFormat} disabled={pending} onChange={(event) => setImportFormat(event.target.value as ReferenceFormat)}><option value="bibtex">BibTeX (.bib)</option><option value="ris">RIS (.ris)</option></select></label>
        <label>{pick("Load a file", "ফাইল খুলুন")}<input type="file" accept=".bib,.ris" disabled={pending} onChange={async (event) => { const file = event.target.files?.[0]; if (!file) return; if (file.size > 500000) { setError(pick("Choose a file smaller than 500 KB.", "৫০০ কেবির ছোট ফাইল বাছুন।")); return; } const text = await file.text(); if (alive.current) { setImportText(text); setImportFormat(file.name.toLowerCase().endsWith(".ris") ? "ris" : "bibtex"); } }} /></label>
        <label>{pick("BibTeX / RIS text", "BibTeX / RIS লেখা")}<textarea required rows={12} maxLength={500000} value={importText} disabled={pending} onChange={(event) => setImportText(event.target.value)} spellCheck={false} /></label><button className="button primary" disabled={pending}>{pick("Import & deduplicate", "আমদানি ও সদৃশ বাদ দিন")}</button>
      </form>
    </LibraryDialog>}
    {modal === "library" && <LibraryDialog title={pick("Add from my library", "আমার লাইব্রেরি থেকে যোগ করুন")} onClose={() => { if (!pending) setModal(null); }} wide>
      {error && <p role="alert" className="notice error">{error}</p>}
      <label className={styles.search}>{pick("Find saved papers", "সংরক্ষিত গবেষণাপত্র খুঁজুন")}<input value={paperQuery} disabled={pending} onChange={(event) => { setPaperQuery(event.target.value); setPaperPage(1); }} /></label>
      <ul className={styles.list}>{papers.map((paper) => <li key={paper.id}><strong>{paper.title}</strong><button type="button" className="button secondary small" disabled={pending} onClick={() => action(async () => { const result = await api.createCitation({ user_paper_id: paper.id }); if (alive.current) { setRevision((v) => v + 1); setNotice(result.warnings.join(" ") || pick("Reference saved.", "তথ্যসূত্র সংরক্ষিত।")); setModal(null); } })}>{pick("Add reference", "তথ্যসূত্র যোগ করুন")}</button></li>)}</ul>
      <div className={styles.heading}><button type="button" disabled={pending || paperPage <= 1} onClick={() => setPaperPage((v) => v - 1)}>{pick("Previous", "আগের")}</button><span>{paperPage} / {Math.max(1, paperPages)}</span><button type="button" disabled={pending || paperPage >= paperPages} onClick={() => setPaperPage((v) => v + 1)}>{pick("Next", "পরের")}</button></div>
    </LibraryDialog>}
  </>;
}
