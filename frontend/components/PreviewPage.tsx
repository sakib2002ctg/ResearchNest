"use client";

import Link from "next/link";
import { AppShell } from "./AppShell";
import { Icon } from "./Icon";
import { useI18n } from "@/lib/i18n";

export function PreviewPage({ english, bangla, phase, icon, detailEn, detailBn }: {
  english: string; bangla: string; phase: string; icon: string; detailEn: string; detailBn: string;
}) {
  const { pick } = useI18n();
  return <AppShell title={pick(english, bangla)} description={pick("A look at what's ahead for your research workspace.", "আপনার গবেষণার কর্মপরিসরে সামনে যা আসছে।")} showHeading>
    <section className="card preview-card">
      <div className="preview-orbit"><Icon name={icon} size={44} /></div>
      <span className="tag">{pick(`Phase ${phase} · Preview`, `ধাপ ${phase} · প্রিভিউ`)}</span>
      <h2>{pick("Thoughtfully planned. Coming later.", "যত্নের সঙ্গে পরিকল্পিত। পরে আসছে।")}</h2>
      <p>{pick(detailEn, detailBn)}</p>
      <p className="muted">{pick("This is a preview shell. This feature does not process content or call AI services yet.", "এটি একটি প্রিভিউ। এই ফিচার এখনো বিষয়বস্তু প্রক্রিয়াকরণ বা এআই সেবায় অনুরোধ করে না।")}</p>
      <Link className="button primary" href="/discover">{pick("Explore papers in the meantime", "এখন গবেষণাপত্র খুঁজে দেখুন")}<Icon name="arrow" size={17} /></Link>
    </section>
  </AppShell>;
}
