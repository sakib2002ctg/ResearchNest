"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { api, type PaginatedPapers } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const blankPaper = { title: "", authors: "", abstract: "", source: "", url: "" };

export default function LibraryPage() {
  const { isAuthenticated } = useAuth();
  const { pick, locale } = useI18n();
  const [data, setData] = useState<PaginatedPapers | null>(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [draft, setDraft] = useState(blankPaper);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [notice, setNotice] = useState<"added" | "deleted" | "failed" | null>(null);
  const requestNumber = useRef(0);

  const load = useCallback(async (showLoading = true) => {
    if (!isAuthenticated) return;
    const request = ++requestNumber.current;
    if (showLoading) setLoading(true);
    setFailed(false);
    try {
      const result = query ? await api.searchPapers(query, page, 10) : await api.getPapers(page, 10);
      if (request === requestNumber.current) setData(result);
    } catch {
      if (request === requestNumber.current) setFailed(true);
    } finally {
      if (request === requestNumber.current) setLoading(false);
    }
  }, [isAuthenticated, page, query]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(false), 0);
    return () => {
      window.clearTimeout(timer);
      requestNumber.current += 1;
    };
  }, [load]);

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setFailed(false);
    setQuery(searchInput.trim());
    setPage(1);
  }

  function changePage(update: (current: number) => number) {
    setLoading(true);
    setFailed(false);
    setPage(update);
  }

  async function addPaper(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving || !draft.title.trim()) return;
    setSaving(true);
    setNotice(null);
    try {
      await api.createPaper({
        title: draft.title.trim(), authors: draft.authors.trim() || null,
        abstract: draft.abstract.trim() || null, source: draft.source.trim() || null,
        url: draft.url.trim() || null,
      });
      setDraft(blankPaper);
      setShowAdd(false);
      setNotice("added");
      setLoading(true);
      setFailed(false);
      setPage(1);
      setQuery("");
      setSearchInput("");
      if (page === 1 && !query) await load();
    } catch {
      setNotice("failed");
    } finally {
      setSaving(false);
    }
  }

  async function deletePaper(id: number) {
    if (deleting !== null) return;
    setDeleting(id);
    setNotice(null);
    try {
      await api.deletePaper(id);
      setConfirmDelete(null);
      setNotice("deleted");
      if (data?.items.length === 1 && page > 1) setPage((current) => current - 1);
      else await load();
    } catch {
      setNotice("failed");
    } finally {
      setDeleting(null);
    }
  }

  const number = (value: number) => new Intl.NumberFormat(locale).format(value);
  const field = (key: keyof typeof blankPaper, value: string) => setDraft((current) => ({ ...current, [key]: value }));

  return <AppShell title={pick("My library", "আমার লাইব্রেরি")} description={pick("Keep your sources close and your questions open.", "উৎসগুলো কাছে রাখুন, প্রশ্নের পথ খোলা থাকুক।")}>
    <div className="page-heading"><div><p className="eyebrow">{pick("YOUR PERSONAL KNOWLEDGE SHELF", "আপনার নিজের জ্ঞানের সংগ্রহ")}</p><h1>{pick("A home for your research.", "আপনার গবেষণার নিজস্ব ঠিকানা।")}</h1><p className="muted">{pick("Saved papers, useful sources, and ideas worth returning to.", "সংরক্ষিত গবেষণাপত্র, দরকারি উৎস এবং ফিরে দেখার মতো ভাবনা।")}</p></div><button className="button primary" type="button" onClick={() => setShowAdd((current) => !current)} aria-expanded={showAdd} aria-controls="add-paper-form"><Icon name={showAdd ? "x" : "plus"} size={17} />{showAdd ? pick("Close form", "ফর্ম বন্ধ করুন") : pick("Add a paper", "গবেষণাপত্র যোগ করুন")}</button></div>

    <div aria-live="polite">{notice && <div className={`notice ${notice === "failed" ? "error" : "success"}`} role={notice === "failed" ? "alert" : "status"}>{notice === "added" ? pick("Paper added to your library.", "গবেষণাপত্রটি আপনার লাইব্রেরিতে যোগ হয়েছে।") : notice === "deleted" ? pick("Paper removed from your library.", "গবেষণাপত্রটি আপনার লাইব্রেরি থেকে সরানো হয়েছে।") : pick("The change could not be saved. Please try again.", "পরিবর্তনটি সংরক্ষণ করা যায়নি। আবার চেষ্টা করুন।")}</div>}</div>

    {showAdd && <section className="card mb-6" id="add-paper-form"><div className="section-heading"><div><h2>{pick("Add a paper manually", "নিজে গবেষণাপত্র যোগ করুন")}</h2><p className="muted text-sm">{pick("Only a title is required. You can keep the other details simple.", "শুধু শিরোনাম দেওয়া আবশ্যক। অন্য তথ্যগুলো প্রয়োজনে দিন।")}</p></div></div><form className="form-stack" onSubmit={addPaper}>
      <label className="field" htmlFor="paper-title"><span>{pick("Paper title", "গবেষণাপত্রের শিরোনাম")}</span><input id="paper-title" required minLength={1} maxLength={255} value={draft.title} onChange={(event) => field("title", event.target.value)} /></label>
      <div className="inline-fields"><label className="field" htmlFor="paper-authors"><span>{pick("Authors", "লেখকবৃন্দ")}</span><input id="paper-authors" maxLength={255} value={draft.authors} onChange={(event) => field("authors", event.target.value)} /></label><label className="field" htmlFor="paper-source"><span>{pick("Publication or source", "প্রকাশনা বা উৎস")}</span><input id="paper-source" maxLength={100} value={draft.source} onChange={(event) => field("source", event.target.value)} /></label></div>
      <label className="field" htmlFor="paper-url"><span>{pick("Original paper URL", "মূল গবেষণাপত্রের লিংক")}</span><input id="paper-url" type="url" maxLength={500} value={draft.url} placeholder="https://" onChange={(event) => field("url", event.target.value)} /></label>
      <label className="field" htmlFor="paper-abstract"><span>{pick("Abstract", "সারসংক্ষেপ")}</span><textarea id="paper-abstract" rows={4} maxLength={5000} value={draft.abstract} onChange={(event) => field("abstract", event.target.value)} /></label>
      <div className="flex gap-3"><button type="submit" className="button primary" disabled={saving}>{saving ? pick("Saving…", "সংরক্ষণ হচ্ছে…") : pick("Save to library", "লাইব্রেরিতে সংরক্ষণ করুন")}</button><button type="button" className="button secondary" onClick={() => setShowAdd(false)} disabled={saving}>{pick("Cancel", "বাতিল")}</button></div>
    </form></section>}

    <section className="card mb-6"><form className="search-form" onSubmit={search}><label className="field flex-1" htmlFor="library-query"><span className="sr-only">{pick("Search your library", "আপনার লাইব্রেরিতে খুঁজুন")}</span><input type="search" id="library-query" maxLength={300} value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder={pick("Search titles, authors, and abstracts…", "শিরোনাম, লেখক ও সারসংক্ষেপ খুঁজুন…")} /></label><button className="button secondary" type="submit" disabled={loading}><Icon name="search" size={17} />{pick("Search library", "লাইব্রেরিতে খুঁজুন")}</button>{query && <button className="button ghost" type="button" onClick={() => { setQuery(""); setSearchInput(""); setPage(1); }}>{pick("Clear", "মুছুন")}</button>}</form></section>

    {loading && <div className="loading-state" role="status">{pick("Opening your library…", "আপনার লাইব্রেরি খোলা হচ্ছে…")}</div>}
    {failed && <div className="notice error" role="alert"><p>{pick("Your library could not be loaded.", "আপনার লাইব্রেরি লোড করা যায়নি।")}</p><button type="button" className="button secondary small" onClick={() => void load()}>{pick("Try again", "আবার চেষ্টা করুন")}</button></div>}
    {!loading && !failed && data && <>
      <div className="section-heading mb-4"><h2>{query ? pick("Matching papers", "মিলে যাওয়া গবেষণাপত্র") : pick("All saved papers", "সব সংরক্ষিত গবেষণাপত্র")}</h2><span className="muted text-sm">{number(data.total)} {pick("papers", "টি গবেষণাপত্র")}</span></div>
      {data.items.length === 0 ? <section className="card empty-state"><Icon name="library" size={32} /><h2>{query ? pick("No papers match your search", "অনুসন্ধানের সাথে কোনো গবেষণাপত্র মেলেনি") : pick("A fresh shelf, full of possibility.", "খালি সংগ্রহেও রয়েছে নতুন সম্ভাবনা।")}</h2><p>{query ? pick("Try different words or clear the search to see your library.", "অন্য শব্দ দিয়ে চেষ্টা করুন অথবা পুরো লাইব্রেরি দেখতে অনুসন্ধান মুছুন।") : pick("Add your first paper or explore discoveries to get started.", "প্রথম গবেষণাপত্র যোগ করুন অথবা নতুন গবেষণার খোঁজ নিন।")}</p><button className="button secondary" type="button" onClick={() => setShowAdd(true)}>{pick("Add a paper", "গবেষণাপত্র যোগ করুন")}</button></section> : <div className="paper-list">{data.items.map((paper) => <article key={paper.id} className="card paper-card"><div className="flex items-start gap-4"><span className="mt-1 shrink-0 rounded-xl bg-[var(--accent-soft)] p-3"><Icon name="file-text" size={20} /></span><div className="min-w-0 flex-1"><span className="tag">{paper.source || pick("Research paper", "গবেষণাপত্র")}</span><h2 className="mt-2 text-xl">{paper.title}</h2><p className="muted mt-2 text-sm">{paper.authors || pick("Authors not listed", "লেখকের তথ্য নেই")}</p>{paper.abstract && <p className="muted mt-3 line-clamp-3 text-sm leading-7">{paper.abstract}</p>}<div className="mt-4 flex flex-wrap items-center justify-between gap-3">{paper.url ? <a href={paper.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm font-medium">{pick("Read original", "মূল প্রকাশনা পড়ুন")}<Icon name="external-link" size={14} /></a> : <span className="muted text-xs">{pick("No source link added", "উৎসের লিংক দেওয়া নেই")}</span>}{confirmDelete === paper.id ? <div className="flex flex-wrap items-center gap-2"><span className="text-sm">{pick("Remove this paper?", "গবেষণাপত্রটি সরাবেন?")}</span><button className="button danger small" type="button" disabled={deleting !== null} onClick={() => void deletePaper(paper.id)}>{deleting === paper.id ? pick("Removing…", "সরানো হচ্ছে…") : pick("Remove", "সরান")}</button><button className="button ghost small" type="button" onClick={() => setConfirmDelete(null)} disabled={deleting !== null}>{pick("Cancel", "বাতিল")}</button></div> : <button type="button" className="button ghost small" disabled={deleting !== null} onClick={() => setConfirmDelete(paper.id)}><Icon name="trash" size={15} />{pick("Remove", "সরান")}</button>}</div></div></div></article>)}</div>}
      {data.pages > 1 && <nav className="mt-6 flex flex-wrap items-center justify-between gap-3" aria-label={pick("Library pages", "লাইব্রেরির পৃষ্ঠা")}><button className="button secondary small" onClick={() => changePage((current) => current - 1)} disabled={page <= 1}>{pick("Previous", "আগের")}</button><span className="muted text-sm">{pick("Page", "পৃষ্ঠা")} {number(page)} {pick("of", "/")} {number(data.pages)}</span><button className="button secondary small" onClick={() => changePage((current) => current + 1)} disabled={page >= data.pages}>{pick("Next", "পরের")}</button></nav>}
    </>}
  </AppShell>;
}
