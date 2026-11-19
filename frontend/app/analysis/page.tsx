"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api, ApiError, type AIProvider, type AIUsageStats, type AnalysisEvidence, type AnalysisField, type ExtractionFields, type Language, type LibraryPaper, type PaperAnalysis, type PaperComparison, type Preferences } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { LibraryDialog } from "../library/DocumentViewer";
import styles from "./workspace.module.css";

const labels: Record<AnalysisField, [string, string]> = {
  abstract_summary: ["Abstract summary", "সারসংক্ষেপ"], research_problem: ["Research problem", "গবেষণার সমস্যা"],
  research_objectives: ["Objectives", "উদ্দেশ্য"], methodology: ["Methodology", "পদ্ধতি"], datasets: ["Datasets", "ডেটাসেট"],
  models_and_algorithms: ["Models & algorithms", "মডেল ও অ্যালগরিদম"], evaluation_metrics: ["Evaluation metrics", "মূল্যায়নের সূচক"],
  key_results: ["Key results", "মূল ফলাফল"], contributions: ["Contributions", "অবদান"], limitations: ["Limitations", "সীমাবদ্ধতা"],
  future_work: ["Future work", "ভবিষ্যৎ কাজ"], strengths: ["Strengths", "সবল দিক"], weaknesses: ["Weaknesses", "দুর্বল দিক"],
};
const groups: AnalysisField[][] = [["abstract_summary"], ["research_problem", "research_objectives"], ["methodology"], ["datasets", "models_and_algorithms"], ["evaluation_metrics", "key_results"], ["contributions"], ["limitations", "future_work"], ["strengths", "weaknesses"]];
const compareFields: AnalysisField[] = ["methodology", "datasets", "models_and_algorithms", "evaluation_metrics", "key_results", "limitations"];

export default function AnalysisPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("Paper Intelligence", "গবেষণাপত্রের অন্তর্দৃষ্টি")} description={pick("Understand, compare and investigate with verifiable source evidence.", "যাচাইযোগ্য উৎসের প্রমাণ দিয়ে বুঝুন, তুলনা করুন ও অনুসন্ধান করুন।")} showHeading>{user && <Workspace key={user.id} />}</AppShell>;
}

