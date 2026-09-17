export interface Guild {
  id: string;
  name: string;
  icon: string | null;
  member_count: number;
  bot_in_server: boolean;
  bot_status: string;
  bot_has_admin: boolean;
}

export interface Me {
  id: string;
  username: string;
  avatar: string | null;
  role: string;
  admin_guilds: Guild[];
  maintenance: boolean;
}

export interface AntiSpamConfig {
  rate_limit: number;
  rate_window: number;
  mention_limit: number;
  mention_window: number;
  caps_ratio: number;
  caps_min_len: number;
  link_limit: number;
  link_window: number;
  emoji_limit: number;
  emoji_window: number;
  webhook_rate_limit: number;
  webhook_window: number;
  action: "delete" | "warn" | "timeout" | "kick" | "ban";
  timeout_minutes: number;
}

export interface AntiNukeConfig {
  channel_limit: number;
  channel_window: number;
  role_limit: number;
  role_window: number;
  kick_limit: number;
  kick_window: number;
  ban_limit: number;
  ban_window: number;
  webhook_limit: number;
  webhook_window: number;
  action: "timeout" | "kick" | "ban";
}

export interface ServerConfig {
  guild_id: string;
  name: string;
  status: string;
  language: string;
  mod_level: number;
  log_channel_id: string | null;
  action_delete: boolean;
  action_warn: boolean;
  action_timeout: boolean;
  action_log: boolean;
  timeout_minutes: number;
  default_lists: Record<string, boolean>;
  bypass_roles: string[];
  bypass_users: string[];
  bypass_privileged: boolean;
  std_word_action: string;
  anti_spam_enabled: boolean;
  anti_nuke_enabled: boolean;
  anti_spam_config: AntiSpamConfig;
  anti_nuke_config: AntiNukeConfig;
  bot_version: string | null;
  member_count: number;
  welcome_channel_id: string | null;
  welcome_message: string;
  leave_channel_id: string | null;
  leave_message: string;
  phishing_enabled: boolean;
  phishing_action: "delete" | "warn" | "timeout" | "log";
  phishing_config: Record<string, unknown>;
}

export interface Word {
  id: number;
  word: string;
  category: string;
  severity: number;
  action: string;
  enabled: boolean;
}

export interface SeriesPoint {
  day: string;
  value: number;
}

export interface WordCount {
  matched_word: string;
  count: number;
}

export interface ActionCount {
  action: string;
  count: number;
}

export interface GuildStats {
  guild_id: string;
  guild_name: string;
  member_count: number;
  status: string;
  violations_today: number;
  violations_series: SeriesPoint[];
  top_words: WordCount[];
  actions: ActionCount[];
  warning_count: number;
}

export interface Update {
  id: number;
  version: string;
  title: string;
  changelog: string | null;
  maintenance_mode: boolean;
  date: string;
}

export interface LogEntry {
  id: number;
  type: string;
  level: string;
  guild_id: string | null;
  message: string;
  stacktrace: string | null;
  created_at: string;
}

export interface AdminOverview {
  servers: number;
  active_servers: number;
  active_users: number;
  violations_today: number;
  violations_total: number;
  error_count: number;
  open_tickets?: number;
  version: string;
  maintenance_mode: boolean;
  started_at: string | null;
  last_updates: Update[];
  status: { bot: string; api: string; database: string };
}

export interface MonitorStatus {
  muted: boolean;
  down_since: string | null;
  last_notified: string | null;
  api_ok: boolean;
  bot_ok: boolean;
  down: boolean;
}

