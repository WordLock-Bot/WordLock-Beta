"use client";

import {
  MessageSquareWarning,
  Languages,
  ShieldBan,
  ShieldAlert,
  Link2,
  Gauge,
  ScrollText,
  BadgeCheck,
  Ticket,
  Users,
  UserPlus,
  CalendarClock,
  Megaphone,
  LayoutDashboard,
  Activity,
  Shield,
  type LucideIcon,
} from "lucide-react";

export interface ModuleInfo {
  id: string;
  icon: LucideIcon;
  titleKey: string;
  descKey: string;
  isNew?: boolean;
}

export interface ModuleGroup {
  id: string;
  titleKey: string;
  icon: LucideIcon;
  modules: ModuleInfo[];
}

export const MODULE_GROUPS: ModuleGroup[] = [
  {
    id: "filter",
    titleKey: "modGroups.filter",
    icon: Shield,
    modules: [
      { id: "wortfilter", icon: MessageSquareWarning, titleKey: "mod.wortfilter.title", descKey: "mod.wortfilter.desc" },
      { id: "serverwords", icon: Languages, titleKey: "mod.serverwords.title", descKey: "mod.serverwords.desc" },
      { id: "antispam", icon: ShieldBan, titleKey: "mod.antispam.title", descKey: "mod.antispam.desc", isNew: true },
      { id: "antinuke", icon: ShieldAlert, titleKey: "mod.antinuke.title", descKey: "mod.antinuke.desc", isNew: true },
      { id: "phishing", icon: Link2, titleKey: "mod.phishing.title", descKey: "mod.phishing.desc", isNew: true },
    ],
  },
  {
    id: "moderation",
    titleKey: "modGroups.moderation",
    icon: Gauge,
    modules: [
      { id: "levels", icon: Gauge, titleKey: "mod.levels.title", descKey: "mod.levels.desc" },
      { id: "incidents", icon: Shield, titleKey: "mod.incidents.title", descKey: "mod.incidents.desc" },
      { id: "logs", icon: ScrollText, titleKey: "mod.logs.title", descKey: "mod.logs.desc" },
      { id: "verify", icon: BadgeCheck, titleKey: "mod.verify.title", descKey: "mod.verify.desc", isNew: true },
      { id: "tickets", icon: Ticket, titleKey: "mod.tickets.title", descKey: "mod.tickets.desc", isNew: true },
    ],
  },
  {
    id: "community",
    titleKey: "modGroups.community",
    icon: Users,
    modules: [
      { id: "welcome", icon: Users, titleKey: "mod.welcome.title", descKey: "mod.welcome.desc", isNew: true },
      { id: "invites", icon: UserPlus, titleKey: "mod.invites.title", descKey: "mod.invites.desc", isNew: true },
      { id: "scheduled", icon: CalendarClock, titleKey: "mod.scheduled.title", descKey: "mod.scheduled.desc", isNew: true },
      { id: "updates", icon: Megaphone, titleKey: "mod.updates.title", descKey: "mod.updates.desc" },
    ],
  },
  {
    id: "platform",
    titleKey: "modGroups.platform",
    icon: LayoutDashboard,
    modules: [
      { id: "dashboard", icon: LayoutDashboard, titleKey: "mod.dashboard.title", descKey: "mod.dashboard.desc" },
      { id: "status", icon: Activity, titleKey: "mod.status.title", descKey: "mod.status.desc" },
    ],
  },
];
