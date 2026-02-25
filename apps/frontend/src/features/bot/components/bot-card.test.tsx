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

  it("should link to bot detail page", () => {
    renderWithProviders(<BotCard bot={mockBot} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/bots/bot-1");
  });
});
