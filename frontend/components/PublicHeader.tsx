"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="ResearchNest">
      <span className="brand-mark" aria-hidden="true">
        <svg width="25" height="25" viewBox="0 0 28 28" fill="none">
          <path d="M6 7.5c3.7 0 6.3 1.1 8 3.3 1.7-2.2 4.3-3.3 8-3.3v12c-3.6 0-6.2 1.1-8 3.1-1.8-2-4.4-3.1-8-3.1v-12Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
          <path d="M14 11v11M10 4.5c2.4.3 3.7 1.7 4 4.2 2-2.9 4.2-4.3 6.7-4.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </span>
      <span>Research<span className="font-normal">Nest</span><span className="text-emerald-600">.</span></span>
    </Link>
  );
}

export function LanguageSwitch() {
  const { language, setLanguage, pick } = useI18n();
  const [error, setError] = useState(false);

  async function change(next: "en" | "bn") {
    setError(false);
    try {
      await setLanguage(next);
    } catch {
      setError(true);
    }
  }

  return (
    <div className="relative">
      <div className="language-switch" role="group" aria-label={pick("Choose language", "ভাষা বেছে নিন")}>
        <button type="button" aria-pressed={language === "en"} onClick={() => void change("en")}>EN</button>
        <span aria-hidden="true">|</span>
        <button type="button" aria-pressed={language === "bn"} onClick={() => void change("bn")}>বাংলা</button>
      </div>
      {error && <span className="absolute right-0 top-full mt-2 w-48 rounded-lg border bg-white p-2 text-xs text-red-700" role="status">{pick("Language changed locally. Preference sync failed.", "ভাষা বদলেছে। পছন্দ সংরক্ষণ করা যায়নি।")}</span>}
    </div>
  );
}

export default function PublicHeader() {
  const { isAuthenticated } = useAuth();
  const { pick } = useI18n();

  return (
    <header className="public-header container">
      <Brand />
      <nav className="hidden items-center gap-7 text-sm text-stone-600 md:flex" aria-label={pick("Public navigation", "পাবলিক নেভিগেশন")}>
        <Link href="/#features">{pick("The platform", "প্ল্যাটফর্ম")}</Link>
        <Link href="/#how-it-works">{pick("How it works", "যেভাবে কাজ করে")}</Link>
        <Link href="/about">{pick("Our purpose", "আমাদের লক্ষ্য")}</Link>
      </nav>
      <div className="flex items-center gap-3 sm:gap-5">
        <LanguageSwitch />
        {isAuthenticated ? (
          <Link className="button primary small" href="/dashboard">{pick("My workspace", "আমার কর্মক্ষেত্র")}</Link>
        ) : (
          <>
            <Link className="hidden text-sm font-medium sm:inline-flex" href="/login">{pick("Log in", "লগইন")}</Link>
            <Link className="button primary small" href="/register">{pick("Get started", "শুরু করুন")} <span aria-hidden="true">↗</span></Link>
          </>
        )}
      </div>
    </header>
  );
}

export function PublicFooter() {
  const { pick } = useI18n();
  return (
    <footer className="public-footer container">
      <div><Brand /><p className="mt-3 text-sm text-stone-500">{pick("A little more clarity. A lot more discovery.", "আরও স্পষ্ট ধারণা। আরও নতুন আবিষ্কার।")}</p></div>
      <nav className="flex flex-wrap gap-x-6 gap-y-3 text-sm text-stone-600" aria-label={pick("Footer navigation", "ফুটার নেভিগেশন")}>
        <Link href="/about">{pick("About", "পরিচিতি")}</Link>
        <Link href="/privacy">{pick("Privacy", "গোপনীয়তা")}</Link>
        <Link href="/terms">{pick("Terms", "শর্তাবলি")}</Link>
      </nav>
      <p className="w-full text-xs text-stone-400">{pick("ResearchNest · Built for the research journey.", "ResearchNest · গবেষণার প্রতিটি ধাপের জন্য।")}</p>
    </footer>
  );
}
