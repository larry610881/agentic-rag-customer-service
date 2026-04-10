import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/test-utils";
import { CompileWikiCard } from "@/features/bot/components/compile-wiki-card";
import { useAuthStore } from "@/stores/use-auth-store";

describe("CompileWikiCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
    });
  });

  it("should render compile button", async () => {
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json(null, { status: 404 }),
      ),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    expect(
      await screen.findByTestId("compile-wiki-button"),
    ).toBeInTheDocument();
  });

  it("should show 'ready' badge with stats when wiki status is ready", async () => {
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json({
          wiki_graph_id: "g-1",
          bot_id: "bot-1",
          kb_id: "kb-1",
          status: "ready",
          node_count: 42,
          edge_count: 87,
          cluster_count: 5,
          doc_count: 10,
          compiled_at: "2026-04-10T10:00:00Z",
          token_usage: {
            input: 5000,
            output: 1200,
            total: 6200,
            estimated_cost: 0.0125,
          },
          errors: null,
        }),
      ),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    const badge = await screen.findByTestId("wiki-status-badge");
    expect(badge).toHaveTextContent("已就緒");
    expect(screen.getByText("42")).toBeInTheDocument(); // node_count
    expect(screen.getByText("87")).toBeInTheDocument(); // edge_count
  });

  it("should show 'compiling' badge with spinner when status is compiling", async () => {
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json({
          wiki_graph_id: "g-1",
          bot_id: "bot-1",
          kb_id: "kb-1",
          status: "compiling",
          node_count: 0,
          edge_count: 0,
          cluster_count: 0,
          doc_count: 5,
          compiled_at: null,
          token_usage: null,
          errors: null,
        }),
      ),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    const badge = await screen.findByTestId("wiki-status-badge");
    expect(badge).toHaveTextContent("編譯中");
  });

  it("should show 'stale' badge with warning text", async () => {
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json({
          wiki_graph_id: "g-1",
          bot_id: "bot-1",
          kb_id: "kb-1",
          status: "stale",
          node_count: 30,
          edge_count: 50,
          cluster_count: 4,
          doc_count: 8,
          compiled_at: "2026-04-09T10:00:00Z",
          token_usage: null,
          errors: null,
        }),
      ),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    expect(await screen.findByTestId("wiki-status-badge")).toHaveTextContent(
      "需重新編譯",
    );
    expect(
      screen.getByText(/知識庫文件已更新，建議重新編譯/),
    ).toBeInTheDocument();
  });

  it("should show 'failed' badge with error list", async () => {
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json({
          wiki_graph_id: "g-1",
          bot_id: "bot-1",
          kb_id: "kb-1",
          status: "failed",
          node_count: 0,
          edge_count: 0,
          cluster_count: 0,
          doc_count: 3,
          compiled_at: "2026-04-10T10:00:00Z",
          token_usage: null,
          errors: ["doc1.pdf: ParseError: invalid format"],
        }),
      ),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    expect(await screen.findByTestId("wiki-status-badge")).toHaveTextContent(
      "編譯失敗",
    );
    expect(
      screen.getByText("doc1.pdf: ParseError: invalid format"),
    ).toBeInTheDocument();
  });

  it("should open confirmation dialog when compile button clicked", async () => {
    const user = userEvent.setup();
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json(null, { status: 404 }),
      ),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    const button = await screen.findByTestId("compile-wiki-button");
    await user.click(button);
    expect(await screen.findByText("確認編譯 Wiki？")).toBeInTheDocument();
    expect(screen.getByTestId("compile-wiki-confirm")).toBeInTheDocument();
  });

  it("should call compile mutation when confirm clicked", async () => {
    const user = userEvent.setup();
    let compileCallCount = 0;
    server.use(
      http.get("/api/v1/bots/:botId/wiki/status", () =>
        HttpResponse.json(null, { status: 404 }),
      ),
      http.post("/api/v1/bots/:botId/wiki/compile", () => {
        compileCallCount++;
        return HttpResponse.json(
          {
            bot_id: "bot-1",
            status: "accepted",
            message: "ok",
          },
          { status: 202 },
        );
      }),
    );
    renderWithProviders(<CompileWikiCard botId="bot-1" />);
    await user.click(await screen.findByTestId("compile-wiki-button"));
    await user.click(await screen.findByTestId("compile-wiki-confirm"));
    await waitFor(() => {
      expect(compileCallCount).toBe(1);
    });
  });
});
