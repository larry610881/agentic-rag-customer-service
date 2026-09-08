import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getRateLimitSnapshot } from "@/lib/api-client";
import type { UploadingFileItem } from "@/features/knowledge/components/upload-progress-card";

/**
 * 批次上傳佇列（類似雲端硬碟：一次丟一整批，背景逐一送出）。
 *
 * 為什麼需要它：原本的實作是 `files.forEach(() => mutateAsync(...))`，
 * 一次丟 33 個檔就同時發出 33 條上傳流程。租戶層限流是 **100 rpm 且整個租戶共用**，
 * 而每個檔要打兩次 API（request-upload、confirm-upload，中間直傳 GCS 不算），
 * 於是前幾個成功、後面全部 429（2026-09-08 實測）。
 *
 * 節流策略刻意**不用「檔數 × 固定百分比」自己算預算**：額度是租戶共用的，
 * 同一時間還有文件輪詢、對話測試、widget、LINE 在吃，單一分頁算不準別人的用量。
 * 改成三層，全部以伺服器實際回報為準：
 *
 * 1. **併發上限**：預設 2，避免單一分頁把額度吃光害別人的對話被擋。
 * 2. **回饋降速**：讀 `x-ratelimit-remaining`，低於 `SLOW_DOWN_RATIO` 時串行並加間隔。
 * 3. **429 全域暫停**：額度是租戶層的，換一個檔送照樣被擋，所以暫停**整個佇列**
 *    `Retry-After` 秒再恢復，而不是只重試那一個檔。
 */

const DEFAULT_CONCURRENCY = 2;
/** 剩餘額度低於總額這個比例時降速 */
const SLOW_DOWN_RATIO = 0.2;
/** 降速時每個檔之間的間隔 */
const SLOW_DOWN_GAP_MS = 1500;
/** 正常時的間隔（仍留一點，避免瞬間打滿） */
const NORMAL_GAP_MS = 250;
/** 單一檔案因 429 重試的次數上限 */
const MAX_RETRY = 3;
/** 429 沒給 Retry-After 時的保底等待 */
const FALLBACK_RETRY_AFTER_S = 30;

export type QueueStats = {
  total: number;
  queued: number;
  uploading: number;
  success: number;
  error: number;
  /** > 0 表示佇列因限流暫停中，數字是剩餘秒數 */
  pausedSeconds: number;
};

type QueueEntry = {
  id: string;
  file: File;
  attempts: number;
};

export type UploadTask = (args: {
  file: File;
  onProgress: (pct: number) => void;
}) => Promise<unknown>;

const sleep = (ms: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });

export function useUploadQueue(
  uploadTask: UploadTask,
  options?: { concurrency?: number; onFileDone?: (id: string) => void },
) {
  const concurrency = options?.concurrency ?? DEFAULT_CONCURRENCY;
  const [items, setItems] = useState<UploadingFileItem[]>([]);
  const [pausedUntil, setPausedUntil] = useState(0);
  const [now, setNow] = useState(() => Date.now());

  const pendingRef = useRef<QueueEntry[]>([]);
  const runningRef = useRef(0);
  const pausedUntilRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // 暫停中每秒重算一次，讓「剩餘 N 秒」的顯示會動
  useEffect(() => {
    if (pausedUntil <= Date.now()) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [pausedUntil]);

  const patch = useCallback(
    (id: string, next: Partial<UploadingFileItem>) => {
      if (!mountedRef.current) return;
      setItems((prev) => prev.map((f) => (f.id === id ? { ...f, ...next } : f)));
    },
    [],
  );

  const waitWhilePaused = useCallback(async () => {
    while (mountedRef.current && pausedUntilRef.current > Date.now()) {
      await sleep(Math.min(1000, pausedUntilRef.current - Date.now()));
    }
  }, []);

  const pauseAll = useCallback((seconds: number) => {
    const until = Date.now() + seconds * 1000;
    // 取較晚者：多個檔同時撞 429 時不要把暫停時間縮短
    pausedUntilRef.current = Math.max(pausedUntilRef.current, until);
    if (mountedRef.current) setPausedUntil(pausedUntilRef.current);
  }, []);

  /** 依伺服器回報的剩餘額度決定這一輪要不要放慢 */
  const gapForCurrentQuota = useCallback(() => {
    const { limit, remaining } = getRateLimitSnapshot();
    if (limit && remaining !== null && remaining < limit * SLOW_DOWN_RATIO) {
      return SLOW_DOWN_GAP_MS;
    }
    return NORMAL_GAP_MS;
  }, []);

  const runWorker = useCallback(async () => {
    while (mountedRef.current) {
      await waitWhilePaused();
      const entry = pendingRef.current.shift();
      if (!entry) break;

      patch(entry.id, { status: "uploading", progress: 0 });
      try {
        await uploadTask({
          file: entry.file,
          onProgress: (pct) =>
            patch(entry.id, { progress: Math.min(pct, 99) }),
        });
        patch(entry.id, { status: "success", progress: 100 });
        options?.onFileDone?.(entry.id);
      } catch (err) {
        const is429 = err instanceof ApiError && err.status === 429;
        if (is429 && entry.attempts < MAX_RETRY) {
          const wait =
            (err as ApiError).retryAfter ?? FALLBACK_RETRY_AFTER_S;
          pauseAll(wait);
          // 放回隊首：先進來的先送完，順序才符合使用者預期
          pendingRef.current.unshift({ ...entry, attempts: entry.attempts + 1 });
          patch(entry.id, { status: "queued", progress: 0 });
        } else {
          const message =
            err instanceof Error && err.message ? err.message : "上傳失敗";
          patch(entry.id, {
            status: "error",
            error: is429 ? `限流重試 ${MAX_RETRY} 次仍失敗` : message,
          });
        }
      }
      await sleep(gapForCurrentQuota());
    }
    runningRef.current -= 1;
  }, [uploadTask, patch, pauseAll, waitWhilePaused, gapForCurrentQuota, options]);

  const pump = useCallback(() => {
    while (
      runningRef.current < concurrency &&
      pendingRef.current.length > 0
    ) {
      runningRef.current += 1;
      void runWorker();
    }
  }, [concurrency, runWorker]);

  const enqueue = useCallback(
    (files: { id: string; file: File }[]) => {
      if (files.length === 0) return;
      setItems((prev) => [
        ...prev,
        ...files.map(({ id, file }) => ({
          id,
          name: file.name,
          progress: 0,
          status: "queued" as const,
        })),
      ]);
      pendingRef.current.push(
        ...files.map(({ id, file }) => ({ id, file, attempts: 0 })),
      );
      pump();
    },
    [pump],
  );

  const retryFailed = useCallback(() => {
    setItems((prev) => {
      const failed = prev.filter((f) => f.status === "error");
      if (failed.length === 0) return prev;
      return prev.map((f) =>
        f.status === "error"
          ? { ...f, status: "queued" as const, error: undefined, progress: 0 }
          : f,
      );
    });
  }, []);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearFinished = useCallback(() => {
    setItems((prev) => prev.filter((f) => f.status !== "success"));
  }, []);

  const stats: QueueStats = {
    total: items.length,
    queued: items.filter((f) => f.status === "queued").length,
    uploading: items.filter((f) => f.status === "uploading").length,
    success: items.filter((f) => f.status === "success").length,
    error: items.filter((f) => f.status === "error").length,
    pausedSeconds: Math.max(0, Math.ceil((pausedUntil - now) / 1000)),
  };

  return { items, stats, enqueue, retryFailed, dismiss, clearFinished };
}
