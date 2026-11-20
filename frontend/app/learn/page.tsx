"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { api, type GlossaryResult, type LearningGuide, type LearningProgress } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { completedLearningSteps, learningModulePath, safePublicLink } from "@/lib/learning-teams";
import { BeginnerExplainer } from "./BeginnerExplainer";
import styles from "@/components/ModuleWorkspace.module.css";

export default function LearnPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("Learn Research", "গবেষণা শিখুন")} description={pick("Build a research practice, one guided step at a time.", "নির্দেশিত ধাপে ধাপে গবেষণার চর্চা গড়ে তুলুন।")} showHeading>{user && <LearningCenter key={user.id} />}</AppShell>;
}

function LearningCenter() {
  const { pick, language, locale } = useI18n();
  const [guides, setGuides] = useState<LearningGuide[]>([]);
  const [tab, setTab] = useState<"guides" | "glossary">("guides");
  const [selected, setSelected] = useState<string | null>(null);
  const [explainer, setExplainer] = useState(false);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.getLearningGuides(controller.signal).then((rows) => {
      if (!controller.signal.aborted) { setGuides(rows); setLoaded(true); setError(""); }
    }).catch(() => { if (!controller.signal.aborted) setError("Unable to load learning guides / শেখার নির্দেশিকা লোড হয়নি।"); });
    return () => controller.abort();
  }, [revision]);
  function updateProgress(slug: string, progress: LearningProgress) {
    setGuides((items) => items.map((item) => item.slug === slug ? { ...item, progress } : item));
  }
  return <>
    <div className={styles.toolbar}>
      <button className="button primary" onClick={() => setExplainer(true)}>{pick("Explain my paper for beginners", "নতুনদের জন্য আমার গবেষণাপত্র বুঝিয়ে দিন")}</button>
      <button className="button secondary" onClick={() => setRevision((v) => v + 1)}>{pick("Refresh progress", "অগ্রগতি রিফ্রেশ")}</button>
      <span className={styles.small}>{guides.filter((guide) => guide.progress.is_completed).length.toLocaleString(locale)} / {guides.length.toLocaleString(locale)} {pick("guides completed", "নির্দেশিকা সম্পন্ন")}</span>
    </div>
    <div className={styles.tabs} role="group" aria-label={pick("Learning resources", "শেখার বিষয়বস্তু")}>
      <button aria-pressed={tab === "guides"} onClick={() => setTab("guides")}>{pick("Guides & workflows", "নির্দেশিকা ও কর্মধারা")}</button>
      <button aria-pressed={tab === "glossary"} onClick={() => setTab("glossary")}>{pick("Academic glossary", "একাডেমিক শব্দকোষ")}</button>
    </div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {tab === "guides" && <>
      {!loaded && !error && <p className="loading-state" role="status">{pick("Loading learning resources…", "শেখার বিষয়বস্তু লোড হচ্ছে…")}</p>}
      {selected ? <GuideDetail key={`${selected}:${revision}`} slug={selected} onBack={() => setSelected(null)} onProgress={updateProgress} /> : <div className={styles.cards}>
        {guides.map((guide) => <article key={guide.slug} className={`card ${styles.card}`}>
          <span className="tag">{pick(`${guide.estimated_minutes} minute guide`, `${guide.estimated_minutes.toLocaleString(locale)} মিনিটের নির্দেশিকা`)}</span>
          <h2>{guide.title[language]}</h2><p>{guide.summary[language]}</p>
          <label className={styles.small}>{pick("Your progress", "আপনার অগ্রগতি")}: {guide.progress.percent.toLocaleString(locale)}%<progress className={styles.progress} max={100} value={guide.progress.percent} /></label>
          <div className={styles.actions}><button className="button secondary" onClick={() => setSelected(guide.slug)}>{guide.progress.is_completed ? pick("Review guide", "আবার দেখুন") : pick("Open guide", "নির্দেশিকা খুলুন")}</button></div>
        </article>)}
      </div>}
    </>}
    {tab === "glossary" && <Glossary />}
    {explainer && <BeginnerExplainer onClose={() => setExplainer(false)} />}
  </>;
}

