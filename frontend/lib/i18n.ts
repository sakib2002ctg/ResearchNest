"use client";

import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, getAccessToken, type Theme } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type Language = "en" | "bn";

const english = {
  "nav.dashboard": "Dashboard",
  "nav.discover": "Discover Papers",
  "nav.library": "My Library",
  "nav.assistant": "AI Research Assistant",
  "nav.analysis": "Paper Analysis",
  "nav.writing": "Writing Studio",
  "nav.citations": "Citations",
  "nav.projects": "My Projects",
  "nav.insights": "Research Insights",
  "nav.learn": "Learn Research",
  "nav.settings": "Settings",
  "common.loading": "Loading…",
  "common.save": "Save",
  "common.cancel": "Cancel",
  "common.delete": "Delete",
  "common.search": "Search",
  "common.email": "Email",
  "common.password": "Password",
  "common.name": "Name",
  "common.language": "Language",
  "common.signIn": "Sign in",
  "common.signOut": "Sign out",
  "common.createAccount": "Create account",
  "common.retry": "Try again",
  "common.error": "Something went wrong. Please try again.",
  "landing.eyebrow": "Free platform · Public SaaS · Hybrid AI · English + Bangla",
  "landing.title": "Search Smarter. Research Better.",
  "landing.description": "Find papers, organize your research, and build a clearer path from discovery to understanding.",
  "landing.getStarted": "Get started for free",
  "landing.explore": "Explore the platform",
  "landing.features": "Everything you need to move research forward",
  "landing.howItWorks": "How it works",
  "landing.integrity": "Academic integrity comes first",
  "landing.integrityText": "ResearchNest supports discovery and organization. It does not replace careful reading, original thought, or proper citation.",
  "landing.discover": "Discover",
  "landing.organize": "Organize",
  "landing.understand": "Understand",
  "landing.privacy": "Privacy Policy",
  "landing.terms": "Terms",
  "landing.about": "About",
  "auth.loginTitle": "Welcome back",
  "auth.registerTitle": "Create your ResearchNest account",
  "auth.loginDescription": "Sign in to continue your research.",
  "auth.registerDescription": "Start building your personal research library.",
  "auth.username": "Username",
  "auth.confirmPassword": "Confirm password",
  "auth.forgotPassword": "Forgot password?",
  "auth.login": "Sign in",
  "auth.register": "Create account",
  "auth.noAccount": "New to ResearchNest?",
  "auth.haveAccount": "Already have an account?",
  "auth.resetTitle": "Reset your password",
  "auth.resetDescription": "Enter your email. If an account exists, we will send reset instructions.",
  "auth.sendReset": "Send reset instructions",
  "auth.newPassword": "New password",
  "auth.confirmReset": "Set new password",
  "auth.verifyTitle": "Verify your email",
  "auth.verifyDescription": "Enter the verification token from your email to confirm your account.",
  "auth.verifyToken": "Verification token",
  "auth.verify": "Verify email",
  "auth.verificationSent": "Verification instructions have been requested.",
  "dashboard.welcome": "Welcome back",
  "dashboard.subtitle": "Your research, in one place.",
  "dashboard.verified": "Your email is verified.",
  "dashboard.unverified": "Verify your email to help protect your account.",
  "dashboard.verify": "Send verification email",
  "dashboard.savedPapers": "Saved papers",
  "dashboard.activeSessions": "Active sessions",
  "dashboard.recentPapers": "Recently saved papers",
  "dashboard.recentActivity": "Recent security activity",
  "dashboard.quickActions": "Quick actions",
  "discover.title": "Discover papers",
  "discover.subtitle": "Search academic papers and save useful finds to your library.",
  "discover.save": "Save to library",
  "discover.saved": "Saved",
  "discover.noResults": "No papers found. Try another search.",
  "library.title": "My library",
  "library.subtitle": "Papers you have saved for your research.",
  "library.empty": "Your library is empty. Discover a paper to get started.",
  "library.remove": "Remove paper",
  "settings.title": "Settings",
  "settings.profile": "Profile",
  "settings.preferences": "Preferences",
  "settings.security": "Security",
  "settings.sessions": "Active sessions",
  "settings.language": "Display language",
  "settings.theme": "Theme",
  "settings.privacy": "Default privacy",
  "settings.externalAI": "Allow private documents to be sent to external AI providers",
  "settings.externalAIHelp": "This is explicit consent. It stays off until you turn it on.",
  "settings.changePassword": "Change password",
  "settings.export": "Download my data",
  "settings.revoke": "Revoke session",
  "settings.revokeAll": "Sign out all devices",
  "settings.deleteAccount": "Delete account",
  "settings.deleteConfirm": "This permanently removes your account and private data. Continue?",
  "settings.saved": "Settings saved.",
  "footer.rights": "Research tools for everyone.",
};

