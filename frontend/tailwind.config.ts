import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        forest: "#163b32",
        mint: "#d7f1d9",
        paper: "#f7f9f6",
        ink: "#17352f",
        line: "#dce5dd"
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans Bengali", "Segoe UI", "sans-serif"]
      }
    }
  },
  plugins: []
} satisfies Config;
