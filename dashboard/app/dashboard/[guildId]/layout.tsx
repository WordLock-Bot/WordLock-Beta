"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { LayoutDashboard, Filter, Settings, ArrowLeft, ShieldAlert, Menu, UserPlus, CalendarClock, Users, Ticket } from "lucide-react";
import Link from "next/link";
import { Sidebar, type SidebarItem } from "@/components/Sidebar";
import { useI18n } from "@/lib/i18n";
import { BackendStatus } from "@/components/BackendStatus";

export default function GuildLayout({ children }: { children: React.ReactNode }) {
  const params = useParams();
  const { t } = useI18n();
  const [navOpen, setNavOpen] = useState(false);
  const guildId = (params?.guildId as string) ?? "";
  const base = `/dashboard/${guildId}`;

  const items: SidebarItem[] = [
    { href: base, label: t("nav.overview"), icon: LayoutDashboard },
    { href: `${base}/filters`, label: t("nav.filters"), icon: Filter },
    { href: `${base}/settings`, label: t("nav.settings"), icon: Settings },
    { href: `${base}/security`, label: t("nav.security"), icon: ShieldAlert },
    { href: `${base}/invites`, label: t("nav.invites"), icon: UserPlus },
    { href: `${base}/panel`, label: t("nav.panel"), icon: Users },
    { href: `${base}/scheduled`, label: t("nav.scheduled"), icon: CalendarClock },
    { href: `${base}/tickets`, label: t("nav.tickets"), icon: Ticket },
  ];

  return (
    <div className="flex min-h-screen">
      <Sidebar title={t("guild.sidebarTitle")} items={items} open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex-1 overflow-y-auto">
        <div className="flex items-center gap-3 border-b border-white/5 bg-discord px-4 py-3 lg:px-6">
          <button
            onClick={() => setNavOpen(true)}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-white/5 hover:text-white lg:hidden"
            aria-label={t("common.menu")}
          >
            <Menu className="h-5 w-5" />
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-white"
          >
            <ArrowLeft className="h-3 w-3" /> {t("guild.allServers")}
          </Link>
        </div>
        <div className="p-4 lg:p-10">
          <div className="mb-6">
            <BackendStatus />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
