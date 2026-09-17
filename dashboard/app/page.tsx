"use client";

import Link from "next/link";
import {
  Shield,
  GitBranch,
  Menu,
  X,
  Activity,
  LogIn,
  ChevronDown,
  Server,
  LayoutDashboard,
  ArrowRight,
  Ticket,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, loginUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { LangSwitcher } from "@/components/LangSwitcher";
import { BackendStatus } from "@/components/BackendStatus";
import { MODULE_GROUPS } from "@/lib/modules";
import type { TeamMember, PublicStatus } from "@/lib/types";

function buildTree(members: TeamMember[]): Map<number | null, TeamMember[]> {
  const map = new Map<number | null, TeamMember[]>();
  for (const m of [...members].sort((a, b) => a.sort_order - b.sort_order)) {
    const key = m.parent_id ?? null;
    const list = map.get(key) ?? [];
    list.push(m);
    map.set(key, list);
  }
  return map;
}

function TeamNode({
  member,
  members,
  withStub = false,
}: {
  member: TeamMember;
  members: TeamMember[];
  withStub?: boolean;
}) {
  const tree = buildTree(members);
  const children = tree.get(member.id) ?? [];
  return (
    <li className="flex flex-col items-center">
      {withStub && <div className="h-6 w-px bg-blurple/40" />}
      <div className="rounded-xl border border-blurple/40 bg-discord px-5 py-3 text-center shadow-lg">
        <div className="text-sm font-semibold text-white">{member.name}</div>
        <div className="mt-0.5 text-xs text-blurple">{member.role}</div>
      </div>
      {children.length > 0 && (
        <>
          <div className="h-6 w-px bg-blurple/40" />
          <div className="relative w-full">
            <div className="absolute left-0 right-0 top-0 h-px bg-blurple/40" />
            <ul className="flex items-start justify-center gap-6 px-6">
              {children.map((c) => (
                <TeamNode key={c.id} member={c} members={members} withStub />
              ))}
            </ul>
          </div>
        </>
      )}
    </li>
  );
}

export default function LandingPage() {
  const { t } = useI18n();
  const [url, setUrl] = useState<string>("");
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [status, setStatus] = useState<PublicStatus | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loginUrl().then(setUrl).catch(() => setUrl(""));
    api<TeamMember[]>("/api/team").then(setTeam).catch(() => {});

    let cancelled = false;
    const load = () =>
      api<PublicStatus>("/api/status")
        .then((s) => {
          if (!cancelled) setStatus(s);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  const roots = buildTree(team).get(null) ?? [];
  const allOperational =
    status != null &&
    status.status.database === "connected" &&
    status.status.bot === "online" &&
    !Object.values(status.downtime ?? {}).some(
      (d) => d.down_since != null,
    );

  const menuItems = [
    {
      href: "#moduls",
      icon: LayoutDashboard,
      label: t("landing.modules"),
      onClick: () => setMenuOpen(false),
    },
    {
      href: "#team",
      icon: GitBranch,
      label: t("landing.team"),
      onClick: () => setMenuOpen(false),
    },
    {
      href: "/status",
      icon: Activity,
      label: t("landing.status"),
      onClick: () => setMenuOpen(false),
    },
    {
      href: "/tickets",
      icon: Ticket,
      label: t("webticket.navLabel"),
      onClick: () => setMenuOpen(false),
    },
  ];

  return (
    <main className="min-h-screen bg-gradient-to-b from-discord-darker via-discord to-blurple/20">
      {/* Nav */}
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 text-xl font-bold text-white">
          <Shield className="h-7 w-7 text-blurple" />
          WordLock
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/status"
            className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-gray-300 transition hover:bg-white/10 sm:inline-flex"
          >
            <span
              className={`h-2 w-2 rounded-full ${allOperational ? "bg-wordlock-green" : "bg-wordlock-yellow"}`}
            />
            {allOperational ? t("landing.allGood") : t("landing.status")}
          </a>
          <LangSwitcher />
          {url ? (
            <a href={url} className="btn-primary hidden sm:inline-flex">
              {t("landing.login")}
            </a>
          ) : (
            <span className="btn-primary hidden opacity-60 sm:inline-flex">
              {t("landing.connecting")}
            </span>
          )}
          <button
            onClick={() => setNavOpen((v) => !v)}
            aria-label={navOpen ? t("landing.closeMenu") : t("landing.openMenu")}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-gray-200 transition hover:bg-white/10 sm:hidden"
          >
            {navOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {/* Mobile nav */}
      {navOpen && (
        <div className="mx-6 mb-2 flex flex-col gap-2 rounded-2xl border border-white/10 bg-discord p-3 sm:hidden">
          {menuItems.map(({ href, icon: Icon, label, onClick }) => (
            <Link
              key={href}
              href={href}
              onClick={() => {
                onClick?.();
                setNavOpen(false);
              }}
              className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-gray-200 transition hover:bg-white/5"
            >
              <Icon className="h-4 w-4 text-blurple" />
              {label}
            </Link>
          ))}
          {url ? (
            <a
              href={url}
              className="mt-1 flex items-center justify-center gap-2 rounded-xl bg-blurple px-4 py-3 text-sm font-semibold text-white"
            >
              <LogIn className="h-4 w-4" />
              {t("landing.login")}
            </a>
          ) : (
            <span className="mt-1 rounded-xl bg-blurple/50 px-4 py-3 text-center text-sm font-semibold text-white/70">
              {t("landing.connecting")}
            </span>
          )}
        </div>
      )}

      {/* Backend status */}
      <div className="mx-auto max-w-6xl px-6">
        <BackendStatus />
      </div>

      {/* Hero */}
      <section className="mx-auto max-w-4xl px-6 pb-24 pt-16 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl">
          {t("landing.hero1")}{" "}
          <span className="bg-gradient-to-r from-blurple to-wordlock-pink bg-clip-text text-transparent">
            {t("landing.hero2")}
          </span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-300">{t("landing.tagline")}</p>

        {/* Modern dropdown menu */}
        <div className="relative mx-auto mt-10 inline-block" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="group inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-8 py-4 text-base font-semibold text-white shadow-lg backdrop-blur transition hover:bg-white/10"
          >
            <Menu className="h-5 w-5 text-blurple transition group-hover:rotate-90" />
            {t("landing.menu")}
            <ChevronDown
              className={`h-4 w-4 text-gray-400 transition-transform duration-300 ${menuOpen ? "rotate-180" : ""}`}
            />
          </button>

          {menuOpen && (
            <div className="absolute left-1/2 top-full z-40 mt-3 w-72 -translate-x-1/2 overflow-hidden rounded-2xl border border-white/10 bg-discord/95 shadow-2xl backdrop-blur-xl sm:w-80">
              <div className="border-b border-white/5 px-5 py-4 text-left">
                <div className="text-sm font-semibold text-white">{t("landing.menuTitle")}</div>
                <div className="mt-0.5 text-xs text-gray-500">{t("landing.menuSubtitle")}</div>
              </div>
              <div className="p-2">
                {menuItems.map(({ href, icon: Icon, label, onClick }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={onClick}
                    className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-gray-200 transition hover:bg-white/5"
                  >
                    <Icon className="h-4 w-4 text-blurple" />
                    {label}
                  </Link>
                ))}
                {url ? (
                  <a
                    href={url}
                    className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-blurple px-4 py-3 text-sm font-semibold text-white transition hover:bg-blurple/80"
                  >
                    <LogIn className="h-4 w-4" />
                    {t("landing.login")}
                  </a>
                ) : (
                  <span className="mt-2 flex items-center justify-center gap-2 rounded-xl bg-blurple/50 px-4 py-3 text-sm font-semibold text-white/70">
                    {t("landing.connecting")}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {status?.stats && (
          <div className="mt-6 flex items-center justify-center gap-2 text-sm text-gray-300">
            <Server className="h-4 w-4 text-blurple" />
            <span>{t("landing.serverCount", { n: String(status.stats.servers) })}</span>
          </div>
        )}
        <div className="mt-8 text-xs text-gray-500">{t("landing.securityNote")}</div>
      </section>

      {/* Modules */}
      <section id="moduls" className="mx-auto max-w-6xl px-6 pb-24">
        <div className="mb-12 text-center">
          <h2 className="text-3xl font-bold text-white">{t("landing.modulesTitle")}</h2>
          <p className="mt-2 text-sm text-gray-400">{t("landing.modulesSubtitle")}</p>
        </div>
        <div className="space-y-12">
          {MODULE_GROUPS.map((group) => (
            <div key={group.id}>
              <div className="mb-4 flex items-center gap-2">
                <group.icon className="h-5 w-5 text-blurple" />
                <h3 className="text-xl font-semibold text-white">{t(group.titleKey)}</h3>
              </div>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {group.modules.map((mod) => (
                  <div key={mod.id} className="card relative">
                    <mod.icon className="h-8 w-8 text-blurple" />
                    <h4 className="mt-4 text-lg font-semibold text-white">{t(mod.titleKey)}</h4>
                    <p className="mt-2 text-sm text-gray-400">{t(mod.descKey)}</p>
                    {mod.isNew && (
                      <span className="absolute right-3 top-3 rounded-full bg-wordlock-green/15 px-2 py-0.5 text-[10px] font-semibold text-wordlock-green">
                        {t("landing.newBadge")}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Dashboard promo */}
        <div className="mt-12">
          <Link
            href="/dashboard"
            className="card flex flex-wrap items-center justify-between gap-4 transition hover:border-blurple/40"
          >
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blurple/10 text-blurple">
                <LayoutDashboard className="h-6 w-6" />
              </div>
              <div>
                <div className="font-semibold text-white">{t("landing.modulesTitle")}</div>
                <div className="text-sm text-gray-400">{t("landing.dashboardCta")}</div>
              </div>
            </div>
            <span className="flex items-center gap-1 text-sm font-semibold text-blurple">
              {t("landing.dashboardCta")}
              <ArrowRight className="h-4 w-4" />
            </span>
          </Link>
        </div>
      </section>

      {/* Team */}
      <section id="team" className="mx-auto max-w-6xl px-6 pb-24">
        <div className="mb-10 text-center">
          <GitBranch className="mx-auto h-8 w-8 text-blurple" />
          <h2 className="mt-4 text-3xl font-bold text-white">{t("landing.teamTitle")}</h2>
          <p className="mt-2 text-sm text-gray-400">{t("landing.teamSubtitle")}</p>
        </div>
        {team.length === 0 ? (
          <p className="py-12 text-center text-gray-500">{t("landing.teamEmpty")}</p>
        ) : (
          <ul className="flex flex-wrap justify-center gap-8">
            {roots.map((m) => (
              <TeamNode key={m.id} member={m} members={team} />
            ))}
          </ul>
        )}
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 text-center text-sm text-gray-500">
        <p>
          WordLock • {t("landing.footer")} • {t("landing.footerVersion")}
        </p>
        <p className="mt-2">{t("landing.copyright")}</p>
        <nav className="mt-4 flex justify-center gap-6">
          <Link href="/impressum" className="transition-colors hover:text-gray-300">
            {t("landing.impressum")}
          </Link>
          <Link href="/datenschutz" className="transition-colors hover:text-gray-300">
            {t("landing.datenschutz")}
          </Link>
          <Link href="/status" className="transition-colors hover:text-gray-300">
            {t("landing.status")}
          </Link>
          <Link href="#moduls" className="transition-colors hover:text-gray-300">
            {t("landing.modules")}
          </Link>
        </nav>
      </footer>
    </main>
  );
}
