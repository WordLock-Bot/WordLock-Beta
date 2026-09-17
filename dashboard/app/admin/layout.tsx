"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  Server,
  BarChart3,
  Rocket,
  FileText,
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  UserCog,
  Users,
  Menu,
  Send,
  Loader2,
  MessageSquare,
  BadgeCheck,
  History,
} from "lucide-react";
import { Sidebar, type SidebarItem } from "@/components/Sidebar";
import { api, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";
import { useI18n } from "@/lib/i18n";
import { BackendStatus } from "@/components/BackendStatus";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { t } = useI18n();
  const [role, setRole] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMsg, setPushMsg] = useState<string | null>(null);

  const items: SidebarItem[] = [
    { href: "/admin", label: t("admin.overview"), icon: LayoutDashboard },
    { href: "/admin/servers", label: t("admin.servers"), icon: Server },
    { href: "/admin/stats", label: t("admin.stats"), icon: BarChart3 },
    { href: "/admin/incidents", label: t("admin.incidents"), icon: ShieldAlert },
    { href: "/admin/security", label: t("admin.security"), icon: ShieldAlert },
    { href: "/admin/tickets", label: t("admin.tickets"), icon: MessageSquare },
    { href: "/admin/verify", label: t("admin.verify"), icon: BadgeCheck },
    { href: "/admin/history", label: t("admin.history"), icon: History },
    { href: "/admin/profile", label: t("admin.profile"), icon: UserCog },
    { href: "/admin/updates", label: t("admin.updates"), icon: Rocket },
    { href: "/admin/lists", label: t("admin.lists"), icon: FileText },
    { href: "/admin/team", label: t("admin.team"), icon: Users },
    { href: "/admin/logs", label: t("admin.logs"), icon: ScrollText },
  ];

  useEffect(() => {
    api<Me>("/api/auth/me")
      .then((me) => {
        setRole(me.role);
        if (!["owner", "developer", "moderator"].includes(me.role)) {
          router.replace("/dashboard");
        }
      })
      .catch((e: ApiError) => {
        if (e.status === 401) router.replace("/");
      });
  }, [router]);

  const sendTestToAll = async () => {
    setPushBusy(true);
    setPushMsg(null);
    try {
      const res = await api<{ sent: number }>("/api/admin/push/test", { method: "POST" });
      setPushMsg(t("push.testAllSent", { n: String(res.sent) }));
    } catch (e) {
      setPushMsg((e as ApiError).status === 400 ? t("push.testAllError") : t("push.testError"));
    } finally {
      setPushBusy(false);
    }
  };

  const roleBadge =
    role === "owner" ? (
      <span className="badge bg-wordlock-red/15 text-wordlock-red">
        <ShieldCheck className="h-3 w-3" /> Owner
      </span>
    ) : role === "developer" ? (
      <span className="badge bg-blurple/15 text-blurple">Developer</span>
    ) : (
      <span className="badge bg-wordlock-green/15 text-wordlock-green">Moderator</span>
    );

  const extra = (
    <div className="space-y-1">
      <button
        onClick={sendTestToAll}
        disabled={pushBusy}
        className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-400 transition hover:bg-white/5 hover:text-gray-200"
      >
        {pushBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        {t("push.testAll")}
      </button>
      {pushMsg && (
        <div className="mx-3 rounded-lg bg-wordlock-green/10 px-3 py-2 text-xs text-wordlock-green">
          {pushMsg}
        </div>
      )}
    </div>
  );

  return (
    <div className="flex min-h-screen">
      <Sidebar
        title={t("admin.sidebarTitle")}
        items={items}
        subtitle={t("admin.sidebarSubtitle")}
        open={navOpen}
        onClose={() => setNavOpen(false)}
        extra={extra}
      />
      <div className="flex-1 overflow-y-auto">
        <div className="flex items-center justify-between border-b border-white/5 bg-discord px-4 py-3 lg:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setNavOpen(true)}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-white/5 hover:text-white lg:hidden"
              aria-label={t("common.menu")}
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              {t("admin.headerLabel")}
            </span>
          </div>
          {roleBadge}
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