export interface AdminServer {
  guild_id: string;
  name: string;
  owner_id: string | null;
  status: string;
  bot_version: string | null;
  member_count: number;
  language: string;
  mod_level: number;
  bypass_privileged: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminServerDetail extends ServerConfig {
  owner_id: string | null;
  created_at: string;
  updated_at: string;
  words: Word[];
  logs: LogEntry[];
  violations: SeriesPoint[];
  top_words: WordCount[];
  incidents: Incident[];
  violations_total: number;
}

export interface ServerChannel {
  id: string;
  name: string;
  type: number;
}

export interface AdminStats {
  violations_series: SeriesPoint[];
  server_growth: SeriesPoint[];
  action_counts: ActionCount[];
  top_words: WordCount[];
  per_guild: { guild_id: string; count: number }[];
  servers: number;
  active_users: number;
  violations_total: number;
}

export interface VerifyGuildStat {
  guild_id: string;
  guild_name: string | null;
  verified: number;
  locked: number;
}

export interface VerifyEvent {
  id: number;
  guild_id: string;
  guild_name: string | null;
  user_id: string;
  action: string;
  created_at: string;
}

export interface VerifyOverview {
  total: number;
  today: number;
  last_7d: number;
  last_30d: number;
  locked: number;
  per_guild: VerifyGuildStat[];
  recent: VerifyEvent[];
}

export interface WordListInfo {
  language: string;
  name: string;
  version: string;
  word_count: number;
}

export interface BotProfile {
  avatar: string | null;
  updated_by: string | null;
  updated_at: string | null;
}

export interface ProfileHistoryEntry {
  id: number;
  field: string;
  guild_id: string | null;
  updated_by: string | null;
  value: string | null;
  created_at: string;
}

export interface TeamMember {
  id: number;
  name: string;
  role: string;
  parent_id: number | null;
  sort_order: number;
  discord_id: number | null;
  panel_access: boolean;
  created_at: string;
  updated_at: string;
}

export interface PublicStatus {
  version: string;
  started_at: string | null;
  status: { api: string; database: string; bot: string };
  downtime: Record<string, { down_since: string | null; last_notified: string | null }>;
  stats: {
    active_servers: number;
    servers: number;
    active_users: number;
    violations_today: number;
    violations_total: number;
  };
  maintenance: boolean;
}

export interface Incident {
  id: number;
  guild_id: string;
  kind: string;
  severity: string;
  actor_id: string | null;
  detail: Record<string, unknown> | null;
  consequence: string | null;
  status: string;
  pushed: boolean;
  created_at: string;
  resolved_at: string | null;
  guild_name?: string;
}

export interface Ticket {
  id: number;
  type: string;
  subject: string;
  message: string;
  sender_name: string;
  sender_email: string;
  sender_id: string | null;
  guild_id: string | null;
  status: string;
  assigned_to: string | null;
  admin_reply: string | null;
  replied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DiscordTicket {
  id: number;
  guild_id: string;
  channel_id: string | null;
  creator_id: string;
  status: string;
  claimed_by: string | null;
  transcript_id: number | null;
  created_at: string;
  closed_at: string | null;
  closed_by: string | null;
}

export interface TicketTranscript {
  id: number;
  ticket_id: number | null;
  html: string;
  created_at: string;
}

export interface InvitePoint {
  date: string;
  n: number;
}

export interface InviteStats {
  total: number;
  recent: number;
  series: InvitePoint[];
}

export interface InviteLeaderboardEntry {
  inviter_id: number | string;
  invites: number;
}

export interface InvitesOverview {
  stats: InviteStats;
  leaderboard: InviteLeaderboardEntry[];
}

export interface AdminInvites {
  leaderboard: InviteLeaderboardEntry[];
  total: number;
}

export interface SecurityStaff {
  discord_id: string;
  role: string;
}

export interface SecurityIncident {
  id: number;
  guild_id: string;
  kind: string;
  severity: string;
  status: string;
  created_at: string;
}

export interface AdminSecurity {
  staff: SecurityStaff[];
  whitelist_ids: number[];
  maintenance_mode: boolean;
  push_subscribers: number;
  incidents: SecurityIncident[];
}

export interface ScheduledMessage {
  id: number;
  guild_id: string;
  channel_id: string | number;
  content: string;
  interval_minutes: number | null;
  daily_hhmm: string | null;
  run_at: string | null;
  enabled: boolean;
  created_by: string | null;
  created_at: string;
}
