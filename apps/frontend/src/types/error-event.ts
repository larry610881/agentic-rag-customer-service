export interface ErrorEvent {
  id: string;
  fingerprint: string;
  source: "backend" | "frontend" | "widget";
  error_type: string;
  message: string;
  stack_trace?: string | null;
  request_id?: string | null;
  path?: string | null;
  method?: string | null;
  status_code?: number | null;
  tenant_id?: string | null;
  user_agent?: string | null;
  extra?: Record<string, unknown> | null;
  resolved: boolean;
  resolved_at?: string | null;
  resolved_by?: string | null;
  created_at: string;
}

export interface ErrorEventListResponse {
  items: ErrorEvent[];
  total: number;
}

export interface ReportErrorPayload {
  source: "frontend" | "widget";
  error_type: string;
  message: string;
  stack_trace?: string;
  path?: string;
  user_agent?: string;
  extra?: Record<string, unknown>;
}

export interface NotificationChannel {
  id: string;
  channel_type: "email" | "slack" | "teams";
  name: string;
  enabled: boolean;
  config: Record<string, unknown>;
  throttle_minutes: number;
  min_severity: "all" | "5xx_only" | "off";
  notify_diagnostics: boolean;
  diagnostic_severity: "critical" | "warning" | "all";
  updated_at: string;
  created_at: string;
}

export interface CreateChannelPayload {
  channel_type: "email" | "slack" | "teams";
  name: string;
  enabled: boolean;
  config: Record<string, unknown>;
  throttle_minutes?: number;
  min_severity?: string;
  notify_diagnostics?: boolean;
  diagnostic_severity?: string;
}
