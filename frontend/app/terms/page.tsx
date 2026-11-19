"use client";

import Link from "next/link";

import PublicHeader, { PublicFooter } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";

export default function TermsPage() {
  const { pick } = useI18n();
  const sections = [
    [pick("Use the platform responsibly", "দায়িত্বশীলভাবে ব্যবহার করুন"), pick("Use ResearchNest for lawful learning, discovery, and research. Do not attempt to access another person's workspace, evade security controls, automate abusive requests, or upload material you are not entitled to use.", "বৈধ শিক্ষা, আবিষ্কার ও গবেষণার কাজে ResearchNest ব্যবহার করুন। অন্যের কর্মক্ষেত্রে ঢোকা, নিরাপত্তা এড়ানো, স্বয়ংক্রিয় অপব্যবহার বা ব্যবহারের অধিকার নেই এমন উপকরণ দেওয়া থেকে বিরত থাকুন।")],
    [pick("Keep your account secure", "অ্যাকাউন্ট নিরাপদ রাখুন"), pick("Use accurate account details and a unique password. Do not share access tokens or recovery codes. Review active sessions, revoke unfamiliar devices, and reset your password if you believe your account is compromised.", "সঠিক তথ্য ও আলাদা পাসওয়ার্ড দিন। অ্যাক্সেস টোকেন বা পুনরুদ্ধার কোড শেয়ার করবেন না। সক্রিয় সেশন দেখুন, অপরিচিত ডিভাইস বন্ধ করুন এবং অ্যাকাউন্ট ঝুঁকিতে মনে হলে পাসওয়ার্ড বদলান।")],
    [pick("Respect authorship and original sources", "লেখকসত্তা ও মূল উৎসের সম্মান করুন"), pick("You retain ownership of your original contributions. Saving paper metadata or linking to an academic source does not transfer copyright or grant additional reuse rights. Read the source, check its license, cite it accurately, and follow your institution's academic-integrity rules.", "আপনার মৌলিক অবদানের মালিকানা আপনার থাকে। গবেষণাপত্রের তথ্য বা উৎসের লিংক সংরক্ষণে কপিরাইট বদলে যায় না বা পুনর্ব্যবহারের নতুন অধিকার মেলে না। মূল উৎস পড়ুন, লাইসেন্স দেখুন, সঠিক সূত্র দিন এবং প্রতিষ্ঠানের গবেষণা-সততার নীতি মানুন।")],
    [pick("Use your own judgment", "নিজের বিচার প্রয়োগ করুন"), pick("Search results and third-party records may contain errors or omissions. Verify important claims against original publications. Future AI features will assist research; they will not guarantee correctness or replace your responsibility for submitted work.", "অনুসন্ধানের ফল বা তৃতীয় পক্ষের রেকর্ডে ভুল বা ঘাটতি থাকতে পারে। গুরুত্বপূর্ণ দাবি মূল প্রকাশনার সাথে মিলিয়ে নিন। ভবিষ্যতের AI গবেষণায় সাহায্য করবে; নির্ভুলতার নিশ্চয়তা দেবে না এবং জমা দেওয়া কাজের দায় আপনারই থাকবে।")],
    [pick("Understand the current scope", "বর্তমান সুবিধা বুঝে ব্যবহার করুন"), pick("The public-platform foundation provides account management, paper discovery, and a private paper library. AI assistance, detailed paper analysis, writing, citations, projects, and learning tools are identified as later-phase previews. Availability can change during development; do not rely on the service as your only copy of essential research.", "পাবলিক প্ল্যাটফর্মের ভিত্তিতে অ্যাকাউন্ট পরিচালনা, গবেষণাপত্র খোঁজা ও ব্যক্তিগত লাইব্রেরি আছে। AI সহায়তা, বিশ্লেষণ, লেখা, উদ্ধৃতি, প্রকল্প ও শিক্ষাসেবা পরবর্তী ধাপের নমুনা হিসেবে দেখানো হয়। উন্নয়নের সময় সুবিধা বদলাতে পারে; গুরুত্বপূর্ণ গবেষণার একমাত্র কপি এখানে রাখবেন না।")],
    [pick("Choose when to leave", "চলে যাওয়ার সিদ্ধান্ত আপনার"), pick("You can export your information and delete your account from Settings. The Privacy Policy explains how private records and retained security events are handled. These public-platform terms will need to evolve alongside the deployed service and its operator details.", "সেটিংস থেকে তথ্য নামিয়ে অ্যাকাউন্ট মুছতে পারেন। ব্যক্তিগত রেকর্ড ও রাখা নিরাপত্তা ঘটনাগুলো কীভাবে পরিচালিত হয় তা গোপনীয়তা নীতিতে আছে। চালু সেবা ও পরিচালনাকারীর তথ্যের সাথে এই শর্তগুলোও হালনাগাদ করতে হবে।")],
  ];
  return (
    <>
      <PublicHeader />
      <main className="legal-copy container">
        <p className="eyebrow">{pick("A shared commitment to good research", "ভালো গবেষণার জন্য সম্মিলিত অঙ্গীকার")}</p>
        <h1 className="mt-4 text-4xl font-medium tracking-tight sm:text-5xl">{pick("Terms of use.", "ব্যবহারের শর্তাবলি।")}</h1>
        <p className="mt-5 text-lg leading-relaxed text-stone-500">{pick("A few clear expectations for using ResearchNest thoughtfully.", "ResearchNest মনোযোগ দিয়ে ব্যবহার করার কয়েকটি স্পষ্ট প্রত্যাশা।")}</p>
        <div className="mt-10 space-y-9">{sections.map(([title, content], index) => <section key={title}><h2 className="text-lg font-semibold"><span className="mr-3 text-xs font-medium text-emerald-700">0{index + 1}</span>{title}</h2><p className="mt-3 text-sm leading-7 text-stone-600">{content}</p></section>)}</div>
        <p className="mt-10 text-sm text-stone-500">{pick("Also read our", "আরও পড়ুন আমাদের")} <Link className="font-medium text-emerald-800 underline underline-offset-4" href="/privacy">{pick("Privacy Policy", "গোপনীয়তা নীতি")}</Link>.</p>
      </main>
      <PublicFooter />
    </>
  );
}
