"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import AuthPanel from "@/components/AuthPanel";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const { pick } = useI18n();
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await login(email.trim(), password);
      setPassword("");
      router.replace("/dashboard");
    } catch (cause: unknown) {
      setError(cause instanceof ApiError && cause.status === 401
        ? pick("The email or password is incorrect.", "ইমেইল বা পাসওয়ার্ড সঠিক নয়।")
        : pick("We could not sign you in. Please check your connection and try again.", "লগইন করা যায়নি। সংযোগ পরীক্ষা করে আবার চেষ্টা করুন।"));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthPanel title={pick("Welcome back.", "আবার স্বাগতম।")} description={pick("Sign in and pick up where your curiosity left off.", "লগইন করুন এবং আপনার কৌতূহলের পথ ধরে এগিয়ে যান।")}>
      <form className="form-stack" onSubmit={submit}>
        <div className="field"><label htmlFor="login-email">{pick("Email address", "ইমেইল ঠিকানা")}</label><input id="login-email" name="email" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={pick("you@university.edu", "you@university.edu")} maxLength={255} /></div>
        <div className="field"><div className="flex items-center justify-between gap-3"><label htmlFor="login-password">{pick("Password", "পাসওয়ার্ড")}</label><Link href="/reset-password" className="text-xs font-medium text-emerald-700">{pick("Forgot password?", "পাসওয়ার্ড ভুলে গেছেন?")}</Link></div><input id="login-password" name="password" type="password" required minLength={8} maxLength={128} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={pick("Enter your password", "আপনার পাসওয়ার্ড লিখুন")} /></div>
        {error && <p className="notice error" role="alert">{error}</p>}
        <button type="submit" className="button primary w-full" disabled={pending}>{pending ? pick("Signing in…", "লগইন হচ্ছে…") : pick("Log in to your workspace", "আপনার কর্মক্ষেত্রে লগইন করুন")} <span aria-hidden="true">→</span></button>
        <p className="text-center text-sm text-stone-500">{pick("New to ResearchNest?", "ResearchNest-এ নতুন?")} <Link href="/register" className="font-medium text-emerald-800">{pick("Create an account", "অ্যাকাউন্ট তৈরি করুন")}</Link></p>
        <p className="text-xs leading-relaxed text-stone-400">{pick("For your privacy, signing in lasts for this browser tab. Refreshing requires a new login.", "আপনার গোপনীয়তার জন্য লগইন এই ট্যাবেই সীমিত। রিফ্রেশ করলে আবার লগইন করতে হবে।")}</p>
      </form>
    </AuthPanel>
  );
}