const bangla: Record<keyof typeof english, string> = {
  "nav.dashboard": "ড্যাশবোর্ড",
  "nav.discover": "গবেষণাপত্র খুঁজুন",
  "nav.library": "আমার লাইব্রেরি",
  "nav.assistant": "এআই গবেষণা সহকারী",
  "nav.analysis": "গবেষণাপত্র বিশ্লেষণ",
  "nav.writing": "লেখার স্টুডিও",
  "nav.citations": "তথ্যসূত্র",
  "nav.projects": "আমার প্রকল্প",
  "nav.insights": "গবেষণার অন্তর্দৃষ্টি",
  "nav.learn": "গবেষণা শিখুন",
  "nav.settings": "সেটিংস",
  "common.loading": "লোড হচ্ছে…",
  "common.save": "সংরক্ষণ",
  "common.cancel": "বাতিল",
  "common.delete": "মুছুন",
  "common.search": "খুঁজুন",
  "common.email": "ইমেইল",
  "common.password": "পাসওয়ার্ড",
  "common.name": "নাম",
  "common.language": "ভাষা",
  "common.signIn": "সাইন ইন",
  "common.signOut": "সাইন আউট",
  "common.createAccount": "অ্যাকাউন্ট খুলুন",
  "common.retry": "আবার চেষ্টা করুন",
  "common.error": "সমস্যা হয়েছে। আবার চেষ্টা করুন।",
  "landing.eyebrow": "বিনামূল্যের প্ল্যাটফর্ম · পাবলিক SaaS · হাইব্রিড এআই · ইংরেজি + বাংলা",
  "landing.title": "স্মার্টভাবে খুঁজুন। আরও ভালো গবেষণা করুন।",
  "landing.description": "গবেষণাপত্র খুঁজুন, গবেষণা গুছিয়ে রাখুন, আর আবিষ্কার থেকে বোঝাপড়ার পথে এগিয়ে যান।",
  "landing.getStarted": "বিনামূল্যে শুরু করুন",
  "landing.explore": "প্ল্যাটফর্ম দেখুন",
  "landing.features": "গবেষণাকে এগিয়ে নিতে প্রয়োজনীয় সবকিছু",
  "landing.howItWorks": "যেভাবে কাজ করে",
  "landing.integrity": "গবেষণার সততাই প্রথম",
  "landing.integrityText": "ResearchNest আবিষ্কার ও সংগঠনে সহায়তা করে। মনোযোগ দিয়ে পড়া, নিজস্ব চিন্তা বা সঠিক তথ্যসূত্রের বিকল্প নয়।",
  "landing.discover": "আবিষ্কার",
  "landing.organize": "গুছিয়ে রাখুন",
  "landing.understand": "বুঝে নিন",
  "landing.privacy": "গোপনীয়তা নীতি",
  "landing.terms": "ব্যবহারের শর্ত",
  "landing.about": "আমাদের সম্পর্কে",
  "auth.loginTitle": "আবার স্বাগতম",
  "auth.registerTitle": "ResearchNest অ্যাকাউন্ট খুলুন",
  "auth.loginDescription": "গবেষণা চালিয়ে যেতে সাইন ইন করুন।",
  "auth.registerDescription": "আপনার ব্যক্তিগত গবেষণা লাইব্রেরি তৈরি শুরু করুন।",
  "auth.username": "ব্যবহারকারীর নাম",
  "auth.confirmPassword": "পাসওয়ার্ড নিশ্চিত করুন",
  "auth.forgotPassword": "পাসওয়ার্ড ভুলে গেছেন?",
  "auth.login": "সাইন ইন",
  "auth.register": "অ্যাকাউন্ট খুলুন",
  "auth.noAccount": "ResearchNest-এ নতুন?",
  "auth.haveAccount": "আগেই অ্যাকাউন্ট আছে?",
  "auth.resetTitle": "পাসওয়ার্ড রিসেট করুন",
  "auth.resetDescription": "ইমেইল দিন। অ্যাকাউন্ট থাকলে রিসেট নির্দেশনা পাঠানো হবে।",
  "auth.sendReset": "রিসেট নির্দেশনা পাঠান",
  "auth.newPassword": "নতুন পাসওয়ার্ড",
  "auth.confirmReset": "নতুন পাসওয়ার্ড দিন",
  "auth.verifyTitle": "ইমেইল যাচাই করুন",
  "auth.verifyDescription": "অ্যাকাউন্ট নিশ্চিত করতে ইমেইলে পাওয়া যাচাইকরণ টোকেন দিন।",
  "auth.verifyToken": "যাচাইকরণ টোকেন",
  "auth.verify": "ইমেইল যাচাই করুন",
  "auth.verificationSent": "যাচাইকরণের নির্দেশনা পাঠানোর অনুরোধ হয়েছে।",
  "dashboard.welcome": "আবার স্বাগতম",
  "dashboard.subtitle": "আপনার গবেষণা, এক জায়গায়।",
  "dashboard.verified": "আপনার ইমেইল যাচাই হয়েছে।",
  "dashboard.unverified": "অ্যাকাউন্ট সুরক্ষায় ইমেইল যাচাই করুন।",
  "dashboard.verify": "যাচাইকরণ ইমেইল পাঠান",
  "dashboard.savedPapers": "সংরক্ষিত গবেষণাপত্র",
  "dashboard.activeSessions": "সক্রিয় সেশন",
  "dashboard.recentPapers": "সাম্প্রতিক সংরক্ষিত গবেষণাপত্র",
  "dashboard.recentActivity": "সাম্প্রতিক নিরাপত্তা কার্যক্রম",
  "dashboard.quickActions": "দ্রুত কাজ",
  "discover.title": "গবেষণাপত্র খুঁজুন",
  "discover.subtitle": "গবেষণাপত্র খুঁজে দরকারি লেখাগুলো লাইব্রেরিতে রাখুন।",
  "discover.save": "লাইব্রেরিতে রাখুন",
  "discover.saved": "সংরক্ষিত",
  "discover.noResults": "কোনো গবেষণাপত্র পাওয়া যায়নি। অন্যভাবে খুঁজুন।",
  "library.title": "আমার লাইব্রেরি",
  "library.subtitle": "গবেষণার জন্য আপনার সংরক্ষিত গবেষণাপত্র।",
  "library.empty": "লাইব্রেরি খালি। শুরু করতে একটি গবেষণাপত্র খুঁজুন।",
  "library.remove": "গবেষণাপত্র সরান",
  "settings.title": "সেটিংস",
  "settings.profile": "প্রোফাইল",
  "settings.preferences": "পছন্দ",
  "settings.security": "নিরাপত্তা",
  "settings.sessions": "সক্রিয় সেশন",
  "settings.language": "প্রদর্শনের ভাষা",
  "settings.theme": "থিম",
  "settings.privacy": "ডিফল্ট গোপনীয়তা",
  "settings.externalAI": "ব্যক্তিগত নথি বাইরের এআই সেবায় পাঠানোর অনুমতি দিন",
  "settings.externalAIHelp": "এটি আপনার স্পষ্ট সম্মতি। চালু না করা পর্যন্ত বন্ধ থাকবে।",
  "settings.changePassword": "পাসওয়ার্ড পরিবর্তন",
  "settings.export": "আমার তথ্য ডাউনলোড",
  "settings.revoke": "সেশন বাতিল",
  "settings.revokeAll": "সব ডিভাইস থেকে সাইন আউট",
  "settings.deleteAccount": "অ্যাকাউন্ট মুছুন",
  "settings.deleteConfirm": "এতে অ্যাকাউন্ট ও ব্যক্তিগত তথ্য স্থায়ীভাবে মুছে যাবে। এগোবেন?",
  "settings.saved": "সেটিংস সংরক্ষিত হয়েছে।",
  "footer.rights": "সবার জন্য গবেষণার সরঞ্জাম।",
};

