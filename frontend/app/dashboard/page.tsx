"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Icon } from "@/components/Icon";
import { api, type Dashboard } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const activityLabels: Record<string, readonly [string, string]> = {
  "user.register": ["Account created", "অ্যাকাউন্ট তৈরি হয়েছে"],
  "auth.login.success": ["Signed in successfully", "সফলভাবে সাইন ইন হয়েছে"],
  "auth.login.failed": ["Unsuccessful sign-in attempt", "সাইন ইন করার ব্যর্থ চেষ্টা"],
  "auth.logout": ["Signed out of a session", "একটি সেশন থেকে সাইন আউট হয়েছে"],
  "auth.logout_all": ["Signed out of all sessions", "সব সেশন থেকে সাইন আউট হয়েছে"],
  "auth.session.revoked": ["A device session was revoked", "একটি ডিভাইসের সেশন বাতিল হয়েছে"],
  "auth.email_verification.requested": ["Verification email requested", "যাচাইকরণ ইমেইল চাওয়া হয়েছে"],
  "auth.email_verification.confirmed": ["Email address verified", "ইমেইল ঠিকানা যাচাই হয়েছে"],
  "auth.password_reset.requested": ["Password reset requested", "পাসওয়ার্ড পুনরুদ্ধার চাওয়া হয়েছে"],
  "auth.password_reset.completed": ["Password reset completed", "পাসওয়ার্ড পুনরুদ্ধার সম্পন্ন"],
  "auth.password_change": ["Password changed", "পাসওয়ার্ড পরিবর্তন হয়েছে"],
  "user.profile.update": ["Profile updated", "প্রোফাইল হালনাগাদ হয়েছে"],
  "user.preferences.update": ["Preferences updated", "পছন্দসমূহ হালনাগাদ হয়েছে"],
  "user.data.exported": ["Account data exported", "অ্যাকাউন্টের তথ্য রপ্তানি হয়েছে"],
};

