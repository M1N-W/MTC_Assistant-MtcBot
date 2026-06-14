export type Workspace = {
  class_id: string;
  label: string;
  active_term_id: string;
  active_term_label: string;
  status: string;
  can_edit_active_term: boolean;
};

export type ServiceMap = {
  line: boolean;
  gemini: boolean;
  firebase: boolean;
  broadcast: boolean;
};

export type Metrics = {
  uptime_seconds: number;
  total_requests: number;
  total_errors: number;
  error_rate_percent: number;
  avg_response_time_ms: number;
};

export type Homework = {
  id: string;
  subject?: string;
  detail?: string;
  due_date?: string;
  created_at?: string;
};

export type BroadcastRecord = {
  id: string;
  message?: string;
  sent_count?: number;
  failed_count?: number;
  timestamp?: string;
  success?: boolean;
};

export type Overview = {
  generated_at: string;
  services: ServiceMap;
  metrics: Metrics;
  counts: {
    registered_users: number;
    rate_limit_tracked_users: number;
    active_homework_preview: number;
    banned_users: number;
    recent_broadcasts: number;
  };
  homework_preview: Homework[];
  recent_broadcasts: BroadcastRecord[];
};

export type UserRow = { user_id: string };

export type BlacklistRow = {
  user_id: string;
  reason: string;
};

export type PaperlessCaptureResult = {
  analysis: {
    title: string;
    summary: string[];
    homework_candidates: string[];
    keywords: string[];
    paperless_value: string;
  };
  image_size_bytes: number;
  mime_type: string;
};

export type PaperlessSummary = {
  successful_capture_count: number;
  latest_success_at: string | null;
  recent: Array<{
    id: string;
    created_at: string | null;
    mime_type: string | null;
    image_size_bytes: number | null;
    summary_item_count: number;
    homework_candidate_count: number;
  }>;
};
