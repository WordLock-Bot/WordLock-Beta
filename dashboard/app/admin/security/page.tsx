"use client";

import { useEffect, useState } from "react";
import { ShieldAlert, UserCog, Users, Lock, Activity, AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AdminSecurity } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const ROLE_BADGES: Record<string, string> = {
  owner: "bg-wordlock-red/15 text-wordlock-red",
  developer: "bg-blurple/15 text-blurple",
  moderator: "bg-wordlock-green/15 text-wordlock-green",
};

export default function AdminSecurityPage() {
  const { t, locale } = useI18n();
  const [data, setData] = useState<AdminSecurity | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AdminSecurity>("/api/admin/security")
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="flex items-center gap-2 rounded-lg bg-wordlock-red/15 px-4 py-3 text-sm text-red-300">
        <AlertTriangle className="h-4 w-4" />
        {error}
      </div>
    );
  }

  if (!data) return <p className="text-gray-400">{t("common.loading")}</p>;

  const fmt = (d: string) =>
    new Date(d).toLocaleString(locale, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

  return (
    <div className="space-y-8">
      <header>
        <h1 className="flex items-center gap-2 text-3xl font-bold text-white">
          <ShieldAlert className="h-7 w-7 text-wordlock-red" /> {t("admin.security")}
        </h1>
        <p className="mt-1 text-sm text-gray-400">{t("admin.securitySubtitle")}</p>
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <UserCog className="h-5 w-5 text-blurple" /> {t("admin.securityStaff")}
          </h2>
          {data.staff.length === 0 ? (
            <p className="text-sm text-gray-500">{t("security.noIncidents")}</p>
          ) : (
            <ul className="space-y-2">
              {data.staff.map((u) => (
                <li
                  key={u.discord_id}
                  className="flex items-center justify-between gap-4 rounded-lg bg-white/5 px-4 py-2.5 text-sm"
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <Users className="h-4 w-4 shrink-0 text-gray-500" />
                    <span className="truncate font-mono text-xs text-gray-200">{u.discord_id}</span>
                  </div>
                  <span className={`badge ${ROLE_BADGES[u.role] ?? "bg-white/10 text-gray-300"}`}>
                    {u.role}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="mb-2 mt-6 text-sm font-semibold text-gray-300">{t("admin.securityWhitelist")}</h3>
          {data.whitelist_ids.length === 0 ? (
            <p className="text-xs text-gray-500">—</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {data.whitelist_ids.map((id) => (
                <span
                  key={id}
                  className="rounded-full bg-white/5 px-3 py-1 font-mono text-xs text-gray-200"
                >
                  {id}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
            <Activity className="h-5 w-5 text-blurple" /> {t("admin.securityServices")}
          </h2>
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-lg bg-white/5 px-4 py-2.5 text-sm">
              <span className="flex items-center gap-2 text-gray-300">
                <Lock className="h-4 w-4 text-gray-500" /> {t("adminOv.maintenance")}
              </span>
              <span
                className={`badge ${
                  data.maintenance_mode
                    ? "bg-wordlock-yellow/15 text-wordlock-yellow"
                    : "bg-wordlock-green/15 text-wordlock-green"
                }`}
              >
                {data.maintenance_mode ? t("common.enabled") : t("common.disabled")}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-white/5 px-4 py-2.5 text-sm">
              <span className="text-gray-300">{t("admin.securityPushSubs")}</span>
              <span className="text-lg font-bold text-white">{data.push_subscribers}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
          <AlertTriangle className="h-5 w-5 text-wordlock-red" /> {t("admin.securityIncidents")}
        </h2>
        {data.incidents.length === 0 ? (
          <p className="py-4 text-center text-sm text-gray-500">{t("security.noIncidents")}</p>
        ) : (
          <ul className="space-y-2">
            {data.incidents.map((inc) => (
              <li
                key={inc.id}
                className="flex flex-wrap items-center gap-2 rounded-lg bg-white/5 px-4 py-2.5 text-sm"
              >
                <span
                  className={`badge ${
                    inc.status === "open"
                      ? "bg-wordlock-red/15 text-wordlock-red"
                      : "bg-wordlock-green/15 text-wordlock-green"
                  }`}
                >
                  {inc.status === "open" ? t("security.open") : t("security.resolved")}
                </span>
                <span className="min-w-0 text-gray-200">
                  {t(`security.kind.${inc.kind}`) === `security.kind.${inc.kind}`
                    ? inc.kind
                    : t(`security.kind.${inc.kind}`)}
                </span>
                <span className="text-xs text-gray-400">
                  {t("adServDetail.severity")}: {inc.severity}
                </span>
                <span className="ml-auto shrink-0 text-xs text-gray-500">
                  #{inc.id} • {fmt(inc.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}