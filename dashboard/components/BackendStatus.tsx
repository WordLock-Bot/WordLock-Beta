"use client";

import { useEffect, useState } from "react";
import { Loader2, WifiOff } from "lucide-react";
import { useI18n } from "@/lib/i18n";

const POLL_MS = 15000;

export function BackendStatus() {
  const { t } = useI18n();
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        if (!cancelled) setUnreachable(!res.ok);
      } catch {
        if (!cancelled) setUnreachable(true);
      }
    };

    check();
    const id = setInterval(check, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!unreachable) return null;

  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-3 border-b border-wordlock-yellow/40 bg-wordlock-yellow/15 px-4 py-3 text-sm text-wordlock-yellow backdrop-blur">
      <WifiOff className="h-5 w-5 shrink-0" />
      <div className="text-center">
        <span className="font-semibold">{t("backend.unreachable")}</span>{" "}
        <span className="inline-flex items-center gap-1.5 text-wordlock-yellow/90">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          {t("backend.restarting")}
        </span>
      </div>
    </div>
  );
}
