import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { renderWithProviders } from "@/test/test-utils";
import { server } from "@/test/mocks/server";
import { AdminToolsTable } from "@/features/admin/components/admin-tools-table";
import { useAuthStore } from "@/stores/use-auth-store";

describe("AdminToolsTable", () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      role: "system_admin",
      tenants: [],
    });
  });

  it("happy: 顯示工具清單並帶 scope badge", async () => {
    server.use(
      http.get("*/api/v1/admin/tools", () =>
        HttpResponse.json([
          {
            name: "rag_query",
            label: "知識庫查詢",
            description: "desc",
            requires_kb: true,
            scope: "global",
            tenant_ids: [],
          },
          {
            name: "query_dm_with_image",
            label: "DM 圖卡查詢",
            description: "desc",
            requires_kb: true,
            scope: "tenant",
            tenant_ids: ["tenant-a"],
          },
        ]),
      ),
      http.get("*/api/v1/tenants", () =>
        HttpResponse.json({ items: [], total: 0 }),
      ),
    );

    renderWithProviders(<AdminToolsTable />);

    expect(await screen.findByText("知識庫查詢")).toBeInTheDocument();
    expect(await screen.findByText("DM 圖卡查詢")).toBeInTheDocument();
    expect(screen.getByText("Global")).toBeInTheDocument();
    // tenant badge shows count ratio
    expect(screen.getByText(/Tenant · 1\//)).toBeInTheDocument();
  });

  it("empty: 後端回傳空清單顯示提示", async () => {
    server.use(
      http.get("*/api/v1/admin/tools", () => HttpResponse.json([])),
      http.get("*/api/v1/tenants", () =>
        HttpResponse.json({ items: [], total: 0 }),
      ),
    );

    renderWithProviders(<AdminToolsTable />);

    await waitFor(() =>
      expect(
        screen.getByText(/目前沒有任何 built-in tool/),
      ).toBeInTheDocument(),
    );
  });

  it("error: 後端 500 顯示錯誤訊息", async () => {
    server.use(
      http.get("*/api/v1/admin/tools", () =>
        HttpResponse.json(null, { status: 500 }),
      ),
      http.get("*/api/v1/tenants", () =>
        HttpResponse.json({ items: [], total: 0 }),
      ),
    );

    renderWithProviders(<AdminToolsTable />);

    await waitFor(() =>
      expect(screen.getByText(/載入失敗/)).toBeInTheDocument(),
    );
  });
});
