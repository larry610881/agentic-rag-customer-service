import { API_BASE } from "@/lib/api-config";
import type { ReportErrorPayload } from "@/types/error-event";

class ErrorReporter {
  private buffer: ReportErrorPayload[] = [];
  private seen = new Set<string>();
  private count = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private readonly MAX_PER_SESSION = 50;
  private readonly FLUSH_INTERVAL = 5000;
  private readonly FLUSH_SIZE = 5;

  install(): void {
    window.onerror = (message, source, lineno, colno, error) => {
      this.report({
        source: "frontend",
        error_type: error?.name || "Error",
        message: String(message),
        stack_trace: error?.stack,
        path: window.location.pathname,
        user_agent: navigator.userAgent,
        extra: { source: source, lineno, colno },
      });
    };

    window.addEventListener("unhandledrejection", (event) => {
      const reason = event.reason;
      this.report({
        source: "frontend",
        error_type: reason?.name || "UnhandledRejection",
        message: reason?.message || String(reason),
        stack_trace: reason?.stack,
        path: window.location.pathname,
        user_agent: navigator.userAgent,
      });
    });
  }

  report(payload: ReportErrorPayload): void {
    if (this.count >= this.MAX_PER_SESSION) return;
    const key = `${payload.error_type}|${payload.message}`;
    if (this.seen.has(key)) return;
    this.seen.add(key);
    this.count++;
    this.buffer.push(payload);
    if (this.buffer.length >= this.FLUSH_SIZE) {
      this.flush();
    } else if (!this.timer) {
      this.timer = setTimeout(() => this.flush(), this.FLUSH_INTERVAL);
    }
  }

  private flush(): void {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    const batch = this.buffer.splice(0);
    for (const item of batch) {
      fetch(`${API_BASE}/api/v1/error-events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item),
      }).catch(() => {
        /* swallow */
      });
    }
  }
}

export const errorReporter = new ErrorReporter();