export const dictionaries: Record<Language, Record<string, string>> = {
  en: english,
  bn: bangla,
};

const aliases: Record<string, string> = {
  "nav.Dashboard": "nav.dashboard",
  "nav.Discover Papers": "nav.discover",
  "nav.My Library": "nav.library",
  "nav.AI Research Assistant": "nav.assistant",
  "nav.Paper Analysis": "nav.analysis",
  "nav.Writing Studio": "nav.writing",
  "nav.Citations": "nav.citations",
  "nav.My Projects": "nav.projects",
  "nav.Research Insights": "nav.insights",
  "nav.Learn Research": "nav.learn",
  "nav.Settings": "nav.settings",
};

type I18nValue = {
  language: Language;
  setLanguage: (language: Language) => Promise<void>;
  t: (key: string) => string;
  pick: (english: string, bangla: string) => string;
  locale: string;
};

const I18nContext = createContext<I18nValue | null>(null);
const STORAGE_KEY = "researchnest.language";
let languageVersion = 0;
let preferenceSyncQueue: Promise<unknown> = Promise.resolve();

function storeLanguage(language: Language): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // Language remains usable in memory when browser storage is unavailable.
  }
}

function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  const dark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [language, setLanguageState] = useState<Language>("en");
  const userId = user?.id;
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const saved = window.localStorage.getItem(STORAGE_KEY);
        if (saved === "bn" || saved === "en") setLanguageState(saved);
      } catch {
        // English is the accessible default when storage cannot be read.
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  useEffect(() => {
    applyTheme("system");
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const updateSystemTheme = () => {
      if (document.documentElement.dataset.theme === "system") applyTheme("system");
    };
    const updateTheme = (event: Event) => {
      if (!(event instanceof CustomEvent)) return;
      const theme: unknown = event.detail;
      if (theme === "light" || theme === "dark" || theme === "system") {
        applyTheme(theme);
      }
    };
    media.addEventListener("change", updateSystemTheme);
    window.addEventListener("researchnest:theme", updateTheme);
    return () => {
      media.removeEventListener("change", updateSystemTheme);
      window.removeEventListener("researchnest:theme", updateTheme);
    };
  }, []);

  useEffect(() => {
    if (!userId) return;
    let active = true;
    const versionAtRequest = languageVersion;
    api
      .getPreferences()
      .then((preferences) => {
        if (active) {
          applyTheme(preferences.theme);
        }
        if (
          active &&
          languageVersion === versionAtRequest &&
          (preferences.language === "en" || preferences.language === "bn")
        ) {
          setLanguageState(preferences.language);
          storeLanguage(preferences.language);
        }
      })
      .catch(() => {
        // Keep the selected language if preferences are temporarily unavailable.
      });
    return () => {
      active = false;
    };
  }, [userId]);

  const setLanguage = useCallback(
    async (next: Language) => {
      languageVersion += 1;
      setLanguageState(next);
      storeLanguage(next);
      if (!userId) return;
      const tokenAtSelection = getAccessToken();
      const update = preferenceSyncQueue.catch(() => undefined).then(async () => {
        if (getAccessToken() === tokenAtSelection && tokenAtSelection) {
          await api.updatePreferences({ language: next });
        }
      });
      preferenceSyncQueue = update;
      await update;
    },
    [userId],
  );

  const value = useMemo<I18nValue>(
    () => ({
      language,
      setLanguage,
      t: (key) => {
        const normalized = aliases[key] ?? key;
        return dictionaries[language][normalized] ?? dictionaries.en[normalized] ?? key;
      },
      pick: (en, bn) => (language === "bn" ? bn : en),
      locale: language === "bn" ? "bn-BD" : "en-US",
    }),
    [language, setLanguage],
  );

  return createElement(I18nContext.Provider, { value }, children);
}

export function useI18n(): I18nValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used within I18nProvider.");
  return context;
}
