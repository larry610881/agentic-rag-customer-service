import type { QueryClient } from "@tanstack/react-query";

/**
 * QueryClient 橋接（M43）：QueryClient 建在 React 樹內，但登出邏輯在 zustand
 * store（React 樹外）。透過此 module-level 註冊點，讓 logout 能清掉整個查詢快取，
 * 避免同分頁換租戶時，key 不含 tenant 維度的查詢（system-prompts / provider-settings
 * / logs / observability / prompt-optimizer datasets…）命中前一租戶的殘留快取。
 */
let client: QueryClient | null = null;

export const registerQueryClient = (c: QueryClient): void => {
  client = c;
};

export const clearQueryCache = (): void => {
  client?.clear();
};
