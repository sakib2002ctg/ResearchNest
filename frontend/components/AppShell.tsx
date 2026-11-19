"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { Icon } from "./Icon";

const navigation = [
  { href: "/dashboard", key: "dashboard", icon: "dashboard" },
  { href: "/discover", key: "discover", icon: "search" },
  { href: "/library", key: "library", icon: "library" },
  { href: "/assistant", key: "assistant", icon: "assistant" },
  { href: "/analysis", key: "analysis", icon: "analysis" },
  { href: "/writing", key: "writing", icon: "writing" },
  { href: "/citations", key: "citations", icon: "citations" },
  { href: "/projects", key: "projects", icon: "projects", phase: "10" },
  { href: "/insights", key: "insights", icon: "insights", phase: "10" },
  { href: "/learn", key: "learn", icon: "learn", phase: "11" },
  { href: "/settings", key: "settings", icon: "settings" },
] as const;

export function AppShell({ children, title, description, showHeading = false }: {
  children: ReactNode; title?: string; description?: string; showHeading?: boolean;
}) {
  const { user, isAuthenticated, logout } = useAuth();
  const { language, setLanguage, t, pick } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const current = navigation.find((item) => item.href === pathname);

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menuOpen]);

  async function switchLanguage(value: "en" | "bn") {
    setNotice("");
    try { await setLanguage(value); }
    catch {
      setNotice(pick(
        "Language changed here. We could not sync your account preference.",
        "এখানে ভাষা বদলেছে। অ্যাকাউন্টের পছন্দ সিঙ্ক করা যায়নি।"
      ));
    }
  }

  async function signOut() {
    try { await logout(); }
    catch { /* The local session is cleared even if the API is unavailable. */ }
    router.replace("/login");
  }

  if (!isAuthenticated || !user) {
    return (
      <main id="main-content" className="auth-gate">
        <div className="brand-mark"><Icon name="book" size={26} /></div>
        <p role="status">{pick("Opening your research workspace…", "আপনার গবেষণার কর্মপরিসর খুলছে…")}</p>
        <Link className="button secondary" href="/login">{pick("Go to sign in", "সাইন ইন করুন")}</Link>
      </main>
    );
  }

  return (
    <div className="app-frame">
      {menuOpen && <button className="sidebar-backdrop" type="button" onClick={() => setMenuOpen(false)}
        aria-label={pick("Close navigation", "নেভিগেশন বন্ধ করুন")} />}
      <aside id="workspace-navigation" className={`app-sidebar ${menuOpen ? "is-open" : ""}`}>
        <Link href="/" className="brand" aria-label="ResearchNest">
          <span className="brand-mark"><Icon name="book" size={23} /></span>
          <span>Research<span className="brand-light">Nest</span><small>{pick("A HOME FOR YOUR IDEAS", "আপনার ভাবনার ঠিকানা")}</small></span>
        </Link>
        <div className="workspace-label"><span className="workspace-dot" />{pick("Personal workspace", "ব্যক্তিগত কর্মপরিসর")}<Icon name="lock" size={13} /></div>
        <nav aria-label={pick("Workspace navigation", "কর্মপরিসরের নেভিগেশন")}>
          <div className="nav-section-label">{pick("YOUR RESEARCH", "আপনার গবেষণা")}</div>
          {navigation.map((item) => (
            <Link key={item.href} href={item.href}
              className={`nav-link ${pathname === item.href ? "is-active" : ""}`}
              aria-current={pathname === item.href ? "page" : undefined}
              onClick={() => setMenuOpen(false)}>
              <Icon name={item.icon} size={19} /><span>{t(`nav.${item.key}`)}</span>
              {"phase" in item && <span className="nav-phase" title={pick(`Preview · Phase ${item.phase}`, `প্রিভিউ · ধাপ ${item.phase}`)}>{item.phase}</span>}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note"><Icon name="leaf" size={20} /><p>{pick("Good research starts with a little curiosity.", "ভালো গবেষণার শুরু একটু কৌতূহল থেকে।")}</p><span>{pick("Make room for your next idea.", "আপনার পরের ভাবনার জন্য জায়গা রাখুন।")}</span></div>
        <div className="sidebar-user">
          <span className="avatar">{user.username.slice(0, 1).toUpperCase()}</span>
          <div><strong>{user.username}</strong><small title={user.email}>{user.email}</small></div>
          <button className="icon-button" type="button" onClick={() => { void signOut(); }}
            aria-label={pick("Sign out", "সাইন আউট")} title={pick("Sign out", "সাইন আউট")}><Icon name="logout" size={18} /></button>
        </div>
      </aside>
      <div className="app-body">
        <header className="app-topbar">
          <div className="topbar-start">
            <button type="button" className="icon-button mobile-menu" aria-controls="workspace-navigation"
              aria-expanded={menuOpen} aria-label={pick("Open navigation", "নেভিগেশন খুলুন")} onClick={() => setMenuOpen(!menuOpen)}><Icon name="menu" /></button>
            <span className="topbar-workspace">{pick("Workspace", "কর্মপরিসর")}</span><span className="breadcrumb-divider">/</span>
            <strong>{current ? t(`nav.${current.key}`) : title}</strong>
          </div>
          <div className="topbar-actions">
            <div className="language-switch" role="group" aria-label={pick("Language", "ভাষা")}>
              <button lang="en" type="button" aria-pressed={language === "en"} onClick={() => { void switchLanguage("en"); }}>EN</button>
              <span aria-hidden="true">|</span>
              <button lang="bn" type="button" aria-pressed={language === "bn"} onClick={() => { void switchLanguage("bn"); }}>বাংলা</button>
            </div>
            <Link href="/discover" className="button primary small topbar-discover"><Icon name="plus" size={16} />{pick("Find a paper", "গবেষণাপত্র খুঁজুন")}</Link>
          </div>
        </header>
        <main id="main-content" className="app-main">
          {showHeading && (title || description) && <div className="page-heading"><div><p className="eyebrow">{pick("YOUR RESEARCH, CONNECTED", "আপনার গবেষণা, এক সুতোয়")}</p>{title && <h1>{title}</h1>}{description && <p className="muted">{description}</p>}</div></div>}
          {notice && <p className="notice" role="status">{notice}</p>}
          {children}
          <footer className="workspace-footer"><span>ResearchNest</span><span>{pick("A little more clarity. A little closer to discovery.", "আরও একটু স্পষ্টতা। আবিষ্কারের আরও কাছে।")}</span><Link href="/privacy">{pick("Privacy", "গোপনীয়তা")}</Link></footer>
        </main>
      </div>
    </div>
  );
}

export default AppShell;