function Workspace() {
  const { pick, language: uiLanguage, locale } = useI18n();
  const [tab, setTab] = useState<"single" | "compare">("single");
  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [single, setSingle] = useState("");
  const [language, setLanguage] = useState<Language>(uiLanguage);
  const [provider, setProvider] = useState<AIProvider>("auto");
  const [force, setForce] = useState(false);
  const [title, setTitle] = useState("");
  const [analysis, setAnalysis] = useState<PaperAnalysis | null>(null);
  const [comparison, setComparison] = useState<PaperComparison | null>(null);
  const [saved, setSaved] = useState<PaperAnalysis[]>([]);
  const [comparisons, setComparisons] = useState<PaperComparison[]>([]);
  const [savedOffset, setSavedOffset] = useState(0);
  const [compareOffset, setCompareOffset] = useState(0);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [usage, setUsage] = useState<AIUsageStats | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [source, setSource] = useState<{ link: AnalysisEvidence; text: string; error: boolean } | null>(null);
  const alive = useRef(true);
  const sourceTicket = useRef(0);
  const retry = useRef<{ fingerprint: string; id: string } | null>(null);

  useEffect(() => {
    alive.current = true;
    let current = true;
    Promise.all([api.getPaperAnalyses(), api.getPaperComparisons(), api.getPreferences(), api.getAIUsage()])
      .then(([analyses, history, preferences, stats]) => { if (current) { setSaved(analyses); setComparisons(history); setPrefs(preferences); setUsage(stats); } })
      .catch(() => { if (current) setError("Unable to load saved analyses / সংরক্ষিত বিশ্লেষণ লোড হয়নি।"); });
    const refresh = () => { api.getPreferences().then((value) => { if (current) setPrefs(value); }).catch(() => {}); };
    window.addEventListener("focus", refresh);
    return () => { current = false; alive.current = false; window.removeEventListener("focus", refresh); };
  }, []);

  useEffect(() => {
    let current = true;
    api.getLibrary({ q: query || undefined, page, size: 50 }).then((result) => { if (current) { setPapers(result.items); setPages(result.pages); } })
      .catch(() => { if (current) setError("Unable to load library / লাইব্রেরি লোড হয়নি।"); });
    return () => { current = false; };
  }, [query, page]);

  function fail(cause: unknown) {
    if (!alive.current) return;
    if (cause instanceof ApiError && cause.status === 409) retry.current = null;
    setError(cause instanceof ApiError && cause.status === 429 ? pick("AI fair-use limit reached. Wait and retry.", "এআই ব্যবহারের সীমা পূর্ণ হয়েছে। কিছুক্ষণ পর আবার চেষ্টা করুন।")
      : cause instanceof ApiError && cause.status === 403 ? pick("Cloud AI requires external AI consent in Settings.", "ক্লাউড এআই ব্যবহারের জন্য সেটিংসে বাহ্যিক এআই অনুমতি দিন।")
      : cause instanceof ApiError && cause.status === 409 ? pick("Every paper needs an indexed PDF. Sources may have changed; refresh and retry.", "প্রতিটি গবেষণাপত্রের ইনডেক্স করা পিডিএফ দরকার। উৎস বদলে যেতে পারে; রিফ্রেশ করে আবার চেষ্টা করুন।")
      : cause instanceof ApiError && cause.status === 404 ? pick("No saved result is available for this paper and language.", "এই গবেষণাপত্র ও ভাষায় কোনো সংরক্ষিত ফলাফল নেই।")
      : pick("Analysis could not be completed. Please retry.", "বিশ্লেষণ সম্পন্ন হয়নি। আবার চেষ্টা করুন।"));
  }

  async function action(work: () => Promise<void>) {
    setPending(true); setError("");
    try { await work(); } catch (cause) { fail(cause); }
    finally { if (alive.current) setPending(false); }
  }

  async function run() {
    const fingerprint = JSON.stringify([tab, single, selected, language, provider, force, title]);
    const request_id = retry.current?.fingerprint === fingerprint ? retry.current.id : crypto.randomUUID();
    retry.current = { fingerprint, id: request_id };
    await action(async () => {
      if (tab === "single") {
        const result = await api.analyzePaper(Number(single), { language, provider, force_refresh: force, request_id });
        if (alive.current) { setAnalysis(result); setSaved((old) => [result, ...old.filter((item) => item.id !== result.id)]); }
      } else {
        const result = await api.comparePapers({ user_paper_ids: selected, title: title.trim() || pick("Paper comparison", "গবেষণাপত্রের তুলনা"), language, provider, request_id });
        if (alive.current) { setComparison(result); setComparisons((old) => [result, ...old.filter((item) => item.id !== result.id)]); }
      }
      retry.current = null;
      const stats = await api.getAIUsage(); if (alive.current) setUsage(stats);
    });
  }

  async function openEvidence(link: AnalysisEvidence) {
    const ticket = ++sourceTicket.current;
    setSource({ link, text: "", error: false });
    try {
      const metadata = await api.getDocument(link.document_id);
      if (metadata.version !== link.document_version || metadata.status !== "completed") throw new Error("Stale source");
      const result = await api.getDocumentPages(link.document_id, link.page_number, 1);
      const text = result.items.find((p) => p.page_number === link.page_number)?.raw_text;
      if (!text || !text.includes(link.quoted_snippet)) throw new Error("Unavailable quote");
      if (alive.current && ticket === sourceTicket.current) setSource({ link, text, error: false });
    } catch { if (alive.current && ticket === sourceTicket.current) setSource({ link, text: "", error: true }); }
  }

  return <>
    {error && <p role="alert" className="notice error">{error}</p>}
    {!prefs?.allow_external_ai && <p className="notice">{pick("External AI consent is disabled. Local/offline analysis is available.", "বাহ্যিক এআই অনুমতি বন্ধ। স্থানীয়/অফলাইন বিশ্লেষণ করা যাবে।")} <Link href="/settings">{pick("Privacy settings", "গোপনীয়তা সেটিংস")}</Link></p>}
    {usage && <p className="muted text-sm">{pick("Remaining this hour", "এই ঘণ্টায় অবশিষ্ট")}: {usage.hourly.remaining_requests.toLocaleString(locale)} {pick("requests", "অনুরোধ")} · {usage.hourly.remaining_tokens.toLocaleString(locale)} {pick("tokens", "টোকেন")}</p>}
    <div className={styles.tabs} role="group" aria-label={pick("Analysis workspace", "বিশ্লেষণের কর্মক্ষেত্র")}>
      <button type="button" className={tab === "single" ? styles.active : ""} disabled={pending} aria-pressed={tab === "single"} onClick={() => setTab("single")}>{pick("Single paper analyzer", "একক গবেষণাপত্র বিশ্লেষণ")}</button>
      <button type="button" className={tab === "compare" ? styles.active : ""} disabled={pending} aria-pressed={tab === "compare"} onClick={() => setTab("compare")}>{pick("Comparison & gap explorer", "তুলনা ও গবেষণার সুযোগ")}</button>
    </div>
    <div className={styles.workspace}>
      <aside className={`card ${styles.controls}`}>
        <label>{pick("Find saved papers", "সংরক্ষিত গবেষণাপত্র খুঁজুন")}<input value={query} disabled={pending} onChange={(e) => { setQuery(e.target.value); setPage(1); }} /></label>
        <fieldset disabled={pending}><legend>{tab === "single" ? pick("Choose one indexed paper", "ইনডেক্স করা একটি গবেষণাপত্র বাছুন") : pick("Choose 2–5 indexed papers", "ইনডেক্স করা ২–৫টি গবেষণাপত্র বাছুন")}</legend>
          <div className={styles.paperList}>{papers.map((paper) => <label key={paper.id} className={styles.choice}>
            <input type={tab === "single" ? "radio" : "checkbox"} name="analysis-paper" disabled={paper.document?.status !== "completed" || (tab === "compare" && selected.length >= 5 && !selected.includes(paper.id))}
              checked={tab === "single" ? single === String(paper.id) : selected.includes(paper.id)} onChange={() => { if (tab === "single") { setSingle(String(paper.id)); setAnalysis(null); } else setSelected((old) => old.includes(paper.id) ? old.filter((id) => id !== paper.id) : [...old, paper.id]); }} />
            <span>{paper.title}<small>{paper.document?.status === "completed" ? pick("Indexed", "ইনডেক্স সম্পন্ন") : pick("PDF not indexed", "পিডিএফ ইনডেক্স হয়নি")}</small></span>
          </label>)}</div>
          <div className={styles.row}><button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>{pick("Previous", "আগের")}</button><span>{page} / {Math.max(1, pages)}</span><button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)}>{pick("Next", "পরের")}</button></div>
        </fieldset>
        {tab === "compare" && <><small>{selected.length} / 5 {pick("selected", "নির্বাচিত")}</small><label>{pick("Comparison title", "তুলনার শিরোনাম")}<input value={title} maxLength={200} disabled={pending} onChange={(e) => setTitle(e.target.value)} /></label></>}
        <label>{pick("Output language", "ফলাফলের ভাষা")}<select value={language} disabled={pending} onChange={(e) => { setLanguage(e.target.value as Language); setAnalysis(null); }}><option value="en">English</option><option value="bn">বাংলা</option></select></label>
        <label>{pick("Inference", "উত্তর তৈরির ব্যবস্থা")}<select value={provider} disabled={pending} onChange={(e) => setProvider(e.target.value as AIProvider)}><option value="auto">{pick("Default", "ডিফল্ট")}</option><option value="offline">{pick("Offline source excerpts", "অফলাইন উৎসের উদ্ধৃতি")}</option><option value="local">{pick("Local AI", "স্থানীয় এআই")}</option><option value="cloud" disabled={!prefs?.allow_external_ai}>{pick("Cloud AI (consent required)", "ক্লাউড এআই (অনুমতি প্রয়োজন)")}</option></select></label>
        {tab === "single" && <label className={styles.choice}><input type="checkbox" checked={force} disabled={pending} onChange={(e) => setForce(e.target.checked)} />{pick("Regenerate saved analysis", "সংরক্ষিত বিশ্লেষণ আবার তৈরি করুন")}</label>}
        <button type="button" className="button primary" disabled={pending || (tab === "single" ? !single : selected.length < 2)} onClick={run}>{pending ? pick("Analyzing…", "বিশ্লেষণ চলছে…") : tab === "single" ? pick("Analyze paper", "গবেষণাপত্র বিশ্লেষণ করুন") : pick("Compare papers", "গবেষণাপত্র তুলনা করুন")}</button>
        {tab === "single" && <button type="button" className="button secondary" disabled={pending || !single} onClick={() => action(async () => { const result = await api.getPaperAnalysis(Number(single), language); if (alive.current) setAnalysis(result); })}>{pick("View saved analysis", "সংরক্ষিত বিশ্লেষণ দেখুন")}</button>}
        <p className="muted text-xs">{pick("Offline mode quotes sources and preserves their original language. AI interpretation needs careful review.", "অফলাইন ব্যবস্থা উৎসের মূল ভাষায় উদ্ধৃতি দেখায়। এআই ব্যাখ্যা সতর্কভাবে যাচাই করুন।")}</p>
        <h2>{pick("Saved results", "সংরক্ষিত ফলাফল")}</h2>
        <ul className={styles.saved}>{(tab === "single" ? saved : comparisons).map((item) => <li key={item.id}><button type="button" disabled={pending} onClick={() => action(async () => {
          if ("user_paper_id" in item) { const value = await api.getPaperAnalysis(item.user_paper_id, item.language); if (alive.current) { setSingle(String(item.user_paper_id)); setLanguage(item.language); setAnalysis(value); } }
          else { const value = await api.getPaperComparison(item.id); if (alive.current) setComparison(value); }
        })}>{"user_paper_id" in item ? `${pick("Paper", "গবেষণাপত্র")} #${item.user_paper_id}` : item.title} · {item.language === "bn" ? "বাংলা" : "English"}{item.is_stale ? " · ↻" : ""}</button></li>)}</ul>
        {(tab === "single" ? saved.length : comparisons.length) >= 30 && <button type="button" disabled={pending} onClick={() => action(async () => {
          if (tab === "single") { const result = await api.getPaperAnalyses(30, savedOffset + 30); if (alive.current) { setSaved((old) => [...old, ...result.filter((item) => !old.some((a) => a.id === item.id))]); setSavedOffset(savedOffset + 30); } }
          else { const result = await api.getPaperComparisons(30, compareOffset + 30); if (alive.current) { setComparisons((old) => [...old, ...result.filter((item) => !old.some((a) => a.id === item.id))]); setCompareOffset(compareOffset + 30); } }
        })}>{pick("Load more", "আরও দেখুন")}</button>}
      </aside>
      <section className={styles.results} aria-label={pick("Analysis results", "বিশ্লেষণের ফলাফল")} aria-busy={pending} aria-live="polite">
        {tab === "single" && analysis ? <>
          <ResultHeading stale={analysis.is_stale} provider={analysis.provider_used} model={analysis.model_used} language={analysis.language} />
          {analysis.status === "failed" && <p role="alert" className="notice error">{pick("The last analysis failed. Regenerate to retry.", "সর্বশেষ বিশ্লেষণ ব্যর্থ হয়েছে। আবার তৈরি করে চেষ্টা করুন।")}</p>}
          <div className={styles.cards}>{groups.map((fields, i) => <article key={i} className="card">{fields.map((field) => <Field key={field} name={field} result={analysis} stale={analysis.is_stale} open={openEvidence} />)}</article>)}</div>
        </> : tab === "compare" && comparison ? <>
          <ResultHeading stale={comparison.is_stale} provider={comparison.provider_used} model={comparison.model_used} language={comparison.language} />
          <section className="card"><h2>{comparison.title}</h2><div className={styles.tableWrap}><table className={styles.matrix}><caption>{pick("Comparison of selected papers", "নির্বাচিত গবেষণাপত্রগুলোর তুলনা")}</caption><thead><tr><th scope="col">{pick("Dimension", "বিষয়")}</th>{comparison.comparison_matrix.map((column) => <th scope="col" key={column.user_paper_id}>{column.paper_title}</th>)}</tr></thead><tbody>{compareFields.map((field) => <tr key={field}><th scope="row">{pick(...labels[field])}</th>{comparison.comparison_matrix.map((column) => <td key={column.user_paper_id}><Field name={field} result={column} stale={comparison.is_stale} open={openEvidence} compact /></td>)}</tr>)}</tbody></table></div></section>
          <section className="card"><h2>{pick("Literature synthesis", "সাহিত্য সংশ্লেষণ")}</h2><p className="tag">{pick("AI interpretation · Selected sources only", "এআই ব্যাখ্যা · শুধু নির্বাচিত উৎস")}</p><p className={styles.pre}>{comparison.literature_synthesis}</p><Evidence links={comparison.evidence_links.filter((link) => link.field === "literature_synthesis")} stale={comparison.is_stale} open={openEvidence} /></section>
          <section className="card"><h2>{pick("Research gap explorer", "গবেষণার সুযোগ অনুসন্ধান")}</h2><p className="muted text-sm">{pick("These are hypotheses grounded in limitations reported by your selected papers. They do not establish gaps across all research.", "এগুলো নির্বাচিত গবেষণাপত্রে উল্লিখিত সীমাবদ্ধতা থেকে পাওয়া অনুমান। সমগ্র গবেষণা সাহিত্যে ঘাটতি আছে—এমন সিদ্ধান্ত নয়।")}</p>
            {comparison.research_gaps.length === 0 ? <p>{pick("Insufficient evidence to identify a research gap in these papers.", "এই গবেষণাপত্রগুলো থেকে গবেষণার ঘাটতি শনাক্ত করার পর্যাপ্ত প্রমাণ নেই।")}</p> : comparison.research_gaps.map((gap, i) => <article key={i} className={styles.gap}><h3>{gap.title}</h3><span className="tag">{pick("AI interpretation", "এআই ব্যাখ্যা")}</span><p className={styles.pre}>{gap.description}</p><Evidence links={gap.evidence_links} stale={comparison.is_stale} open={openEvidence} /></article>)}
          </section>
        </> : <section className="card empty-state"><h2>{pick("Begin with indexed sources", "ইনডেক্স করা উৎস দিয়ে শুরু করুন")}</h2><p>{pick("Choose a paper for structured extraction, or compare 2–5 papers with source-backed research gaps.", "সাজানো বিশ্লেষণের জন্য একটি গবেষণাপত্র বাছুন, অথবা উৎসভিত্তিক গবেষণার সুযোগ খুঁজতে ২–৫টি গবেষণাপত্র তুলনা করুন।")}</p><Link href="/library" className="button secondary">{pick("Open library", "লাইব্রেরি খুলুন")}</Link></section>}
      </section>
    </div>
    {source && <LibraryDialog title={`${source.link.paper_title} · ${pick("Page", "পৃষ্ঠা")} ${source.link.page_number}`} onClose={() => { ++sourceTicket.current; setSource(null); }} wide><blockquote>{source.link.quoted_snippet}</blockquote>{source.error ? <p role="alert">{pick("This exact source version is unavailable. Regenerate the analysis.", "উৎসের এই সংস্করণটি পাওয়া যাচ্ছে না। বিশ্লেষণ আবার তৈরি করুন।")}</p> : <p className={styles.pre}>{source.text || pick("Loading source…", "উৎস লোড হচ্ছে…")}</p>}</LibraryDialog>}
  </>;
}

