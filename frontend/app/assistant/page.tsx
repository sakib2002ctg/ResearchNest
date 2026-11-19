"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { AppShell } from "@/components/AppShell";
import { api, ApiError, type AIProvider, type AIUsageStats, type Conversation, type ConversationHistory, type ConversationInput, type LibraryCollection, type LibraryPaper, type Preferences, type SourceCitation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { LibraryDialog } from "../library/DocumentViewer";
import styles from "./workspace.module.css";

export default function AssistantPage() {
  const { user } = useAuth();
  const { pick } = useI18n();
  return <AppShell title={pick("AI Research Assistant", "এআই গবেষণা সহকারী")} description={pick("Ask questions grounded in your private papers.", "আপনার ব্যক্তিগত গবেষণাপত্রের প্রমাণভিত্তিক প্রশ্ন করুন।")} showHeading>
    {user && <Workspace key={user.id} />}
  </AppShell>;
}

function Workspace() {
  const { pick, language, locale } = useI18n();
  const [chats, setChats] = useState<Conversation[]>([]);
  const [chat, setChat] = useState<ConversationHistory | null>(null);
  const [papers, setPapers] = useState<LibraryPaper[]>([]);
  const [paperPage, setPaperPage] = useState(1);
  const [paperPages, setPaperPages] = useState(1);
  const [query, setQuery] = useState("");
  const [collections, setCollections] = useState<LibraryCollection[]>([]);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [usage, setUsage] = useState<AIUsageStats | null>(null);
  const [scope, setScope] = useState<ConversationInput["scope_type"]>("single_paper");
  const [selected, setSelected] = useState<number[]>([]);
  const [collection, setCollection] = useState("");
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState<AIProvider>("auto");
  const [pending, setPending] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [source, setSource] = useState<{ citation: SourceCitation; text: string; error: boolean } | null>(null);
  const [offset, setOffset] = useState(0);
  const alive = useRef(true);
  const sourceTicket = useRef(0);
  const retry = useRef<{ fingerprint: string; id: string } | null>(null);

  function fail(cause: unknown) {
    if (!alive.current) return;
    setError(cause instanceof ApiError && cause.status === 429
      ? pick("AI usage limit reached. Wait and retry.", "এআই ব্যবহারের সীমা পূর্ণ হয়েছে। কিছুক্ষণ পর চেষ্টা করুন।")
      : cause instanceof ApiError && cause.status === 403
        ? pick("Cloud AI requires external AI consent in Settings.", "ক্লাউড এআই ব্যবহারের জন্য সেটিংসে বাহ্যিক এআই অনুমতি দিন।")
        : pick("The request failed. Please try again.", "অনুরোধ ব্যর্থ হয়েছে। আবার চেষ্টা করুন।"));
  }

  useEffect(() => {
    alive.current = true;
    let current = true;
    const requested = new URLSearchParams(window.location.search).get("conversation_id");
    const linkedHistory = requested && /^[1-9]\d*$/.test(requested)
      ? api.getConversation(Number(requested)).catch(() => { if (current) setError("Unable to open conversation / আলোচনা খোলা যায়নি।"); return null; })
      : Promise.resolve(null);
    Promise.all([api.getConversations(), api.getLibraryCollections(), api.getPreferences(), api.getAIUsage(), linkedHistory])
      .then(([conversations, folders, preferences, stats, history]) => {
        if (current) { setChats(conversations); setCollections(folders); setPrefs(preferences); setUsage(stats); setChat(history); setReady(true); }
      }).catch(() => { if (current) setError("Unable to load / লোড হয়নি।"); });
    const refresh = () => { api.getPreferences().then((preferences) => { if (current) setPrefs(preferences); }).catch(() => {}); };
    window.addEventListener("focus", refresh);
    return () => { current = false; alive.current = false; window.removeEventListener("focus", refresh); };
  }, []);

  useEffect(() => {
    let current = true;
    api.getLibrary({ q: query || undefined, page: paperPage, size: 50 }).then((result) => {
      if (current) { setPapers(result.items); setPaperPages(result.pages); }
    }).catch(() => { if (current) setError("Unable to load papers / গবেষণাপত্র লোড হয়নি।"); });
    return () => { current = false; };
  }, [query, paperPage]);

  async function action(work: () => Promise<void>) {
    setPending(true); setError("");
    try { await work(); } catch (cause) { fail(cause); }
    finally { if (alive.current) setPending(false); }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await action(async () => {
      const result = await api.createConversation({ title: title.trim() || pick("Research conversation", "গবেষণা আলোচনা"), scope_type: scope,
        scope_paper_ids: scope === "collection" ? [] : selected, scope_collection_id: scope === "collection" ? Number(collection) : null, language });
      if (alive.current) { setChats((items) => [result, ...items]); setChat({ ...result, messages: [] }); setQuestion(""); retry.current = null; }
    });
  }

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!chat || !question.trim()) return;
    const id = chat.id;
    const fingerprint = JSON.stringify([id, question.trim(), provider]);
    const request_id = retry.current?.fingerprint === fingerprint ? retry.current.id : crypto.randomUUID();
    retry.current = { fingerprint, id: request_id };
    await action(async () => {
      try {
        await api.sendAssistantMessage(id, { content: question.trim(), provider, request_id });
      } catch (cause) {
        if (cause instanceof ApiError && cause.status === 409) retry.current = null;
        throw cause;
      }
      const [result, stats] = await Promise.all([api.getConversation(id), api.getAIUsage()]);
      if (alive.current) { setChat(result); setUsage(stats); setQuestion(""); retry.current = null; }
    });
  }

  async function openSource(citation: SourceCitation) {
    const ticket = ++sourceTicket.current;
    setSource({ citation, text: "", error: false });
    if (!citation.document_id || !citation.chunk_id) { setSource({ citation, text: "", error: true }); return; }
    try {
      const result = await api.getDocumentPages(citation.document_id, citation.page_number, 1);
      const page = result.items.find((item) => item.page_number === citation.page_number);
      if (alive.current && ticket === sourceTicket.current) setSource({ citation, text: page?.raw_text || "", error: !page });
    } catch { if (alive.current && ticket === sourceTicket.current) setSource({ citation, text: "", error: true }); }
  }

  return <>
    {error && <p role="alert" className="notice error">{error}</p>}
    {!prefs?.allow_external_ai && <p className="notice">{pick("External AI is disabled. Local and offline modes keep your papers private.", "বাহ্যিক এআই বন্ধ। স্থানীয় ও অফলাইন ব্যবস্থা আপনার নথি ব্যক্তিগত রাখে।")} <Link href="/settings">{pick("Privacy settings", "গোপনীয়তা সেটিংস")}</Link></p>}
    {usage && <p className={styles.quota} aria-live="polite">{pick("Remaining this hour", "এই ঘণ্টায় অবশিষ্ট")}: {usage.hourly.remaining_requests.toLocaleString(locale)} {pick("requests", "অনুরোধ")} · {usage.hourly.remaining_tokens.toLocaleString(locale)} {pick("tokens", "টোকেন")} — {pick("Daily requests", "দৈনিক অনুরোধ")}: {usage.daily.remaining_requests.toLocaleString(locale)} / {usage.daily.request_limit.toLocaleString(locale)}</p>}
    <div className={styles.workspace}>
      <aside className={`card ${styles.sidebar}`}>
        <h2>{pick("New conversation", "নতুন আলোচনা")}</h2>
        <form onSubmit={create} className={styles.form}>
          <label>{pick("Title", "শিরোনাম")}<input maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} disabled={pending} /></label>
          <label>{pick("Scope", "পরিসর")}<select value={scope} disabled={pending} onChange={(e) => { setScope(e.target.value as ConversationInput["scope_type"]); setSelected([]); }}>
            <option value="single_paper">{pick("One paper", "একটি গবেষণাপত্র")}</option><option value="selected_papers">{pick("Selected papers", "নির্বাচিত গবেষণাপত্র")}</option><option value="collection">{pick("Collection", "সংগ্রহ")}</option>
          </select></label>
          {scope === "collection" ? <label>{pick("Collection", "সংগ্রহ")}<select required value={collection} onChange={(e) => setCollection(e.target.value)} disabled={pending}><option value="">{pick("Choose…", "নির্বাচন করুন…")}</option>{collections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            : <fieldset disabled={pending}><legend>{pick("Choose up to 50 papers", "সর্বোচ্চ ৫০টি গবেষণাপত্র নির্বাচন করুন")}</legend>
              <input aria-label={pick("Find saved papers", "সংরক্ষিত গবেষণাপত্র খুঁজুন")} value={query} onChange={(e) => { setQuery(e.target.value); setPaperPage(1); }} />
              <div className={styles.paperChoices}>{papers.map((paper) => <label key={paper.id} className={styles.choice}>
                <input type={scope === "single_paper" ? "radio" : "checkbox"} name="paper" checked={selected.includes(paper.id)} disabled={!selected.includes(paper.id) && selected.length >= 50}
                  onChange={() => setSelected((ids) => scope === "single_paper" ? [paper.id] : ids.includes(paper.id) ? ids.filter((id) => id !== paper.id) : [...ids, paper.id])} />
                <span>{paper.title}<small>{paper.document?.status === "completed" ? pick("Indexed", "ইনডেক্স সম্পন্ন") : pick("PDF not indexed", "পিডিএফ ইনডেক্স হয়নি")}</small></span>
              </label>)}</div>
              <div className={styles.row}><button type="button" disabled={paperPage <= 1} onClick={() => setPaperPage((p) => p - 1)}>{pick("Previous", "আগের")}</button><span>{paperPage} / {Math.max(1, paperPages)}</span><button type="button" disabled={paperPage >= paperPages} onClick={() => setPaperPage((p) => p + 1)}>{pick("Next", "পরের")}</button></div>
              <small>{selected.length} {pick("selected", "নির্বাচিত")}</small>
            </fieldset>}
          <button className="button primary" disabled={!ready || pending || (scope !== "collection" && selected.length === 0)}>{pick("Start conversation", "আলোচনা শুরু করুন")}</button>
        </form>
        <h2>{pick("Conversations", "আলোচনাসমূহ")}</h2>
        <ul className={styles.chats}>{chats.map((item) => <li key={item.id}>
          <button type="button" aria-pressed={chat?.id === item.id} disabled={pending} onClick={() => action(async () => { const result = await api.getConversation(item.id); if (alive.current) { setChat(result); setQuestion(""); retry.current = null; } })}>{item.title}</button>
          <button type="button" disabled={pending} aria-label={pick("Delete", "মুছুন") + ` ${item.title}`} onClick={() => action(async () => { await api.deleteConversation(item.id); if (alive.current) { setChats((items) => items.filter((c) => c.id !== item.id)); if (chat?.id === item.id) setChat(null); } })}>×</button>
        </li>)}</ul>
        {chats.length >= 50 && <button type="button" disabled={pending} onClick={() => action(async () => { const result = await api.getConversations(50, offset + 50); if (alive.current) { setChats((old) => [...old, ...result.filter((item) => !old.some((c) => c.id === item.id))]); setOffset(offset + 50); } })}>{pick("Load more", "আরও দেখুন")}</button>}
      </aside>
      <section className={`card ${styles.thread}`} aria-label={pick("Research conversation", "গবেষণা আলোচনা")}>
        {chat ? <>
          <header className={styles.row}><h2>{chat.title}</h2><span className="tag">{chat.language === "bn" ? "বাংলা" : "English"}</span></header>
          <div aria-live="polite" aria-busy={pending} className={styles.messages}>{chat.messages.map((message) => <article key={message.id} className={message.role === "user" ? styles.user : styles.answer}>
            <strong>{message.role === "user" ? pick("You", "আপনি") : pick("Research assistant", "গবেষণা সহকারী")}</strong>
            {message.role === "assistant" && <p className="tag">{message.evidence_status === "supported" ? pick("Supported evidence", "সমর্থিত প্রমাণ") : message.evidence_status === "partial_interpretation" ? pick("AI interpretation", "এআই ব্যাখ্যা") : pick("Insufficient evidence", "অপর্যাপ্ত প্রমাণ")}</p>}
            <p className={styles.pre}>{message.content}</p>
            {message.interpretation && <section><h3>{pick("AI interpretation / synthesis", "এআই ব্যাখ্যা / সংশ্লেষণ")}</h3><p className={styles.pre}>{message.interpretation}</p></section>}
            {message.missing_information && <section><h3>{pick("Missing information", "অনুপস্থিত তথ্য")}</h3><p>{message.missing_information}</p></section>}
            <div className={styles.citations}>{message.citations.map((citation) => <button type="button" key={citation.id} className={styles.citation} onClick={() => openSource(citation)}>
              <strong>{citation.paper_title} · {pick("p.", "পৃষ্ঠা")} {citation.page_number}</strong>{citation.section_heading && <small>{citation.section_heading}</small>}<q>{citation.quoted_snippet}</q><small>{pick("Open source page", "উৎসের পৃষ্ঠা খুলুন")}</small>
            </button>)}</div>
            {message.role === "assistant" && <div className={styles.followups}>{message.follow_up_questions.map((text, i) => <button type="button" key={i} disabled={pending} onClick={() => setQuestion(text)}>{text}</button>)}</div>}
            {message.provider_used && <small className="muted">{message.provider_used} · {message.model_used}</small>}
          </article>)}</div>
          <form onSubmit={send} className={styles.form}>
            <label>{pick("Inference", "উত্তর তৈরির ব্যবস্থা")}<select disabled={pending} value={provider} onChange={(e) => setProvider(e.target.value as AIProvider)}>
              <option value="auto">{pick("Default", "ডিফল্ট")}</option><option value="offline">{pick("Offline source excerpts", "অফলাইন উৎসের উদ্ধৃতি")}</option><option value="local">{pick("Local AI", "স্থানীয় এআই")}</option><option value="cloud" disabled={!prefs?.allow_external_ai}>{pick("Cloud AI (consent required)", "ক্লাউড এআই (অনুমতি প্রয়োজন)")}</option>
            </select></label>
            <label>{pick("Your question", "আপনার প্রশ্ন")}<textarea required minLength={2} maxLength={2000} rows={3} disabled={pending} value={question} onChange={(e) => setQuestion(e.target.value)} /></label>
            <button className="button primary" disabled={pending || question.trim().length < 2}>{pending ? pick("Working…", "কাজ চলছে…") : pick("Ask with sources", "উৎসভিত্তিক প্রশ্ন করুন")}</button>
          </form>
        </> : <div className="empty-state"><h2>{pick("Begin with your sources", "আপনার উৎস দিয়ে শুরু করুন")}</h2><p>{pick("Choose indexed papers or a collection. Offline mode returns verified source excerpts.", "ইনডেক্স করা গবেষণাপত্র বা সংগ্রহ নির্বাচন করুন। অফলাইন ব্যবস্থা যাচাই করা উৎসের উদ্ধৃতি দেখায়।")}</p></div>}
      </section>
    </div>
    {source && <LibraryDialog title={`${source.citation.paper_title} · ${pick("Page", "পৃষ্ঠা")} ${source.citation.page_number}`} onClose={() => { ++sourceTicket.current; setSource(null); }} wide>
      <blockquote>{source.citation.quoted_snippet}</blockquote>
      {source.error ? <p role="alert">{pick("The source page is unavailable. It may have been deleted or reindexed.", "উৎসের পৃষ্ঠা পাওয়া যাচ্ছে না। এটি মুছে ফেলা বা পুনরায় ইনডেক্স করা হতে পারে।")}</p> : <p className={styles.pre}>{source.text || pick("Loading source…", "উৎস লোড হচ্ছে…")}</p>}
    </LibraryDialog>}
  </>;
}
