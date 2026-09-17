"use client";

import { useEffect, useState } from "react";
import { BadgeCheck, Lock, ShieldCheck, Clock, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import type { VerifyOverview } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { useI18n } from "@/lib/i18n";

export default function AdminVerify() {
  const { t } = useI18n();
  const [data, setData] = useState<VerifyOverview | null>(null);

  useEffect(() => {
    api<VerifyOverview>("/api/admin/verify").then(setData).catch(() => setData(null));
  }, []);

  if (!data) return <p className="text-gray-400">{t("adVerify.loading")}</p>;

  const fmt = (d: string) =>
    new Date(d).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("adVerify.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("adVerify.subtitle")}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label={t("adVerify.verifiedTotal")} value={data.total} icon={CheckCircle2} tone="green" />
        <StatCard label={t("adVerify.verifiedToday")} value={data.today} icon={ShieldCheck} tone="default" />
        <StatCard label={t("adVerify.verified7d")} value={data.last_7d} icon={BadgeCheck} tone="yellow" />
        <StatCard label={t("adVerify.verified30d")} value={data.last_30d} icon={BadgeCheck} tone="default" />
        <StatCard label={t("adVerify.locked")} value={data.locked} icon={Lock} tone="red" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 text-lg font-semibold text-white">{t("adVerify.perGuild")}</h2>
          {data.per_guild.length === 0 ? (
            <p className="text-sm text-gray-500">{t("adVerify.noData")}</p>
          ) : (
            <ul className="space-y-3">
              {data.per_guild.map((g) => (
                <li
                  key={g.guild_id}
                  className="flex items-center justify-between gap-4 rounded-lg bg-white/5 px-4 py-2.5 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-gray-200">
                      {g.guild_name || `${t("adVerify.unknownGuild")} (${g.guild_id})`}
                    </p>
                    <p className="font-mono text-xs text-gray-500">{g.guild_id}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3 text-xs">
                    <span className="text-wordlock-green">{g.verified} ✓</span>
                    <span className="text-wordlock-red">{g.locked} 🔒</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Clock className="h-4 w-4 text-blurple" /> {t("adVerify.recent")}
          </h2>
          {data.recent.length === 0 ? (
            <p className="text-sm text-gray-500">{t("adVerify.noData")}</p>
          ) : (
            <ul className="space-y-2">
              {data.recent.map((e) => (
                <li
                  key={e.id}
                  className="flex items-center justify-between gap-4 rounded-lg bg-white/5 px-4 py-2.5 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate text-gray-200">
                      {e.action === "lock" ? "🔒" : "✅"}{" "}
                      <span className="font-mono text-xs text-gray-400">{e.user_id}</span>
                    </p>
                    <p className="truncate text-xs text-gray-500">
                      {e.guild_name || `${t("adVerify.unknownGuild")} (${e.guild_id})`}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        e.action === "lock"
                          ? "bg-wordlock-red/15 text-wordlock-red"
                          : "bg-wordlock-green/15 text-wordlock-green"
                      }`}
                    >
                      {e.action === "lock" ? t("adVerify.actionLock") : t("adVerify.actionVerified")}
                    </span>
                    <span className="text-xs text-gray-500">{fmt(e.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}