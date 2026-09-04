/**
 * Widget session（Issue #67 P4）
 *
 * 後端 `GET /config` 依 Origin 白名單簽發短效 widget token（15 分鐘）與伺服器簽發的
 * visitor id。之後 chat / feedback / error / 文件檢視都要帶票；401 時重新取設定換票。
 */

import type { WidgetConfig } from "./types";
import { getVisitorId, setVisitorId } from "./visitor";

let currentToken = "";
let expiresAt = 0;
let apiBase = "";
let shortCode = "";

/** Fetch widget config (and a fresh token) from the backend. */
export async function fetchWidgetConfig(
  base: string,
  code: string,
): Promise<WidgetConfig> {
  apiBase = base;
  shortCode = code;
  const res = await fetch(`${base}/api/v1/widget/${code}/config`, {
    headers: { "X-Visitor-Id": getVisitorId() },
  });
  if (!res.ok) throw new Error(`Config fetch failed: HTTP ${res.status}`);
  const data = (await res.json()) as WidgetConfig;
  if (data.widget_token) {
    currentToken = data.widget_token;
    expiresAt = Date.now() + Math.max(30, (data.token_expires_in ?? 900) - 30) * 1000;
  }
  if (data.visitor_id) setVisitorId(data.visitor_id);
  return data;
}

/** Current token, refreshed transparently when close to expiry. */
export async function getWidgetToken(): Promise<string> {
  if (!currentToken || Date.now() >= expiresAt) {
    if (apiBase && shortCode) await fetchWidgetConfig(apiBase, shortCode);
  }
  return currentToken;
}

/** Synchronous accessor for places that cannot await (e.g. building an <a href>). */
export function peekWidgetToken(): string {
  return currentToken;
}

/** Force a refresh (after a 401). */
export async function refreshWidgetToken(): Promise<string> {
  currentToken = "";
  return getWidgetToken();
}

/**
 * 宿主身分綁定（P7b）：hash 必須由宿主後端以租戶 identity secret 計算
 * HMAC-SHA256(secret, `${userId}.${exp}`)；前端只轉交。
 */
export interface IdentifyPayload {
  userId: string;
  exp: number; // unix seconds，最多未來 24 小時
  hash: string;
  name?: string;
  email?: string;
}

export interface IdentifyResult {
  identified: boolean;
  reason?: string;
}

export async function identify(payload: IdentifyPayload): Promise<IdentifyResult> {
  if (!apiBase || !shortCode) throw new Error("widget not initialized");
  const res = await widgetFetch(`${apiBase}/api/v1/widget/${shortCode}/identify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      exp: payload.exp,
      hash: payload.hash,
      name: payload.name,
      email: payload.email,
    }),
  });
  if (res.status === 403) return { identified: false, reason: "identity_required" };
  if (!res.ok) return { identified: false, reason: `HTTP ${res.status}` };
  const data = (await res.json()) as {
    identified: boolean;
    widget_token?: string;
    token_expires_in?: number;
    reason?: string;
  };
  if (data.identified && data.widget_token) {
    currentToken = data.widget_token;
    expiresAt = Date.now() + Math.max(30, (data.token_expires_in ?? 900) - 30) * 1000;
  }
  return { identified: data.identified, reason: data.reason };
}

/** Headers for authenticated widget calls. */
export async function authHeaders(
  extra: Record<string, string> = {},
): Promise<Record<string, string>> {
  const token = await getWidgetToken();
  return { ...extra, Authorization: `Bearer ${token}` };
}

/**
 * fetch with widget token; on 401 refreshes the token once and retries.
 */
export async function widgetFetch(
  url: string,
  init: RequestInit & { headers?: Record<string, string> } = {},
): Promise<Response> {
  const headers = await authHeaders(init.headers ?? {});
  let res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    const token = await refreshWidgetToken();
    res = await fetch(url, {
      ...init,
      headers: { ...(init.headers ?? {}), Authorization: `Bearer ${token}` },
    });
  }
  return res;
}
