"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import AuthPanel from "@/components/AuthPanel";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function RegisterPage() {
  const { pick } = useI18n();
  const { register } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError(pick("Your passwords do not match.", "পাসওয়ার্ড দুটি এক নয়।"));
      return;
    }
    setPending(true);
    try {
      await register(username.trim(), email.trim(), password);
      setPassword("");
      setConfirmation("");
      router.replace("/verify-email");
    } catch (cause: unknown) {
      setError(cause instanceof ApiError && cause.status === 400
        ? pick("That email or username is already in use. Try another or log in.", "এই ইমেইল বা ব্যবহারকারীর নাম আগে থেকেই আছে। অন্যটি দিন বা লগইন করুন।")
        : pick("We could not finish registration. Check your connection, or try logging in if your account was created.", "নিবন্ধন সম্পন্ন করা যায়নি। সংযোগ পরীক্ষা করুন, অথবা অ্যাকাউন্ট তৈরি হয়ে থাকলে লগইন করুন।"));
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthPanel title={pick("Make room for discovery.", "নতুন আবিষ্কারের জায়গা করুন।")} description={pick("Create your free account. Your personal research space is waiting.", "বিনামূল্যে অ্যাকাউন্ট তৈরি করুন। আপনার ব্যক্তিগত গবেষণার জায়গা প্রস্তুত।")}>
      <form className="form-stack" onSubmit={submit}>
        <div className="field"><label htmlFor="register-username">{pick("Username", "ব্যবহারকারীর নাম")}</label><input id="register-username" name="username" required minLength={3} maxLength={50} autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder={pick("Choose a username", "ব্যবহারকারীর নাম বেছে নিন")} /></div>
        <div className="field"><label htmlFor="register-email">{pick("Email address", "ইমেইল ঠিকানা")}</label><input id="register-email" name="email" type="email" required maxLength={255} autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@university.edu" /></div>
        <div className="field"><label htmlFor="register-password">{pick("Password", "পাসওয়ার্ড")}</label><input id="register-password" name="password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} aria-describedby="password-hint" /><p id="password-hint" className="text-xs text-stone-400">{pick("Use 8–128 characters and a password you do not use elsewhere.", "৮–১২৮ অক্ষরের এমন পাসওয়ার্ড দিন যা অন্য কোথাও ব্যবহার করেন না।")}</p></div>
        <div className="field"><label htmlFor="register-confirm">{pick("Confirm password", "আবার পাসওয়ার্ড লিখুন")}</label><input id="register-confirm" name="confirm-password" type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></div>
        {error && <p className="notice error" role="alert">{error}</p>}
        <button type="submit" className="button primary w-full" disabled={pending}>{pending ? pick("Creating your account…", "অ্যাকাউন্ট তৈরি হচ্ছে…") : pick("Create my account", "আমার অ্যাকাউন্ট তৈরি করুন")} <span aria-hidden="true">→</span></button>
        <p className="text-center text-sm text-stone-500">{pick("Already have an account?", "আগেই অ্যাকাউন্ট আছে?")} <Link href="/login" className="font-medium text-emerald-800">{pick("Log in", "লগইন করুন")}</Link></p>
      </form>
    </AuthPanel>
  );
}
