import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { BotCard } from "@/features/bot/components/bot-card";
import { mockBot } from "@/test/fixtures/bot";

describe("BotCard", () => {
  it("should render bot name", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    expect(screen.getByText("Customer Service Bot")).toBeInTheDocument();
  });

  it("should render bot description", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    expect(screen.getByText("Handles customer inquiries")).toBeInTheDocument();
  });

  it("should show Active badge when bot is active", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    expect(screen.getByText("啟用")).toBeInTheDocument();
  });

  it("should show Inactive badge when bot is inactive", () => {
    renderWithProviders(
      <BotCard bot={{ ...mockBot, is_active: false }} />,
    );
    expect(screen.getByText("停用")).toBeInTheDocument();
  });

  it("should display KB count", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    expect(screen.getByText("2 KB")).toBeInTheDocument();
  });

  it("should show 深度 badge for deep mode (Issue #66)", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    expect(screen.getByText("深度")).toBeInTheDocument();
  });

  it("should show 快速 badge for fast mode (Issue #66)", () => {
    renderWithProviders(<BotCard bot={{ ...mockBot, mode: "fast" }} />);
    expect(screen.getByText("快速")).toBeInTheDocument();
  });

  it("should show 知識庫 badge for kb mode (Issue #70)", () => {
    renderWithProviders(<BotCard bot={{ ...mockBot, mode: "kb" }} />);
    expect(screen.getByText("知識庫")).toBeInTheDocument();
  });

  it("should link to bot detail page", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/bots/bot-1");
  });
});
