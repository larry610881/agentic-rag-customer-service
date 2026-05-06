import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/test-utils";
import AdminOutboxPage from "@/pages/admin-outbox";
import { useAuthStore } from "@/stores/use-auth-store";
import { resetOutboxMocks } from "@/test/mocks/handlers/outbox";

describe("AdminOutboxPage", () => {
  beforeEach(() => {
    resetOutboxMocks();
    useAuthStore.setState({
      token: "test-token",
      tenantId: "tenant-1",
      tenants: [],
    });
  });

  it("renders page header + stats panel + DLQ table", async () => {
    renderWithProviders(<AdminOutboxPage />);
    expect(
      screen.getByRole("heading", { name: /outbox 死信佇列/i }),
    ).toBeInTheDocument();
    // Stats labels appear
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("DLQ (dead)")).toBeInTheDocument();
    // Mock DLQ rows render
    expect(
      await screen.findByTestId(/dlq-row-evt-aaaaaaaa/),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(/dlq-row-evt-bbbbbbbb/),
    ).toBeInTheDocument();
  });

  it("retry button triggers POST then removes row from DLQ", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminOutboxPage />);
    await screen.findByTestId(/dlq-row-evt-aaaaaaaa/);
    const retryBtns = screen.getAllByRole("button", { name: /^重排$/ });
    await user.click(retryBtns[0]);
    await waitFor(() => {
      expect(
        screen.queryByTestId(/dlq-row-evt-aaaaaaaa/),
      ).not.toBeInTheDocument();
    });
  });

  it("bulk retry button triggers POST then DLQ becomes empty", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminOutboxPage />);
    await screen.findByTestId(/dlq-row-evt-aaaaaaaa/);
    const bulkBtn = screen.getByRole("button", {
      name: /批次重排（最多 100 筆）/,
    });
    await user.click(bulkBtn);
    expect(await screen.findByText(/DLQ 是空的/)).toBeInTheDocument();
  });

  it("abandon opens confirm dialog requiring reason input", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminOutboxPage />);
    await screen.findByTestId(/dlq-row-evt-aaaaaaaa/);
    const abandonBtns = screen.getAllByRole("button", { name: /^放棄$/ });
    await user.click(abandonBtns[0]);
    // Dialog opens — confirm button should exist (label 永久放棄)
    const confirmBtn = await screen.findByRole("button", {
      name: /永久放棄/,
    });
    expect(confirmBtn).toBeInTheDocument();
  });

  it("filter by tenant_id narrows DLQ list", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdminOutboxPage />);
    await screen.findByTestId(/dlq-row-evt-aaaaaaaa/);
    expect(screen.getByTestId(/dlq-row-evt-bbbbbbbb/)).toBeInTheDocument();
    const tenantInput = screen.getByLabelText(/租戶 ID/);
    await user.type(tenantInput, "tenant-1");
    await waitFor(() => {
      expect(
        screen.queryByTestId(/dlq-row-evt-bbbbbbbb/),
      ).not.toBeInTheDocument();
    });
    expect(screen.getByTestId(/dlq-row-evt-aaaaaaaa/)).toBeInTheDocument();
  });
});
