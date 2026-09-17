import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import { LangSwitcher } from "@/components/LangSwitcher";
import { PushNotifications } from "@/components/PushNotifications";

export interface SidebarItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export function Sidebar({
  items,
  title,
  subtitle,
  open,
  onClose,
  extra,
}: {
  items: SidebarItem[];
  title: string;
  subtitle?: string;
  open?: boolean;
  onClose?: () => void;
  extra?: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();

  const logout = async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch {
      /* ignore */
    }
    router.push("/");
    router.refresh();
  };

  const content = (
    <>
      <div className="flex items-center gap-2 px-5 py-5">
        <Shield className="h-8 w-8 text-blurple" />
        <div>
          <div className="text-sm font-bold text-white">WordLock</div>
          <div className="text-[11px] text-gray-500">{title}</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {items.map((item) => {
          const active =
            (pathname ?? "") === item.href || (pathname ?? "").startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                active
                  ? "bg-blurple/20 text-white"
                  : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {subtitle && (
        <div className="mx-4 mb-2 truncate rounded-lg bg-white/5 px-3 py-2 text-xs text-gray-400">
          {subtitle}
        </div>
      )}

      <div className="space-y-1 border-t border-white/5 p-3">
        <div className="flex justify-end">
          <LangSwitcher />
        </div>
        <PushNotifications />
        {extra}
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-400 transition hover:bg-white/5 hover:text-red-400"
        >
          <LogOut className="h-4 w-4" />
          {t("common.logout")}
        </button>
      </div>
    </>
  );

  return (
    <>
      <aside className="hidden h-screen w-64 flex-col border-r border-white/5 bg-discord-dark lg:flex">
        {content}
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={onClose} />
          <aside className="absolute left-0 top-0 flex h-full w-64 flex-col border-r border-white/5 bg-discord-dark">
            {content}
          </aside>
        </div>
      )}
    </>
  );
}
