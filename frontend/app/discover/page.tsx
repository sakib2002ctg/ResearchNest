"use client";

import { useState, type FormEvent } from "react";

import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { api, type ExternalPaper } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function DiscoverPage() {
  const { pick, locale } = useI18n();
  const [query, setQuery] = useState("");
  const [papers, setPapers] = useState<ExternalPaper[]>([]);
  const [total, setTotal] = useState(0);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<Set<string>>(new Set());
  const [saveFailed, setSaveFailed] = useState(false);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading || query.trim().length < 2) return;
    setLoading(true);
    setFailed(false);
    setSaveFailed(false);
    setSearched(true);
    try {
      const result = await api.searchResearch(query.trim(), 20);
      setPapers(result.papers);
      setTotal(result.total);
    } catch {
      setFailed(true);
      setPapers([]);
    } finally {
      setLoading(false);
    }
  }

  async function save(paper: ExternalPaper) {
    setSaving(paper.url);
    setSaveFailed(false);
    try {
      await api.createPaper({
        title: paper.title.slice(0, 255), authors: paper.authors.join(", ").slice(0, 255),
        abstract: paper.abstract.slice(0, 5000), source: paper.source.slice(0, 100), url: paper.url,
      });
      setSaved((current) => new Set(current).add(paper.url));
    } catch {
      setSaveFailed(true);
    } finally {
      setSaving(null);
    }
  }

  return <AppShell title={pick("Discover papers", "গবেষণাপত্র খুঁজুন")} description={pick("Follow a question. Find a new perspective.", "একটি প্রশ্নের সূত্র ধরে নতুন দৃষ্টিভঙ্গি খুঁজুন।")}>
    <div className="page-heading"><div><p className="eyebrow">{pick("LET CURIOSITY LEAD", "কৌতূহলই পথ দেখাক")}</p><h1>{pick("Find your next great read.", "খুঁজে নিন পরবর্তী গুরুত্বপূর্ণ গবেষণা।")}</h1><p className="muted">{pick("Search academic literature from arXiv and save what matters to you.", "arXiv-এর একাডেমিক প্রকাশনা খুঁজুন এবং গুরুত্বপূর্ণ গবেষণাপত্র সংরক্ষণ করুন।")}</p></div></div>
    <section className="card">
      <form onSubmit={search} className="search-form">
        <label className="field flex-1" htmlFor="discover-query"><span className="sr-only">{pick("Search research papers", "গবেষণাপত্র অনুসন্ধান")}</span><input id="discover-query" type="search" value={query} minLength={2} maxLength={300} onChange={(event) => setQuery(event.target.value)} placeholder={pick("A topic, a question, an idea…", "একটি বিষয়, একটি প্রশ্ন, একটি ভাবনা…")} required /></label>
        <button className="button primary" type="submit" disabled={loading}><Icon name="search" size={18} />{loading ? pick("Searching…", "খোঁজা হচ্ছে…") : pick("Search papers", "গবেষণাপত্র খুঁজুন")}</button>
      </form>
      <p className="muted mt-3 text-xs">{pick("Searches use the original publication metadata. Try specific English keywords for wider arXiv results.", "অনুসন্ধানে মূল প্রকাশনার তথ্য ব্যবহৃত হয়। arXiv-এ বেশি ফলাফলের জন্য নির্দিষ্ট ইংরেজি শব্দ ব্যবহার করতে পারেন।")}</p>
    </section>
    <div aria-live="polite">
      {failed && <div role="alert" className="notice error">{pick("Research search is unavailable right now. Please try again.", "গবেষণাপত্র অনুসন্ধান এই মুহূর্তে কাজ করছে না। আবার চেষ্টা করুন।")}</div>}
      {saveFailed && <div role="alert" className="notice error">{pick("The paper could not be saved. Please try again.", "গবেষণাপত্রটি সংরক্ষণ করা যায়নি। আবার চেষ্টা করুন।")}</div>}
      {loading && <div role="status" className="loading-state">{pick("Looking for useful connections…", "প্রাসঙ্গিক গবেষণা খোঁজা হচ্ছে…")}</div>}
      {!loading && searched && !failed && <div className="section-heading my-6"><h2>{pick("Search results", "অনুসন্ধানের ফলাফল")}</h2><span className="muted text-sm">{new Intl.NumberFormat(locale).format(total)} {pick("papers returned", "টি গবেষণাপত্র পাওয়া গেছে")}</span></div>}
    </div>
    {!loading && !searched && <section className="card empty-state py-16"><span className="rounded-full bg-[var(--accent-soft)] p-5"><Icon name="search" size={32} /></span><h2>{pick("A world of ideas, one search away.", "এক অনুসন্ধানেই ভাবনার নতুন জগৎ।")}</h2><p>{pick("Explore a research topic to start building your personal reading library.", "নিজের পাঠাগার গড়ে তুলতে একটি গবেষণার বিষয় অনুসন্ধান করুন।")}</p><div className="mt-4 flex flex-wrap justify-center gap-2">{["Machine learning", "Climate science", "Natural language processing"].map((topic, index) => <button key={topic} onClick={() => setQuery(topic)} type="button" className="tag">{pick(topic, ["মেশিন লার্নিং", "জলবায়ু বিজ্ঞান", "প্রাকৃতিক ভাষা প্রক্রিয়াকরণ"][index] ?? topic)}</button>)}</div></section>}
    {!loading && searched && !failed && papers.length === 0 && <section className="card empty-state"><Icon name="search" size={30} /><h2>{pick("No papers found for this search", "এই অনুসন্ধানে গবেষণাপত্র পাওয়া যায়নি")}</h2><p>{pick("Try a shorter query or different keywords.", "ছোট প্রশ্ন বা অন্য শব্দ দিয়ে চেষ্টা করুন।")}</p></section>}
    {!loading && papers.length > 0 && <div className="paper-list">{papers.map((paper, index) => <article className="card paper-card" key={`${paper.url}-${index}`}>
      <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0 flex-1"><span className="tag">{paper.source}</span><h2 className="mt-3 text-xl">{paper.title}</h2><p className="muted mt-2 text-sm">{paper.authors.join(", ") || pick("Authors not listed", "লেখকের তথ্য নেই")}</p></div><button className={`button small ${saved.has(paper.url) ? "secondary" : "primary"}`} type="button" disabled={saving !== null || saved.has(paper.url)} onClick={() => void save(paper)}><Icon name={saved.has(paper.url) ? "check" : "plus"} size={16} />{saved.has(paper.url) ? pick("Saved", "সংরক্ষিত") : saving === paper.url ? pick("Saving…", "সংরক্ষণ হচ্ছে…") : pick("Save paper", "সংরক্ষণ করুন")}</button></div>
      <p className="muted mt-4 line-clamp-4 text-sm leading-7">{paper.abstract || pick("No abstract provided.", "সারসংক্ষেপ দেওয়া নেই।")}</p>
      <a className="mt-5 inline-flex items-center gap-2 text-sm font-medium" href={paper.url} target="_blank" rel="noopener noreferrer">{pick("Read the original paper", "মূল গবেষণাপত্র পড়ুন")}<Icon name="external-link" size={15} /></a>
    </article>)}</div>}
  </AppShell>;
}
