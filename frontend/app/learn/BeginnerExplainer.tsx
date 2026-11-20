"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, type AIProvider, type AIUsageStats, type BeginnerExplanation, type Language, type LibraryPaper, type Preferences } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { readVerifiedEducationPage } from "@/lib/learning-teams";
import { LibraryDialog } from "../library/DocumentViewer";
import styles from "@/components/ModuleWorkspace.module.css";

export function BeginnerExplainer({ onClose }: { onClose: () => void }) {
  const { pick, language: uiLanguage, locale } = useI18n();
  const [language, setLanguage] = useState<Language>(uiLanguage);
  const [provider, setProvider] = useState<AIProvider>("auto");
  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [usage, setUsage] = useState<AIUsageStats | null>(null);
  const [result, setResult] = useState<BeginnerExplanation | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [libraryError, setLibraryError] = useState("");
  const [source, setSource] = useState<string | null>(null);
  const [sourceError, setSourceError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const retry = useRef<{ key: string; request_id: string } | null>(null);
  const sourceTicket = useRef(0);
  useEffect(() => {
    const active = new AbortController(); controller.current = active;
    api.getPreferences(active.signal).then((value) => { if (!active.signal.aborted) setPreferences(value); }).catch(() => {});
    api.getAIUsage(active.signal).then((value) => { if (!active.signal.aborted) setUsage(value); }).catch(() => {});
    return () => active.abort();
  }, []);
  useEffect(() => {
    const active = new AbortController();
    api.getLibrary({ q: query || undefined, page, size: 20 }, active.signal).then((value) => {
      if (!active.signal.aborted) { setPapers(value.items); setPages(value.pages); setLibraryError(""); }
    }).catch(() => { if (!active.signal.aborted) setLibraryError("Unable to load your library / আপনার লাইব্রেরি লোড হয়নি।"); });
    return () => active.abort();
  }, [page, query]);
  async function explain() {
    if (!selected || pending) return;
    const key = JSON.stringify([selected, language, provider]);
    if (retry.current?.key !== key) retry.current = { key, request_id: crypto.randomUUID() };
    const signal = controller.current?.signal;
    sourceTicket.current += 1;
    setPending(true); setError(""); setResult(null); setSource(null); setSourceError("");
    try {
      const response = await api.explainPaperForBeginners(selected, { language, provider, request_id: retry.current.request_id }, signal);
      if (!signal?.aborted) { setResult(response); retry.current = null; }
    } catch (cause) {
      if (!signal?.aborted) {
        if (cause instanceof ApiError && cause.status === 409) retry.current = null;
        setError(cause instanceof ApiError && cause.status === 429 ? pick("Your AI quota is reached. Wait before trying again.", "এআই ব্যবহারের সীমা পূর্ণ হয়েছে। পরে আবার চেষ্টা করুন।")
          : cause instanceof ApiError && cause.status === 403 ? pick("External AI needs consent in Settings. You can choose local or offline mode.", "বাহ্যিক এআইয়ের জন্য সেটিংসে অনুমতি দিন। স্থানীয় বা অফলাইন ব্যবস্থা বেছে নিতে পারেন।")
          : cause instanceof ApiError && cause.status === 409 ? pick("The paper or request state changed. Check its PDF index, refresh, and retry with a new request.", "গবেষণাপত্র বা অনুরোধের অবস্থা বদলেছে। পিডিএফের ইনডেক্স দেখে রিফ্রেশ করুন এবং নতুন অনুরোধে আবার চেষ্টা করুন।")
          : pick("The explanation is unavailable. Check that the paper remains in your library and retry.", "ব্যাখ্যাটি পাওয়া যায়নি। গবেষণাপত্রটি লাইব্রেরিতে আছে কি না দেখে আবার চেষ্টা করুন।"));
      }
    } finally {
      if (!signal?.aborted) { setPending(false); api.getAIUsage(signal).then((value) => { if (!signal?.aborted) setUsage(value); }).catch(() => {}); }
    }
  }
  async function inspect(evidence: BeginnerExplanation["supported_evidence"][number]) {
    const signal = controller.current?.signal;
    const ticket = ++sourceTicket.current;
    setSource(null); setSourceError("");
    try {
      const text = await readVerifiedEducationPage(api, evidence, signal);
      if (!signal?.aborted && ticket === sourceTicket.current) setSource(text);
    } catch { if (!signal?.aborted && ticket === sourceTicket.current) setSourceError(pick("This evidence is no longer current. Re-index and request a new explanation.", "এই প্রমাণ আর বর্তমান নয়। আবার ইনডেক্স করে নতুন ব্যাখ্যা চান।")); }
  }
  return <LibraryDialog title={pick("Paper explainer for beginners", "নতুনদের জন্য গবেষণাপত্রের ব্যাখ্যা")} onClose={onClose} wide>
    <p className={styles.small}>{pick("Choose an indexed paper from your own library. Explanations keep quoted source facts separate from reading guidance and AI interpretation.", "নিজের লাইব্রেরির ইনডেক্স করা গবেষণাপত্র বাছুন। উৎসের তথ্যের উদ্ধৃতি, পড়ার নির্দেশনা ও এআই ব্যাখ্যা আলাদা থাকে।")}</p>
    <div className={styles.grid}>
      <section className={styles.form}>
        <label className="field">{pick("Find my paper", "আমার গবেষণাপত্র খুঁজুন")}<input maxLength={120} disabled={pending} value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); setSelected(null); setResult(null); }} /></label>
        {libraryError && <p className="notice error" role="alert">{libraryError}</p>}
        <fieldset disabled={pending}><legend>{pick("Indexed library papers", "লাইব্রেরির ইনডেক্স করা গবেষণাপত্র")}</legend>{papers.map((paper) => <label className={styles.choice} key={paper.id}><input type="radio" name="beginner-paper" checked={selected === paper.id} disabled={paper.document?.status !== "completed"} onChange={() => { setSelected(paper.id); setResult(null); }} /><span>{paper.title}<small>{paper.document?.status === "completed" ? pick("Indexed", "ইনডেক্স সম্পন্ন") : pick("Index a PDF first", "আগে পিডিএফ ইনডেক্স করুন")}</small></span></label>)}
          <div className={styles.pagination}><button type="button" disabled={page <= 1} onClick={() => { setPage((v) => v - 1); setSelected(null); }}>{pick("Previous", "আগের")}</button><span>{page.toLocaleString(locale)} / {Math.max(1, pages).toLocaleString(locale)}</span><button type="button" disabled={page >= pages} onClick={() => { setPage((v) => v + 1); setSelected(null); }}>{pick("Next", "পরের")}</button></div>
        </fieldset>
        <label className="field">{pick("Explanation language", "ব্যাখ্যার ভাষা")}<select value={language} disabled={pending} onChange={(e) => { setLanguage(e.target.value as Language); setResult(null); }}><option value="en">English</option><option value="bn">বাংলা</option></select></label>
        <label className="field">{pick("AI provider", "এআই ব্যবস্থা")}<select value={provider} disabled={pending} onChange={(e) => { setProvider(e.target.value as AIProvider); setResult(null); }}><option value="auto">{pick("Default", "ডিফল্ট")}</option><option value="offline">{pick("Offline reading guide", "অফলাইন পড়ার নির্দেশনা")}</option><option value="local">{pick("Local AI", "স্থানীয় এআই")}</option><option value="cloud" disabled={!preferences?.allow_external_ai}>{pick("Cloud AI (consent required)", "ক্লাউড এআই (অনুমতি দরকার)")}</option></select></label>
        {!preferences?.allow_external_ai && <p className={styles.small}>{pick("External AI consent is disabled or unavailable. Local and offline options remain available.", "বাহ্যিক এআই অনুমতি বন্ধ বা পাওয়া যায়নি। স্থানীয় ও অফলাইন ব্যবস্থা আছে।")} <Link href="/settings">{pick("Privacy settings", "গোপনীয়তা সেটিংস")}</Link></p>}
        {usage && <p className={styles.small}>{pick("Remaining this hour", "এই ঘণ্টায় অবশিষ্ট")}: {usage.hourly.remaining_requests.toLocaleString(locale)} {pick("requests", "অনুরোধ")} · {usage.hourly.remaining_tokens.toLocaleString(locale)} {pick("tokens", "টোকেন")}</p>}
        <button className="button primary" disabled={pending || !selected} onClick={() => { void explain(); }}>{pending ? pick("Preparing explanation…", "ব্যাখ্যা প্রস্তুত হচ্ছে…") : pick("Explain selected paper", "বাছাই করা গবেষণাপত্র বুঝিয়ে দিন")}</button>
      </section>
      <section aria-live="polite" aria-busy={pending}>
        {error && <p className="notice error" role="alert">{error}</p>}
        {!result && !pending && <p className="empty-state">{pick("Your beginner guide and source quotes will appear here.", "নতুনদের নির্দেশনা ও উৎসের উদ্ধৃতি এখানে দেখা যাবে।")}</p>}
        {result && <><h2>{result.title}</h2><p className={styles.small}>{result.provider_used} · {result.model_used} · {result.language === "bn" ? "বাংলা" : "English"}</p>
          {result.mode_notice && <p className="notice">{result.mode_notice}</p>}
          <h3>{pick("Beginner reading guide", "নতুনদের পড়ার নির্দেশনা")}</h3><p className={styles.prose}>{result.beginner_explanation}</p>
          {result.plain_language_interpretation?.map((item) => <div className={styles.notice} key={item.focus}><h3>{focusLabel(item.focus, pick)}</h3><span className="tag">{pick("AI interpretation — review against sources", "এআই ব্যাখ্যা — উৎসের সঙ্গে যাচাই করুন")}</span><p className={styles.prose}>{item.explanation}</p>{item.evidence.map((evidence) => <blockquote className={styles.quote} key={`${evidence.chunk_id}:${evidence.quoted_snippet}`}>{evidence.quoted_snippet}<footer className={styles.small}>{evidence.paper_title} · {pick("page", "পৃষ্ঠা")} {evidence.page_number.toLocaleString(locale)}</footer></blockquote>)}</div>)}
          {!!result.term_explanations?.length && <><h3>{pick("Helpful research vocabulary", "সহায়ক গবেষণার শব্দ")}</h3><dl>{result.term_explanations.map((term) => <div key={term.term}><dt><strong>{term.term}</strong></dt><dd className={styles.prose}>{term.definition}</dd></div>)}</dl></>}
          <p className="notice">{pick("AI wording needs review. Original source quotes retain their original language; they are not automatically translated facts.", "এআইয়ের ভাষা যাচাই করুন। উৎসের উদ্ধৃতি মূল ভাষায় থাকে; এগুলো স্বয়ংক্রিয়ভাবে অনূদিত তথ্য নয়।")}</p>
          <h3>{pick("Quoted source evidence", "উৎসের প্রমাণের উদ্ধৃতি")}</h3>{result.supported_evidence.map((item) => <div key={`${item.chunk_id}:${item.quoted_snippet}`}><p className={styles.source}>{item.paper_title} · {pick("page", "পৃষ্ঠা")} {item.page_number.toLocaleString(locale)}</p><blockquote className={styles.quote}>{item.quoted_snippet}</blockquote><button className="button ghost small" onClick={() => { void inspect(item); }}>{pick("Verify current source page", "উৎসের বর্তমান পৃষ্ঠা যাচাই")}</button></div>)}
          {result.missing_information && <><h3>{pick("Missing information", "অনুপস্থিত তথ্য")}</h3><p className={styles.prose}>{result.missing_information}</p></>}
          {!!result.follow_up_questions.length && <><h3>{pick("Questions to explore", "আরও যে প্রশ্ন ভাবতে পারেন")}</h3><ul className={styles.checklist}>{result.follow_up_questions.map((question, i) => <li key={i}>{question}</li>)}</ul></>}
          {sourceError && <p className="notice error" role="alert">{sourceError}</p>}{source && <div className={styles.notice}><h3>{pick("Verified current page text", "যাচাই করা বর্তমান পৃষ্ঠার পাঠ্য")}</h3><p className={styles.prose}>{source}</p></div>}
        </>}
      </section>
    </div>
  </LibraryDialog>;
}

function focusLabel(focus: string, pick: (en: string, bn: string) => string) {
  const names: Record<string, [string, string]> = { question: ["Research question", "গবেষণার প্রশ্ন"], method: ["How the study works", "গবেষণাটি যেভাবে করা হয়েছে"], findings: ["What the findings mean", "ফলাফলের অর্থ"], limitations: ["Limits to keep in mind", "যে সীমাবদ্ধতা মনে রাখতে হবে"] };
  return pick(...(names[focus] || [focus, focus]));
}
