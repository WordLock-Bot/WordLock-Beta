"use client";

import { Languages } from "lucide-react";
import { useI18n, type Lang } from "@/lib/i18n";

const LANGS: { code: Lang; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "de", label: "DE" },
];

export function LangSwitcher() {
  const { lang, setLang } = useI18n();
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 py-1 pl-2.5 pr-1 backdrop-blur">
      <Languages className="h-3.5 w-3.5 text-gray-400" />
      <div className="flex rounded-full bg-discord-dark/60 p-0.5">
        {LANGS.map(({ code, label }) => {
          const active = lang === code;
          return (
            <button
              key={code}
              onClick={() => setLang(code)}
              aria-label={`${code.toUpperCase()} - ${code === "en" ? "English" : "Deutsch"}`}
              className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide transition-all ${
                active
                  ? "bg-blurple text-white shadow-sm"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