function ResultHeading({ stale, provider, model, language }: { stale: boolean; provider: string; model: string; language: Language }) {
  const { pick } = useI18n();
  return <div className="card"><p className="muted text-xs">{provider} · {model} · {language === "bn" ? "বাংলা" : "English"}</p>{stale && <p role="status" className="notice">{pick("Sources changed or were removed. Regenerate before relying on this saved result.", "উৎস বদলেছে বা মুছে ফেলা হয়েছে। এই ফলাফলের ওপর নির্ভর করার আগে আবার তৈরি করুন।")}</p>}</div>;
}

function Field({ name, result, open, stale, compact = false }: { name: AnalysisField; result: ExtractionFields; open: (link: AnalysisEvidence) => void; stale: boolean; compact?: boolean }) {
  const { pick } = useI18n();
  const value = result[name];
  const items = Array.isArray(value) ? value : [value];
  return <section className={styles.field}>{!compact && <h3>{pick(...labels[name])}</h3>}
    <span className="tag">{result.field_statuses[name] === "supported" ? pick("Source evidence", "উৎসের প্রমাণ") : result.field_statuses[name] === "partial_interpretation" ? pick("AI interpretation", "এআই ব্যাখ্যা") : pick("Not specified in document", "নথিতে উল্লেখ নেই")}</span>
    {items.map((item, i) => <p key={i} className={styles.pre}>{item === "Not specified in document" ? pick(item, "নথিতে উল্লেখ নেই") : item}</p>)}
    <Evidence links={result.evidence_links.filter((link) => link.field === name)} stale={stale} open={open} />
  </section>;
}

function Evidence({ links, stale, open }: { links: AnalysisEvidence[]; stale: boolean; open: (link: AnalysisEvidence) => void }) {
  const { pick } = useI18n();
  return <div className={styles.evidence}>{links.map((link, i) => <details key={i}><summary>{link.paper_title} · {pick("p.", "পৃষ্ঠা")} {link.page_number}</summary>{link.section_heading && <small>{link.section_heading}</small>}<blockquote>{link.quoted_snippet}</blockquote><button type="button" disabled={stale} onClick={() => open(link)}>{pick("Open verified page", "যাচাই করা পৃষ্ঠা খুলুন")}</button></details>)}</div>;
}
