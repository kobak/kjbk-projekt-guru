export type Member = {
  id: number;
  name: string;
  email: string;
  admin: boolean;
  active: boolean;
};
export type ThemeMode = "system" | "light" | "dark";
export type ListSort = "due" | "priority" | "created" | "manual";
export type Appearance = {
  theme: ThemeMode;
  default_view: "board" | "list";
  show_completed: boolean;
  list_sort: ListSort;
  font_size: "normal" | "large";
  density: "compact" | "spacious";
  updated_at: string | null;
};
export type ListOrder = { task_ids: string[]; version: number };
export type Project = {
  id: string;
  name: string;
  description: string;
  color: string;
  archived: boolean;
};
export type Status = "todo" | "doing" | "review" | "done";
export type Task = {
  id: string;
  project_id: string;
  title: string;
  description: string;
  status: Status;
  priority: "low" | "normal" | "high" | "urgent";
  assignee_id: number | null;
  created_by_id: number;
  due_date: string | null;
  due_time: string | null;
  labels: string[];
  position: number;
  version: number;
  created_at: string;
  updated_at: string;
  checklist: { id: number; text: string; done: boolean }[];
  comment_count: number;
  attachment_count: number;
  calendar: {
    enabled: boolean;
    url: string;
    error: string;
    pending: boolean;
  } | null;
  calendar_manual_url?: string;
  calendar_ics_url?: string;
  comments?: {
    id: number;
    user: Member;
    body: string;
    created_at: string;
    mentions: { user_id: number; start: number; end: number }[];
  }[];
  attachments?: {
    id: number;
    name: string;
    size: number;
    url: string;
    kind: "file" | "drive";
    can_delete: boolean;
  }[];
};
export type Notice = {
  id: number;
  title: string;
  body: string;
  read: boolean;
  task_id: string | null;
  created_at: string;
};
export type Integrations = {
  email_configured: boolean;
  google_configured: boolean;
  google_connected: boolean;
  google_error: string;
  push_configured: boolean;
  vapid_public_key: string;
  mcp_url: string;
};
export type NotificationEvent =
  "task_assigned" | "task_updated" | "comment" | "mention" | "due" | "overdue";
export type NotificationPreferences = {
  events: { key: NotificationEvent; label: string; description: string }[];
  preferences: Record<NotificationEvent, { email: boolean; push: boolean }>;
  email: string;
  email_configured: boolean;
};
export type Bootstrap = {
  appearance: Appearance;
  list_order: ListOrder;
  workspace: string;
  user: Member;
  members: Member[];
  projects: Project[];
  tasks: Task[];
  notifications: Notice[];
  unread: number;
  integrations: Integrations;
  activity: {
    id: number;
    user: Member;
    text: string;
    task_id: string | null;
    task_title: string;
    created_at: string;
  }[];
};
