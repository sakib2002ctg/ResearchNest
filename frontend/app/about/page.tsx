"use client";

import Link from "next/link";

import PublicHeader, { PublicFooter } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";

export default function AboutPage() {
  const { pick } = useI18n();
  return (
    <>
      <PublicHeader />
      <main className="container">
        <section className="section grid gap-10 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <div><p className="eyebrow">{pick("For the questions worth asking", "যে প্রশ্নগুলো করা দরকার")}</p><h1 className="mt-5 text-4xl font-medium leading-tight tracking-tight sm:text-5xl">{pick("Research should feel like discovery.", "গবেষণায় থাকুক আবিষ্কারের আনন্দ।")}<br /><span className="text-emerald-700">{pick("Not a maze.", "বিভ্রান্তির গোলকধাঁধা নয়।")}</span></h1><p className="mt-6 text-lg leading-relaxed text-stone-500">{pick("ResearchNest brings the first steps of research into one calm workspace: finding sources, saving useful papers, and keeping control of your work.", "গবেষণার শুরুর কাজগুলো—উৎস খোঁজা, প্রয়োজনীয় গবেষণাপত্র সংরক্ষণ ও নিজের কাজের নিয়ন্ত্রণ—ResearchNest একটি শান্ত কর্মক্ষেত্রে নিয়ে আসে।")}</p><Link className="button primary mt-7" href="/register">{pick("Find your starting point", "শুরুর পথ খুঁজে নিন")} <span aria-hidden="true">→</span></Link></div>
          <div className="rounded-2xl bg-[#e9f2e7] p-8 sm:p-10"><span className="text-6xl text-emerald-800/30" aria-hidden="true">“</span><p className="text-2xl font-medium leading-relaxed tracking-tight text-emerald-950">{pick("Good tools make room for better questions.", "ভালো সরঞ্জাম আরও ভালো প্রশ্নের জায়গা করে দেয়।")}</p><div className="mt-7 h-px w-16 bg-emerald-700/20" /><p className="mt-5 text-xs uppercase tracking-[.15em] text-emerald-800">{pick("The idea behind ResearchNest", "ResearchNest-এর পেছনের ভাবনা")}</p></div>
        </section>
        <section className="section border-t border-stone-200">
          <p className="eyebrow">{pick("What we believe", "আমাদের বিশ্বাস")}</p>
          <div className="feature-grid mt-8">{[
            [pick("Research is for everyone", "গবেষণা সবার জন্য"), pick("English and Bangla belong in the same workspace. Language should support your thinking rather than stand in its way.", "একই কর্মক্ষেত্রে ইংরেজি ও বাংলার জায়গা আছে। ভাষা ভাবনায় সাহায্য করবে, বাধা হয়ে দাঁড়াবে না।")],
            [pick("Ownership is a starting point", "মালিকানা শুরু থেকেই"), pick("Your private library belongs to your account. Export, session control, and account deletion are part of the foundation.", "ব্যক্তিগত লাইব্রেরি আপনার অ্যাকাউন্টের। তথ্য রপ্তানি, সেশন নিয়ন্ত্রণ ও অ্যাকাউন্ট মুছে ফেলা ভিত্তির অংশ।")],
            [pick("Judgment stays human", "বিচার থাকুক মানুষের হাতে"), pick("Tools can organize discovery. Original sources, honest citation, and your own critical thinking remain essential.", "সরঞ্জাম আবিষ্কার গুছিয়ে দিতে পারে। মূল উৎস, সৎ উদ্ধৃতি ও নিজের সমালোচনামূলক ভাবনা সবসময় জরুরি।")],
          ].map(([title, body]) => <article className="feature-card" key={title}><h2 className="text-lg font-medium">{title}</h2><p className="mt-3 text-sm leading-relaxed text-stone-500">{body}</p></article>)}</div>
        </section>
        <section className="section grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-stone-200 bg-white p-7"><p className="eyebrow">{pick("Available in this foundation", "এই ধাপে যা প্রস্তুত")}</p><h2 className="mt-4 text-2xl font-medium">{pick("A practical place to begin.", "শুরু করার বাস্তব জায়গা।")}</h2><p className="mt-4 text-sm leading-7 text-stone-500">{pick("Secure accounts and recovery, English/Bangla preferences, an account dashboard, arXiv paper discovery, private paper management, device sessions, and data export.", "নিরাপদ অ্যাকাউন্ট ও পুনরুদ্ধার, ইংরেজি/বাংলার পছন্দ, ড্যাশবোর্ড, arXiv অনুসন্ধান, ব্যক্তিগত গবেষণাপত্র পরিচালনা, ডিভাইস সেশন ও তথ্য রপ্তানি।")}</p></div>
          <div className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/40 p-7"><p className="eyebrow">{pick("On the roadmap", "ভবিষ্যতের পরিকল্পনা")}</p><h2 className="mt-4 text-2xl font-medium">{pick("Growing with your work.", "আপনার কাজের সাথে বেড়ে ওঠা।")}</h2><p className="mt-4 text-sm leading-7 text-stone-500">{pick("AI research assistance, paper analysis, writing and citations, projects, research insights, and guided learning. Preview screens describe these plans without presenting them as active services.", "AI গবেষণা সহায়তা, গবেষণাপত্র বিশ্লেষণ, লেখা ও উদ্ধৃতি, প্রকল্প, গবেষণার অন্তর্দৃষ্টি এবং সহায়ক শিক্ষা। নমুনা পাতায় এগুলো পরিকল্পনা হিসেবে দেখানো হয়, চালু সেবা হিসেবে নয়।")}</p></div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