export default function DashboardPage() {
  const { user, isAuthenticated } = useAuth();
  const { pick, locale } = useI18n();
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const requestNumber = useRef(0);

  const load = useCallback(async (showLoading = true) => {
    if (!isAuthenticated) return;
    const request = ++requestNumber.current;
    if (showLoading) setLoading(true);
    setFailed(false);
    try {
      const result = await api.getDashboard();
      if (request === requestNumber.current) setData(result);
    } catch {
      if (request === requestNumber.current) setFailed(true);
    } finally {
      if (request === requestNumber.current) setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(false), 0);
    return () => {
      window.clearTimeout(timer);
      requestNumber.current += 1;
    };
  }, [load]);

  const number = (value: number) => new Intl.NumberFormat(locale).format(value);
  const date = (value: string) => new Intl.DateTimeFormat(locale, {
    dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));
  const name = data?.profile.full_name || user?.username || pick("researcher", "গবেষক");

  return (
    <AppShell
      title={pick("Dashboard", "ড্যাশবোর্ড")}
      description={pick("A little clarity for your next discovery.", "আপনার পরবর্তী আবিষ্কারের জন্য একটু স্বচ্ছতা।")}
    >
      <div className="page-heading">
        <div>
          <p className="eyebrow">{pick("YOUR RESEARCH, CONNECTED", "আপনার গবেষণা, এক জায়গায়")}</p>
          <h1>{pick("Welcome back,", "আবার স্বাগতম,")} {name}.</h1>
          <p className="muted">{pick("Make room for your next good question.", "আপনার পরবর্তী গুরুত্বপূর্ণ প্রশ্নের জন্য প্রস্তুত হোন।")}</p>
        </div>
        <Link href="/discover" className="button primary"><Icon name="search" size={17} />{pick("Discover papers", "গবেষণাপত্র খুঁজুন")}</Link>
      </div>

      {loading && <div className="loading-state" role="status">{pick("Preparing your research workspace…", "আপনার গবেষণার কর্মপরিসর প্রস্তুত হচ্ছে…")}</div>}
      {failed && <div className="notice error" role="alert"><p>{pick("Your dashboard could not be loaded. Please try again.", "ড্যাশবোর্ড লোড করা যায়নি। আবার চেষ্টা করুন।")}</p><button className="button secondary small" onClick={() => void load()}>{pick("Try again", "আবার চেষ্টা করুন")}</button></div>}

      {data && !loading && !failed && <>
        {!data.verification_status && <div className="notice flex flex-wrap items-center justify-between gap-4">
          <div><strong>{pick("One small step: verify your email", "আর একটি ধাপ: ইমেইল যাচাই করুন")}</strong><p className="muted">{pick("Confirm your address to keep your account identity up to date.", "আপনার পরিচয় নিশ্চিত করতে ইমেইল ঠিকানা যাচাই করুন।")}</p></div>
          <Link href="/verify-email" className="button secondary small">{pick("Verify email", "ইমেইল যাচাই করুন")}<Icon name="arrow-right" size={16} /></Link>
        </div>}

        <div className="stats-grid">
          <article className="stat-card"><span className="stat-icon"><Icon name="library" size={21} /></span><p className="muted">{pick("Saved papers", "সংরক্ষিত গবেষণাপত্র")}</p><strong className="text-4xl tracking-tight">{number(data.saved_papers_count)}</strong><Link href="/library" className="mt-3 inline-flex items-center gap-2 text-sm">{pick("Open your library", "আপনার লাইব্রেরি খুলুন")}<Icon name="arrow-right" size={14} /></Link></article>
          <article className="stat-card"><span className="stat-icon"><Icon name="monitor" size={21} /></span><p className="muted">{pick("Active sessions", "সক্রিয় সেশন")}</p><strong className="text-4xl tracking-tight">{number(data.active_sessions_count)}</strong><Link href="/settings#sessions" className="mt-3 inline-flex items-center gap-2 text-sm">{pick("Manage your devices", "ডিভাইস পরিচালনা করুন")}<Icon name="arrow-right" size={14} /></Link></article>
          <article className="stat-card"><span className="stat-icon"><Icon name="shield" size={21} /></span><p className="muted">{pick("Library privacy", "লাইব্রেরির গোপনীয়তা")}</p><strong className="text-2xl tracking-tight">{pick("Yours to control", "নিয়ন্ত্রণ আপনার হাতে")}</strong><p className="mt-3 text-sm muted">{data.allow_external_ai ? pick("External AI consent is on.", "বহিরাগত এআই ব্যবহারের সম্মতি চালু।") : pick("External AI consent is off.", "বহিরাগত এআই ব্যবহারের সম্মতি বন্ধ।")}</p></article>
        </div>

        <div className="content-grid">
          <section className="card">
            <div className="section-heading"><div><p className="eyebrow">{pick("PICK UP WHERE YOU LEFT OFF", "যেখান থেকে থেমেছিলেন")}</p><h2>{pick("Recently saved", "সম্প্রতি সংরক্ষিত")}</h2></div><Link href="/library" className="button ghost small">{pick("View library", "লাইব্রেরি দেখুন")}<Icon name="arrow-right" size={15} /></Link></div>
            {data.recent_papers.length === 0 ? <div className="empty-state"><Icon name="book-open" size={32} /><h3>{pick("Your next idea starts here", "আপনার পরবর্তী ভাবনার শুরু এখানে")}</h3><p>{pick("Save a paper from Discover or add one to your library.", "অনুসন্ধান থেকে একটি গবেষণাপত্র সংরক্ষণ করুন অথবা লাইব্রেরিতে যোগ করুন।")}</p><Link className="button secondary" href="/discover">{pick("Find your first paper", "প্রথম গবেষণাপত্র খুঁজুন")}</Link></div> : <div className="paper-list">{data.recent_papers.map((paper) => <article key={paper.id} className="paper-card"><div className="flex items-start gap-3"><span className="mt-1 shrink-0 muted"><Icon name="file-text" size={20} /></span><div className="min-w-0"><span className="tag">{paper.source || pick("Research paper", "গবেষণাপত্র")}</span><h3>{paper.title}</h3><p className="muted text-sm">{paper.authors || pick("Authors not listed", "লেখকের তথ্য নেই")}</p>{paper.url && <a href={paper.url} className="mt-2 inline-flex items-center gap-1 text-sm" target="_blank" rel="noopener noreferrer">{pick("Read original", "মূল প্রকাশনা পড়ুন")}<Icon name="external-link" size={13} /></a>}</div></div></article>)}</div>}
          </section>
          <aside className="flex flex-col gap-6">
            <section className="card">
              <div className="section-heading"><h2>{pick("Recent activity", "সাম্প্রতিক কার্যক্রম")}</h2><Icon name="activity" size={20} /></div>
              {data.recent_activity.length === 0 ? <p className="muted py-4">{pick("Your account activity will appear here.", "আপনার অ্যাকাউন্টের কার্যক্রম এখানে দেখা যাবে।")}</p> : <ul className="activity-list">{data.recent_activity.map((event) => { const label = activityLabels[event.action]; return <li key={event.id}><span className="activity-dot" /><div><p className="text-sm font-medium">{label ? pick(label[0], label[1]) : pick("Account activity", "অ্যাকাউন্টের কার্যক্রম")}</p><time className="muted text-xs" dateTime={event.created_at}>{date(event.created_at)}</time></div></li>; })}</ul>}
              <Link href="/settings" className="mt-4 inline-flex items-center gap-2 text-sm">{pick("Account settings", "অ্যাকাউন্ট সেটিংস")}<Icon name="arrow-right" size={14} /></Link>
            </section>
            <section className="card bg-[var(--accent-soft)]"><Icon name="sparkles" size={23} /><h3 className="mt-3">{pick("A thoughtful research habit", "গবেষণায় একটি ভালো অভ্যাস")}</h3><p className="muted mt-2 text-sm">{pick("Read the original. Question the claim. Keep track of the source. Good research starts with curiosity and care.", "মূল প্রকাশনা পড়ুন। দাবিগুলো যাচাই করুন। উৎসের তথ্য রাখুন। কৌতূহল ও সতর্কতা থেকেই ভালো গবেষণার শুরু।")}</p></section>
          </aside>
        </div>
      </>}
    </AppShell>
  );
}