function GuideDetail({ slug, onBack, onProgress }: { slug: string; onBack: () => void; onProgress: (slug: string, progress: LearningProgress) => void }) {
  const { pick, language, locale } = useI18n();
  const [guide, setGuide] = useState<LearningGuide | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const active = new AbortController(); controller.current = active;
    api.getLearningGuide(slug, active.signal).then((row) => { if (!active.signal.aborted) setGuide(row); })
      .catch(() => { if (!active.signal.aborted) setError("Unable to open this guide / নির্দেশিকাটি খোলা যায়নি।"); });
    return () => active.abort();
  }, [slug]);
  async function complete(id: string, checked: boolean) {
    if (!guide || pending) return;
    const signal = controller.current?.signal;
    setPending(true); setError("");
    try {
      const progress = await api.updateLearningProgress(slug, completedLearningSteps(guide, guide.progress.completed_step_ids, id, checked), signal);
      if (!signal?.aborted) { setGuide((item) => item ? { ...item, progress } : item); onProgress(slug, progress); }
    } catch { if (!signal?.aborted) setError(pick("Progress was not saved. Please retry.", "অগ্রগতি সংরক্ষণ হয়নি। আবার চেষ্টা করুন।")); }
    finally { if (!signal?.aborted) setPending(false); }
  }
  return <>
    <div className={styles.toolbar}><button className="button secondary" onClick={onBack}>{pick("← All guides", "← সব নির্দেশিকা")}</button></div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {!guide ? !error && <p role="status">{pick("Opening guide…", "নির্দেশিকা খুলছে…")}</p> : <section className={`card ${styles.section}`} aria-busy={pending}>
      <h2>{guide.title[language]}</h2><p className={styles.prose}>{guide.summary[language]}</p>
      <label className={styles.small}>{guide.progress.percent.toLocaleString(locale)}% {pick("completed", "সম্পন্ন")}<progress className={styles.progress} value={guide.progress.percent} max={100} /></label>
      <ol className={styles.list}>{guide.steps.map((step, index) => <li key={step.id}>
        <label className={styles.checkbox}><input type="checkbox" disabled={pending} checked={guide.progress.completed_step_ids.includes(step.id)} onChange={(e) => { void complete(step.id, e.target.checked); }} /><strong>{(index + 1).toLocaleString(locale)}. {step.title[language]}</strong></label>
        <p>{step.description[language]}</p><ul className={styles.checklist}>{step.checklist.map((item, i) => <li key={i}>{item[language]}</li>)}</ul>
        {learningModulePath(step.module_path) && <Link className="button ghost small" href={step.module_path}>{pick("Practice in ResearchNest →", "রিসার্চনেস্টে অনুশীলন করুন →")}</Link>}
      </li>)}</ol>
      <div><h3>{pick("Further reading & sources", "আরও পড়ুন ও উৎস")}</h3><ul>{guide.sources.map((source) => <li key={source.url}>{safePublicLink(source.url) ? <a href={safePublicLink(source.url)!} target="_blank" rel="noopener noreferrer nofollow">{source.title}</a> : source.title}</li>)}</ul></div>
    </section>}
  </>;
}

function Glossary() {
  const { pick, language } = useI18n();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [result, setResult] = useState<GlossaryResult | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api.getGlossary(query, category, controller.signal).then((rows) => { if (!controller.signal.aborted) { setResult(rows); setError(""); } })
        .catch(() => { if (!controller.signal.aborted) setError("Unable to search glossary / শব্দকোষে খোঁজা যায়নি।"); });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, category]);
  return <>
    <div className={styles.toolbar}>
      <label className={`field ${styles.search}`}>{pick("Search in English or Bangla", "ইংরেজি বা বাংলায় খুঁজুন")}<input type="search" value={query} maxLength={120} onChange={(e) => setQuery(e.target.value)} /></label>
      <label className="field">{pick("Category", "বিভাগ")}<select value={category} onChange={(e) => setCategory(e.target.value)}><option value="">{pick("All categories", "সব বিভাগ")}</option>{result?.categories.map((item) => <option key={item} value={item}>{categoryLabel(item, language)}</option>)}</select></label>
    </div>
    {error && <p className="notice error" role="alert">{error}</p>}
    {!result && !error && <p role="status">{pick("Loading glossary…", "শব্দকোষ লোড হচ্ছে…")}</p>}
    <div className={styles.cards}>{result?.items.map((entry) => <article key={entry.slug} className={`card ${styles.card}`}>
      <span className="tag">{categoryLabel(entry.category, language)}</span><h2>{entry.term[language]}</h2><p lang={language === "bn" ? "en" : "bn"}>{entry.term[language === "bn" ? "en" : "bn"]}</p>
      <p>{entry.definition[language]}</p><p><strong>{pick("Academic usage", "একাডেমিক ব্যবহার")}: </strong>{entry.example[language]}</p>
    </article>)}</div>
    {result && !result.items.length && <p className="empty-state">{pick("No matching terms. Try another word or category.", "মিলযুক্ত শব্দ নেই। অন্য শব্দ বা বিভাগ বাছুন।")}</p>}
  </>;
}

function categoryLabel(category: string, language: "en" | "bn") {
  const names: Record<string, [string, string]> = { methodology: ["Methodology", "গবেষণা পদ্ধতি"], methods: ["Research methods", "গবেষণা পদ্ধতি"], integrity: ["Research integrity", "গবেষণার সততা"], reading: ["Reading papers", "গবেষণাপত্র পড়া"], planning: ["Research planning", "গবেষণা পরিকল্পনা"], synthesis: ["Literature synthesis", "সাহিত্য সমন্বয়"], statistics: ["Statistics", "পরিসংখ্যান"], publishing: ["Publishing", "প্রকাশনা"], writing: ["Academic writing", "একাডেমিক লেখা"], ethics: ["Research ethics", "গবেষণার নীতি"], discovery: ["Discovery", "অনুসন্ধান"], research: ["Research practice", "গবেষণার চর্চা"] };
  return names[category]?.[language === "bn" ? 1 : 0] || category;
}
