"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import PublicHeader from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";

type AuthPanelProps = {
  title: string;
  description: string;
  children: ReactNode;
};

export default function AuthPanel({ title, description, children }: AuthPanelProps) {
  const { pick } = useI18n();
  return (
    <>
      <PublicHeader />
      <main className="auth-layout container">
        <section className="auth-story">
          <p className="eyebrow">{pick("A home for your research", "আপনার গবেষণার নিজস্ব ঠিকানা")}</p>
          <h1 className="mt-6 max-w-lg text-4xl font-medium leading-tight tracking-tight sm:text-5xl">{pick("Your next discovery starts with a question.", "একটি প্রশ্ন থেকেই শুরু আপনার পরবর্তী আবিষ্কার।")}</h1>
          <p className="mt-6 max-w-md text-base leading-relaxed opacity-75">{pick("Find the papers that matter. Keep your thinking organized. Make room for the work only you can do.", "প্রয়োজনীয় গবেষণাপত্র খুঁজুন। নিজের ভাবনাগুলো গুছিয়ে রাখুন। আপনার অনন্য কাজের জন্য সময় রাখুন।")}</p>
          <div className="my-10 h-px w-20 bg-current opacity-20" />
          <ul className="space-y-4 text-sm">
            <li className="flex items-center gap-3"><span aria-hidden="true">✓</span>{pick("One private workspace", "একটি ব্যক্তিগত কর্মক্ষেত্র")}</li>
            <li className="flex items-center gap-3"><span aria-hidden="true">✓</span>{pick("English and Bangla, side by side", "ইংরেজি ও বাংলা, পাশাপাশি")}</li>
            <li className="flex items-center gap-3"><span aria-hidden="true">✓</span>{pick("Your data. Your choices.", "আপনার তথ্য। আপনার সিদ্ধান্ত।")}</li>
          </ul>
          <div className="mt-16 flex items-center gap-3 text-xs opacity-60">
            <svg width="17" height="19" viewBox="0 0 17 19" fill="none" aria-hidden="true"><path d="m8.5 1.5 6 2.4v5.4c0 3.3-2.2 5.9-6 8.2-3.8-2.3-6-4.9-6-8.2V3.9l6-2.4Z" stroke="currentColor" strokeWidth="1.4" /><path d="m5.8 9.2 1.7 1.7 3.6-3.6" stroke="currentColor" strokeWidth="1.4" /></svg>
            {pick("Privacy is part of the foundation.", "গোপনীয়তা শুরু থেকেই ভিত্তির অংশ।")}
          </div>
        </section>
        <section className="auth-card" aria-label={title}>
          <p className="eyebrow mb-3">ResearchNest</p>
          <h2 className="text-3xl font-semibold tracking-tight">{title}</h2>
          <p className="mt-3 mb-8 text-sm leading-relaxed text-stone-500">{description}</p>
          {children}
          <p className="mt-8 text-xs leading-relaxed text-stone-500">{pick("By using ResearchNest, you agree to our", "ResearchNest ব্যবহার করে আপনি আমাদের")} <Link className="underline underline-offset-2" href="/terms">{pick("Terms", "শর্তাবলি")}</Link> {pick("and", "ও")} <Link className="underline underline-offset-2" href="/privacy">{pick("Privacy Policy", "গোপনীয়তা নীতি")}</Link>{pick(".", " মেনে নেন।")}</p>
        </section>
      </main>
    </>
  );
}
