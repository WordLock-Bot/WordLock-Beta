"use client";

import Link from "next/link";
import {
  Activity,
  Bot,
  Database,
  Gauge,
  Server,
  Shield,
  Users,
  Zap,
  ArrowLeft,
  AlertTriangle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { LangSwitcher } from "@/components/LangSwitcher";
import type { PublicStatus } from "@/lib/types";

const POLL_MS = 5000;
const HISTORY_MAX = 60;
const LOCAL_KEY = "wordlock.localSince";

function readLocalSince(): Record<string, number> {
  try {
    const raw = window.sessionStorage.getItem(LOCAL_KEY);
    if (raw) return JSON.parse(raw) as Record<string, number>;
  } catch {
    /* ignore */
  }
  return {};
}

type ServiceKey = "api" | "database" | "bot";

function useCountUp(target: number, duration = 800) {
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);

  useEffect(() => {
    const from = fromRef.current;
    if (from === target) return;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(from + (target - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      fromRef.current = target;
    };
  }, [target, duration]);

  return value;
}

function formatUptime(seconds: number): string {
  const s = Math.floor(seconds);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");
  if (d > 0) return `${d}d ${pad(h)}h ${pad(m)}m`;
  if (h > 0) return `${pad(h)}h ${pad(m)}m ${pad(sec)}s`;
  return `${pad(m)}m ${pad(sec)}s`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return n.toString();
}

export default function StatusPage() {
  const { t } = useI18n();
  const [data, setData] = useState<PublicStatus | null>(null);
  const [online, setOnline] = useState<boolean>(true);
  const [latency, setLatency] = useState<number | null>(null);
  const [history, setHistory] = useState<number[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const [localSince, setLocalSince] = useState<Record<string, number>>(readLocalSince);
  const historyRef = useRef<number[]>([]);

  const tick = useCallback(() => setNow(Date.now()), []);
  useEffect(() => {
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [tick]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(LOCAL_KEY, JSON.stringify(localSince));
    } catch {
      /* ignore */
    }
  }, [localSince]);

  const isServiceOk = useCallback(
    (key: ServiceKey, body: PublicStatus | null) => {
      if (!body) return false;
      if (key === "database") return body.status.database === "connected";
      return body.status[key] === "online";
    },
    [],
  );

  const serverSince = useMemo(() => {
    const out: Record<string, number> = {};
    for (const key of ["api", "database", "bot"] as ServiceKey[]) {
      const iso = data?.downtime?.[key]?.down_since;
      if (iso) {
        const ts = new Date(iso).getTime();
        if (!Number.isNaN(ts)) out[key] = ts;
      }
    }
    return out;
  }, [data]);

  const downSinceFor = (key: ServiceKey): number | null =>
    serverSince[key] ?? localSince[key] ?? null;

  const fetchStatus = useCallback(async () => {
    const start = performance.now();
    let body: PublicStatus | null = null;
    try {
      const res = await fetch("/api/status", { cache: "no-store" });
      const elapsed = Math.round(performance.now() - start);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      body = await res.json();
      setData(body);
      setLatency(elapsed);
    } catch {
      body = null;
    }
    const allOk = body
      ? ["api", "database", "bot"].every((k) => isServiceOk(k as ServiceKey, body))
      : false;
    setOnline(allOk);
    const arr = [...historyRef.current, allOk ? 1 : 0].slice(-HISTORY_MAX);
    historyRef.current = arr;
    setHistory(arr);
    setLocalSince((prev) => {
      const next: Record<string, number> = { ...prev };
      for (const key of ["api", "database", "bot"] as ServiceKey[]) {
        const ok = isServiceOk(key, body);
        const hasServer = body?.downtime?.[key]?.down_since != null;
        if (ok || hasServer) delete next[key];
        else if (!next[key]) next[key] = Date.now();
      }
      return next;
    });
  }, [isServiceOk]);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const startedAt = useMemo(
    () => (data?.started_at ? new Date(data.started_at) : null),
    [data],
  );
  const uptimeSec = startedAt
    ? Math.max(0, (now - startedAt.getTime()) / 1000)
    : null;

  const services: { key: ServiceKey; label: string; icon: typeof Bot }[] = [
    { key: "api", label: t("status.service.api"), icon: Zap },
    { key: "database", label: t("status.service.database"), icon: Database },
    { key: "bot", label: t("status.service.bot"), icon: Bot },
  ];

  const uptimePercent = history.length
    ? Math.round((history.filter(Boolean).length / history.length) * 100)
    : 100;

  const statusDot = (key: ServiceKey) => isServiceOk(key, data);

  const activeServers = useCountUp(data?.stats.active_servers ?? 0);
  const activeUsers = useCountUp(data?.stats.active_users ?? 0);
  const violationsToday = useCountUp(data?.stats.violations_today ?? 0);
  const violationsTotal = useCountUp(data?.stats.violations_total ?? 0);

  return (
    <main className="min-h-screen bg-gradient-to-b from-discord-darker via-discord to-blurple/20">
      <nav className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-white">
          <Shield className="h-6 w-6 text-blurple" />
          WordLock
        </Link>
        <div className="flex items-center gap-3">
          <LangSwitcher />
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 text-sm font-medium text-gray-200 transition hover:bg-white/10"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t("status.back")}</span>
          </Link>
        </div>
      </nav>

      <div className="mx-auto max-w-5xl px-6 pb-24 pt-6">
        {/* Header */}
        <div className="mb-10 text-center">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm font-medium backdrop-blur">
            <span
              className={`relative flex h-2.5 w-2.5 rounded-full ${
                online ? "bg-wordlock-green" : "bg-wordlock-red"
              }`}
            >
              <span
                className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${
                  online ? "bg-wordlock-green" : "bg-wordlock-red"
                }`}
              />
            </span>
            {online ? t("status.allOperational") : t("status.issuesDetected")}
            <span className="text-gray-500">
              {latency !== null ? `${latency}ms` : "–"}
            </span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-5xl">
            {t("status.title")}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-gray-400">{t("status.subtitle")}</p>
        </div>

        {data?.maintenance && (
          <div className="mb-8 flex items-center justify-center gap-2 rounded-xl border border-wordlock-yellow/40 bg-wordlock-yellow/10 px-4 py-3 text-sm text-wordlock-yellow">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {t("status.maintenance")}
          </div>
        )}

        {/* Service status */}
        <div className="grid gap-4 sm:grid-cols-3">
          {services.map(({ key, label, icon: Icon }) => {
            const ok = statusDot(key);
            return (
              <div key={key} className="card flex items-center gap-4">
                <div
                  className={`flex h-11 w-11 items-center justify-center rounded-xl ${
                    ok ? "bg-wordlock-green/10 text-wordlock-green" : "bg-wordlock-red/10 text-wordlock-red"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-gray-300">{label}</div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className={`h-2 w-2 rounded-full ${ok ? "bg-wordlock-green" : "bg-wordlock-red"}`} />
                    {ok ? (
                      <span className="text-wordlock-green">{t("status.operational")}</span>
                    ) : (
                      <span className="text-wordlock-red">
                        {t("status.serviceDown", {
                          service: label,
                          time: formatUptime((now - (downSinceFor(key) ?? now)) / 1000),
                        })}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Uptime sparkline + latency */}
        <div className="card mt-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blurple" />
              <span className="text-sm font-semibold text-white">{t("status.liveHealth")}</span>
            </div>
            <div className="flex items-center gap-4 text-xs text-gray-400">
              <span>
                {t("status.uptime")}: <span className="font-semibold text-wordlock-green">{uptimePercent}%</span>
              </span>
              <span>
                {t("status.uptimeSince")}:{" "}
                <span className="font-semibold text-white">
                  {uptimeSec !== null ? formatUptime(uptimeSec) : "–"}
                </span>
              </span>
            </div>
          </div>
          <div className="mt-4 flex h-16 items-end gap-[3px]">
            {history.length === 0 &&
              Array.from({ length: 60 }).map((_, i) => (
                <div key={i} className="h-1/2 flex-1 rounded-sm bg-white/5" />
              ))}
            {history.map((v, i) => (
              <div
                key={i}
                style={{ height: v ? "100%" : "18%" }}
                className={`flex-1 rounded-sm transition-all duration-500 ${
                  v ? "bg-wordlock-green/80" : "bg-wordlock-red/80"
                }`}
              />
            ))}
          </div>
          <p className="mt-2 text-xs text-gray-500">{t("status.liveHealthHint")}</p>
        </div>

        {/* Stats */}
        <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="card flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blurple/10 text-blurple">
              <Server className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{formatNumber(activeServers)}</div>
              <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
                {t("status.stats.servers")}
              </div>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wordlock-green/10 text-wordlock-green">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{formatNumber(activeUsers)}</div>
              <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
                {t("status.stats.users")}
              </div>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wordlock-yellow/10 text-wordlock-yellow">
              <Gauge className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{formatNumber(violationsToday)}</div>
              <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
                {t("status.stats.today")}
              </div>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-wordlock-red/10 text-wordlock-red">
              <Zap className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-bold text-white">{formatNumber(violationsTotal)}</div>
              <div className="text-xs font-medium uppercase tracking-wider text-gray-400">
                {t("status.stats.total")}
              </div>
            </div>
          </div>
        </div>

        {/* Footer meta */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-center text-xs text-gray-500">
          <span>
            {t("status.version")} <span className="text-gray-300">{data?.version ?? "–"}</span>
          </span>
          <span className="hidden sm:inline">•</span>
          <span>
            {t("status.startedAt")}{" "}
            <span className="text-gray-300">
              {startedAt ? startedAt.toLocaleString() : "–"}
            </span>
          </span>
        </div>

        <p className="mt-10 text-center text-xs text-gray-600">
          WordLock • {t("status.footer")}
        </p>
      </div>
    </main>
  );
}
