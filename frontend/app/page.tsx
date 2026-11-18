"use client";

import Link from "next/link";

import PublicHeader, { PublicFooter } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";

export default function LandingPage() {
  const { pick } = useI18n();
  const features = [
    { number: "01", title: pick("Follow your curiosity", "কৌতূহলের পথ ধরুন"), body: pick("Search academic papers from arXiv and bring useful discoveries into your own library.", "arXiv থেকে গবেষণাপত্র খুঁজে প্রয়োজনীয় আবিষ্কার নিজের লাইব্রেরিতে রাখুন।"), mark: "↗" },
    { number: "02", title: pick("Give good ideas a home", "ভালো ভাবনার নিজস্ব জায়গা"), body: pick("Save papers, search your personal library, and keep your research close at hand.", "গবেষণাপত্র সংরক্ষণ করুন, ব্যক্তিগত লাইব্রেরিতে খুঁজুন এবং হাতের কাছে রাখুন।"), mark: "▤" },
    { number: "03", title: pick("Stay in control", "নিয়ন্ত্রণ আপনার হাতে"), body: pick("Manage sessions, choose your preferences, export your information, or delete your account.", "সেশন ও পছন্দ নিয়ন্ত্রণ করুন, তথ্য রপ্তানি করুন বা নিজের অ্যাকাউন্ট মুছে ফেলুন।"), mark: "◇" },
  ];
  return (
    <>
      <PublicHeader />
      <main>
        <section className="marketing-hero container">
          <div className="hero-copy">
            <p className="eyebrow flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-emerald-600" />{pick("A clearer path from question to insight", "প্রশ্ন থেকে উপলব্ধির সহজ পথ")}</p>
            <h1 className="mt-6 text-5xl font-medium leading-[1.07] tracking-[-0.055em] sm:text-6xl lg:text-7xl">{pick("Search Smarter.", "আরও বুদ্ধিমত্তায় খুঁজুন।")}<br /><span className="text-emerald-700">{pick("Research Better.", "আরও ভালো গবেষণা করুন।")}</span></h1>
            <p className="mt-6 max-w-lg text-lg leading-relaxed text-stone-500">{pick("Your ideas deserve more than scattered tabs. Discover academic papers and build a private research space that grows with you.", "আপনার ভাবনাগুলো এলোমেলো ট্যাবের চেয়ে ভালো জায়গা প্রাপ্য। গবেষণাপত্র আবিষ্কার করুন ও নিজের সাথে বেড়ে ওঠা ব্যক্তিগত গবেষণার জায়গা তৈরি করুন।")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className="button primary">{pick("Start your research journey", "আপনার গবেষণাযাত্রা শুরু করুন")} <span aria-hidden="true">→</span></Link>
              <a href="#how-it-works" className="button secondary">{pick("See how it works", "যেভাবে কাজ করে")}</a>
            </div>
            <p className="mt-6 text-xs tracking-wide text-stone-500">{pick("Free platform · Public SaaS · Hybrid AI · English + Bangla", "বিনামূল্যের প্ল্যাটফর্ম · পাবলিক SaaS · হাইব্রিড AI · ইংরেজি + বাংলা")}</p>
            <div className="mt-8 flex items-center gap-3 text-xs text-stone-500"><span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-emerald-200 bg-emerald-50 text-emerald-800" aria-hidden="true">✓</span>{pick("Private by default. Built for curious minds.", "শুরু থেকেই ব্যক্তিগত। কৌতূহলী মনের জন্য তৈরি।")}</div>
          </div>
          <div className="hero-visual relative" aria-label={pick("ResearchNest platform preview", "ResearchNest প্ল্যাটফর্মের নমুনা")}>
            <div className="absolute -right-4 -top-5 h-32 w-32 rounded-full border border-emerald-200/70" aria-hidden="true" />
            <div className="absolute -bottom-7 -left-7 h-48 w-48 rounded-full bg-emerald-100/60" aria-hidden="true" />
            <div className="relative rounded-2xl border border-stone-200 bg-white p-5 shadow-[0_28px_80px_-35px_rgba(22,59,50,.35)] sm:p-7">
              <div className="mb-8 flex items-center justify-between border-b border-stone-100 pb-4">
                <div className="flex gap-1.5" aria-hidden="true"><span className="h-2 w-2 rounded-full bg-stone-200" /><span className="h-2 w-2 rounded-full bg-stone-200" /><span className="h-2 w-2 rounded-full bg-stone-200" /></div>
                <span className="text-[10px] font-medium uppercase tracking-[.2em] text-stone-400">{pick("A glimpse of your workspace", "আপনার কর্মক্ষেত্রের এক ঝলক")}</span>
              </div>
              <p className="eyebrow">{pick("Start with a question", "একটি প্রশ্ন দিয়ে শুরু")}</p>
              <h2 className="mt-3 text-2xl font-medium leading-snug tracking-tight">{pick("What will you discover today?", "আজ আপনি কী আবিষ্কার করবেন?")}</h2>
              <div className="mt-5 flex items-center gap-3 rounded-xl border border-stone-200 bg-stone-50/70 p-4 text-sm text-stone-400"><svg width="17" height="17" viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.5" /><path d="m12 12 5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>{pick("A topic, an author, a new direction…", "একটি বিষয়, একজন লেখক, নতুন দিশা…")}</div>
              <div className="mt-6 rounded-xl bg-[#eff5ed] p-5">
                <div className="flex items-center justify-between"><span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-800">arXiv</span><span className="text-emerald-800" aria-hidden="true">↗</span></div>
                <h3 className="mt-4 text-base font-medium">{pick("Discover the work behind the ideas.", "ভাবনার পেছনের গবেষণা আবিষ্কার করুন।")}</h3>
                <p className="mt-2 text-xs leading-relaxed text-stone-500">{pick("Search original sources. Save what matters. Come back with a clearer perspective.", "মূল উৎসে খুঁজুন। প্রয়োজনীয় অংশ রাখুন। আরও স্পষ্ট ধারণা নিয়ে ফিরুন।")}</p>
              </div>
              <div className="mt-5 flex items-center justify-between"><div className="flex items-center gap-2 text-xs text-stone-500"><span className="h-2 w-2 rounded-full bg-emerald-500" />{pick("Your library, your space", "আপনার লাইব্রেরি, আপনার জায়গা")}</div><span className="text-[10px] uppercase tracking-wider text-stone-400">{pick("Preview", "নমুনা")}</span></div>
            </div>
            <div className="relative ml-auto mr-[-8px] mt-[-12px] flex w-fit items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-3 shadow-sm"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-50 text-emerald-800" aria-hidden="true">অ</span><div><p className="text-xs font-medium">{pick("Think in your own language.", "নিজের ভাষায় ভাবুন।")}</p><p className="mt-0.5 text-[10px] text-stone-400">{pick("English + বাংলা", "বাংলা + English")}</p></div></div>
          </div>
        </section>
        <section id="features" className="section container scroll-mt-24">
          <div className="mb-10 flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="eyebrow">{pick("Less friction. More focus.", "কম বাধা। আরও মনোযোগ।")}</p><h2 className="mt-3 text-3xl font-medium tracking-tight sm:text-4xl">{pick("Space for your next big idea.", "আপনার পরবর্তী বড় ভাবনার জায়গা।")}</h2></div><p className="max-w-xs text-sm leading-relaxed text-stone-500">{pick("The essentials are ready. Your research journey is just getting started.", "প্রয়োজনীয় সুবিধাগুলো প্রস্তুত। আপনার গবেষণাযাত্রা সবে শুরু।")}</p></div>
          <div className="feature-grid">
            {features.map((feature) => <article key={feature.number} className="feature-card"><div className="flex items-start justify-between"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-xl text-emerald-800" aria-hidden="true">{feature.mark}</span><span className="text-xs text-stone-400">{feature.number}</span></div><h3 className="mt-7 text-lg font-medium tracking-tight">{feature.title}</h3><p className="mt-3 text-sm leading-relaxed text-stone-500">{feature.body}</p></article>)}
          </div>
        </section>
        <section id="how-it-works" className="section container scroll-mt-24">
          <div className="rounded-2xl border border-stone-200 bg-white p-7 sm:p-10 lg:p-12">
            <p className="eyebrow">{pick("From curiosity to clarity", "কৌতূহল থেকে স্পষ্টতা")}</p>
            <h2 className="mt-3 text-3xl font-medium tracking-tight">{pick("Find your rhythm in three steps.", "তিন ধাপে খুঁজে নিন গবেষণার ছন্দ।")}</h2>
            <div className="mt-10 grid gap-8 md:grid-cols-3">{[
              [pick("Ask a better question", "আরও ভালো প্রশ্ন করুন"), pick("Start with a topic, an author, or an idea you want to understand.", "একটি বিষয়, একজন লেখক বা বুঝতে চান এমন ভাবনা দিয়ে শুরু করুন।")],
              [pick("Build your reading list", "আপনার পাঠতালিকা তৈরি করুন"), pick("Explore original papers and save useful sources to your private library.", "মূল গবেষণাপত্র দেখুন এবং দরকারি উৎস ব্যক্তিগত লাইব্রেরিতে রাখুন।")],
              [pick("Make the thinking yours", "ভাবনাকে নিজের করে নিন"), pick("Read critically, connect ideas, and return to the sources that move your work forward.", "মনোযোগ দিয়ে পড়ুন, ভাবনার সংযোগ খুঁজুন এবং কাজ এগিয়ে নেয় এমন উৎসে ফিরুন।")],
            ].map(([title, body], index) => <div key={title}><span className="text-xs font-semibold text-emerald-700">0{index + 1}</span><h3 className="mt-4 font-medium">{title}</h3><p className="mt-3 text-sm leading-relaxed text-stone-500">{body}</p></div>)}</div>
          </div>
        </section>
        <section className="container pb-20">
          <div className="rounded-2xl bg-[#163b32] p-8 text-white sm:p-12"><div className="max-w-3xl"><p className="text-xs uppercase tracking-[.16em] text-emerald-200">{pick("Your work. Your integrity.", "আপনার কাজ। আপনার সততা।")}</p><h2 className="mt-4 text-3xl font-medium tracking-tight">{pick("A research partner. Never a shortcut around thinking.", "গবেষণার সঙ্গী। ভাবনার বিকল্প নয়।")}</h2><p className="mt-5 text-sm leading-relaxed text-emerald-50/70">{pick("Our commitment is to support honest scholarship. Always read and verify original sources, cite the work you use, and keep your judgment at the center. AI-assisted reading and writing are planned features, not a replacement for your authorship.", "আমাদের লক্ষ্য সৎ গবেষণায় সহায়তা করা। মূল উৎস পড়ুন ও যাচাই করুন, ব্যবহৃত কাজের সূত্র দিন এবং নিজের বিচারকে প্রাধান্য দিন। ভবিষ্যতের AI পাঠ ও লেখার সুবিধা আপনার লেখকসত্তার বিকল্প হবে না।")}</p><Link href="/about" className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-emerald-100">{pick("Get to know ResearchNest", "ResearchNest সম্পর্কে জানুন")} <span aria-hidden="true">→</span></Link></div></div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
