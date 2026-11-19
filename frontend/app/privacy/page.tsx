"use client";

import Link from "next/link";

import PublicHeader, { PublicFooter } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";

export default function PrivacyPage() {
  const { pick } = useI18n();
  const sections = [
    [pick("Your research belongs to you", "আপনার গবেষণা আপনারই"),
      pick("Your profile, saved papers, preferences, and account activity form your private workspace. ResearchNest does not claim ownership of your original research or writing. The original authors and publishers keep their rights to the academic works you discover.", "আপনার প্রোফাইল, সংরক্ষিত গবেষণাপত্র, পছন্দ ও অ্যাকাউন্টের কার্যক্রম মিলেই ব্যক্তিগত কর্মক্ষেত্র। ResearchNest আপনার মৌলিক গবেষণা বা লেখার মালিকানা দাবি করে না। আবিষ্কৃত গবেষণাপত্রের অধিকার মূল লেখক ও প্রকাশকেরই থাকে।")],
    [pick("What the platform stores", "প্ল্যাটফর্মে যে তথ্য থাকে"),
      pick("The account service stores your username, email, password hash, profile and preferences, saved paper metadata, and session and security-event metadata. Passwords are stored as hashes, not plaintext. Verification and recovery tokens are also stored as hashes and expire after use or their time limit.", "অ্যাকাউন্ট সেবা আপনার নাম, ইমেইল, পাসওয়ার্ডের হ্যাশ, প্রোফাইল ও পছন্দ, সংরক্ষিত গবেষণাপত্রের তথ্য এবং সেশন ও নিরাপত্তা কার্যক্রমের তথ্য রাখে। পাসওয়ার্ড সাধারণ লেখা হিসেবে নয়, হ্যাশ হিসেবে থাকে। যাচাই ও পুনরুদ্ধার টোকেনও হ্যাশ হিসেবে থাকে এবং ব্যবহার বা নির্ধারিত সময়ের পর অকার্যকর হয়।")],
    [pick("Private by default", "শুরু থেকেই ব্যক্তিগত"),
      pick("Personal library and account APIs require an authenticated session and check the account owner. The privacy-default preference records your intended default for future sharing features; selecting a different preference does not automatically publish your existing library.", "ব্যক্তিগত লাইব্রেরি ও অ্যাকাউন্ট API ব্যবহারে লগইন করা সেশন লাগে এবং মালিকানা যাচাই হয়। গোপনীয়তার পছন্দ ভবিষ্যতের শেয়ারিংয়ের জন্য আপনার ইচ্ছা সংরক্ষণ করে; এটি বদলালেই বর্তমান লাইব্রেরি প্রকাশিত হয় না।")],
    [pick("External AI is a choice", "বাহ্যিক AI ব্যবহার আপনার সিদ্ধান্ত"),
      pick("External AI consent starts off. You can change the consent preference in Settings. Document upload, AI analysis, and AI writing are future-phase features; this frontend does not send your private documents to a cloud model. Any future provider workflow must respect explicit consent and explain the information it sends.", "বাহ্যিক AI ব্যবহারের সম্মতি শুরুতে বন্ধ থাকে। সেটিংস থেকে এটি বদলাতে পারেন। নথি আপলোড, AI বিশ্লেষণ ও AI লেখার সুবিধা পরবর্তী ধাপে আসবে; এই ফ্রন্টএন্ড আপনার ব্যক্তিগত নথি ক্লাউড মডেলে পাঠায় না। ভবিষ্যতের যেকোনো প্রোভাইডার ব্যবহারে স্পষ্ট সম্মতি ও পাঠানো তথ্যের ব্যাখ্যা দরকার হবে।")],
    [pick("Your browser and sessions", "আপনার ব্রাউজার ও সেশন"),
      pick("The web app keeps the access token in memory for the current page session rather than persistent browser storage. A refresh requires a new sign-in. Your display language may be stored locally so it is remembered. You can inspect and revoke active device sessions from Settings.", "ওয়েব অ্যাপ অ্যাক্সেস টোকেন স্থায়ী ব্রাউজার স্টোরেজে না রেখে বর্তমান পেজ সেশনের মেমোরিতে রাখে। রিফ্রেশ করলে আবার লগইন করতে হবে। ভাষার পছন্দ মনে রাখতে স্থানীয়ভাবে রাখা হতে পারে। সেটিংস থেকে সক্রিয় ডিভাইস সেশন দেখে বন্ধ করতে পারেন।")],
    [pick("Export and deletion", "তথ্য রপ্তানি ও মুছে ফেলা"),
      pick("Settings lets you download a JSON export of your account, profile, preferences, saved papers, active session metadata, and security history. You can also delete your account. Deletion removes the account and its private records; security audit events are retained with the user reference cleared. Exports never include password hashes, bearer tokens, or recovery-token hashes.", "সেটিংস থেকে অ্যাকাউন্ট, প্রোফাইল, পছন্দ, গবেষণাপত্র, সক্রিয় সেশনের তথ্য ও নিরাপত্তা ইতিহাস JSON হিসেবে নামাতে পারেন। অ্যাকাউন্ট মুছেও ফেলতে পারেন। এতে অ্যাকাউন্ট ও ব্যক্তিগত রেকর্ড মুছে যায়; নিরাপত্তা নিরীক্ষার ঘটনাগুলোতে ব্যবহারকারীর সংযোগ সরিয়ে রাখা হয়। রপ্তানিতে পাসওয়ার্ড হ্যাশ, বেয়ারার টোকেন বা পুনরুদ্ধার টোকেনের হ্যাশ থাকে না।")],
    [pick("A platform still growing", "বেড়ে ওঠা একটি প্ল্যাটফর্ম"),
      pick("ResearchNest is in active development. This page describes the public-platform foundation, not a certification or a promise that future features are already available. Production hosting, backup retention, and email-provider details must be disclosed as the service is deployed and expanded.", "ResearchNest-এর উন্নয়ন চলছে। এই পাতা পাবলিক প্ল্যাটফর্মের ভিত্তি ব্যাখ্যা করে; এটি কোনো সনদ বা ভবিষ্যতের সুবিধা এখনই প্রস্তুত থাকার দাবি নয়। চালু ও বিস্তৃত হওয়ার সাথে সাথে হোস্টিং, ব্যাকআপ রাখার সময় এবং ইমেইল প্রোভাইডারের তথ্য প্রকাশ করতে হবে।")],
  ];
  return (
    <>
      <PublicHeader />
      <main className="legal-copy container">
        <p className="eyebrow">{pick("Built around your ownership", "আপনার মালিকানাকে কেন্দ্রে রেখে")}</p>
        <h1 className="mt-4 text-4xl font-medium tracking-tight sm:text-5xl">{pick("Privacy, in plain language.", "সহজ ভাষায় গোপনীয়তা।")}</h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-stone-500">{pick("You should understand what you share, what stays private, and what you control.", "কী শেয়ার হচ্ছে, কী ব্যক্তিগত থাকছে এবং কী আপনার নিয়ন্ত্রণে—সবই স্পষ্ট হওয়া উচিত।")}</p>
        <div className="mt-10 space-y-9">{sections.map(([title, content], index) => <section key={title}><h2 className="text-lg font-semibold"><span className="mr-3 text-xs font-medium text-emerald-700">0{index + 1}</span>{title}</h2><p className="mt-3 text-sm leading-7 text-stone-600">{content}</p></section>)}</div>
        <div className="mt-12 rounded-xl bg-emerald-50 p-5"><p className="text-sm text-emerald-900">{pick("Your privacy controls are in your workspace.", "গোপনীয়তার নিয়ন্ত্রণ আপনার কর্মক্ষেত্রেই আছে।")} <Link className="font-semibold underline underline-offset-4" href="/settings">{pick("Open Settings", "সেটিংস খুলুন")} <span aria-hidden="true">→</span></Link></p></div>
      </main>
      <PublicFooter />
    </>
  );
}
