"use client";

import { useEffect, useState } from "react";
import { ScrollText, Bug, Server, Database, Info } from "lucide-react";
import { api } from "@/lib/api";
import type { LogEntry } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const LEVEL_TONES: Record<string, string> = {
  info: "bg-blurple/15 text-blurple",
  warning: "bg-wordlock-yellow/15 text-wordlock-yellow",
  error: "bg-wordlock-red/15 text-wordlock-red",
  critical: "bg-wordlock-pink/20 text-wordlock-pink",
};

const TYPE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  api: Server,
  discord: Server,
  database: Database,
  bot: Bug,
  admin: ScrollText,
  updates: Info,
  wordlists: Info,
};

export default function AdminLogs() {
  const { t, locale } = useI18n();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState<string>("");
  const [logType, setLogType] = useState<string>("");
  const [limit, setLimit] = useState(100);

  const reload = () => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (level) params.set("level", level);
    if (logType) params.set("log_type", logType);
    api<LogEntry[]>(`/api/admin/logs?${params}`).then(setLogs);
  };

  useEffect(reload, [level, logType, limit]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-white">{t("adLogs.title")}</h1>
        <p className="mt-1 text-sm text-gray-400">{t("adLogs.subtitle")}</p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <select className="input max-w-[160px]" value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">{t("adLogs.allLevels")}</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
          <option value="critical">critical</option>
        </select>
        <select className="input max-w-[180px]" value={logType} onChange={(e) => setLogType(e.target.value)}>
          <option value="">{t("adLogs.allTypes")}</option>
          <option value="api">api</option>
          <option value="discord">discord</option>
          <option value="database">database</option>
          <option value="bot">bot</option>
          <option value="admin">admin</option>
          <option value="updates">updates</option>
          <option value="wordlists">wordlists</option>
        </select>
        <select className="input max-w-[120px]" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          <option value={50}>50</option>
          <option value={100}>100</option>
          <option value={200}>200</option>
        </select>
      </div>

      <div className="card space-y-2">
        {logs.length === 0 && (
          <p className="py-10 text-center text-sm text-gray-500">{t("adLogs.none")}</p>
        )}
        {logs.map((l) => {
          const Icon = TYPE_ICONS[l.type] ?? Info;
          return (
            <div key={l.id} className="flex gap-3 rounded-lg bg-white/5 p-4">
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`badge ${LEVEL_TONES[l.level] ?? "bg-white/5 text-gray-400"}`}>
                    {l.level}
                  </span>
                  <span className="badge bg-white/5 text-gray-300">{l.type}</span>
                  {l.guild_id && (
                    <span className="font-mono text-[10px] text-gray-500">guild {l.guild_id}</span>
                  )}
                  <span className="ml-auto text-xs text-gray-500">
                    {new Date(l.created_at).toLocaleString(locale)}
                  </span>
                </div>
                <p className="mt-2 break-words text-sm text-gray-200">{l.message}</p>
                {l.stacktrace && (
                  <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-discord-darker p-3 font-mono text-xs text-red-300/80">
                    {l.stacktrace}
                  </pre>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
