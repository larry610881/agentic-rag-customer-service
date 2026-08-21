/** M53：#54 版本 mutation hooks 的 endpoint 契約測試（MSW）。
 *
 * 防守場景：publish/reject/validate/rollback/replay 任一 endpoint path 打字錯誤
 * → vitest 全綠但使用者按下按鈕得到 404。此處以 MSW 綁定「正確路徑」，
 * 路徑不符時 mutation reject、測試失敗。
 */

import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import {
  usePublishConfigVersion,
  useRejectConfigVersion,
  useRollbackConfigVersion,
  useValidateConfigVersion,
} from "@/hooks/queries/use-config-versions";
import { server } from "@/test/mocks/server";
import { AllProviders } from "@/test/test-utils";

const BASE = "*/api/v1/bots/bot-1/config-versions";

function bindOnce(method: "post", url: string, hits: string[]) {
  server.use(
    http[method](url, () => {
      hits.push(url);
      return HttpResponse.json({ id: "ver-1", status: "published" });
    }),
  );
}

describe("use-config-versions mutation endpoint 契約", () => {
  it("publish 打 /{versionId}/publish", async () => {
    const hits: string[] = [];
    bindOnce("post", `${BASE}/ver-1/publish`, hits);
    const { result } = renderHook(() => usePublishConfigVersion(), {
      wrapper: AllProviders,
    });
    await act(async () => {
      await result.current.mutateAsync({ botId: "bot-1", versionId: "ver-1" });
    });
    await waitFor(() => expect(hits).toHaveLength(1));
  });

  it("reject 打 /{versionId}/reject", async () => {
    const hits: string[] = [];
    bindOnce("post", `${BASE}/ver-1/reject`, hits);
    const { result } = renderHook(() => useRejectConfigVersion(), {
      wrapper: AllProviders,
    });
    await act(async () => {
      await result.current.mutateAsync({ botId: "bot-1", versionId: "ver-1" });
    });
    await waitFor(() => expect(hits).toHaveLength(1));
  });

  it("validate 打 /{versionId}/validate", async () => {
    const hits: string[] = [];
    bindOnce("post", `${BASE}/ver-1/validate`, hits);
    const { result } = renderHook(() => useValidateConfigVersion(), {
      wrapper: AllProviders,
    });
    await act(async () => {
      await result.current.mutateAsync({ botId: "bot-1", versionId: "ver-1" });
    });
    await waitFor(() => expect(hits).toHaveLength(1));
  });

  it("rollback 打 /rollback", async () => {
    const hits: string[] = [];
    bindOnce("post", `${BASE}/rollback`, hits);
    const { result } = renderHook(() => useRollbackConfigVersion(), {
      wrapper: AllProviders,
    });
    await act(async () => {
      await result.current.mutateAsync({
        botId: "bot-1",
        targetVersionId: "ver-0",
      });
    });
    await waitFor(() => expect(hits).toHaveLength(1));
  });
});
