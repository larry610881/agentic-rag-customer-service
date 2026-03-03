import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { DocumentList } from "@/features/knowledge/components/document-list";
import type { DocumentQualityStat } from "@/types/knowledge";

describe("Document quality indicators integration", () => {
  const documents = [
    {
      id: "doc-good",
      kb_id: "kb-1",
      tenant_id: "tenant-1",
      filename: "good-doc.pdf",
      content_type: "application/pdf",
      status: "processed" as const,
      chunk_count: 20,
      avg_chunk_length: 200,
      min_chunk_length: 100,
      max_chunk_length: 400,
      quality_score: 0.9,
      quality_issues: [],
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    },
    {
      id: "doc-warning",
      kb_id: "kb-1",
      tenant_id: "tenant-1",
      filename: "warning-doc.pdf",
      content_type: "application/pdf",
      status: "processed" as const,
      chunk_count: 10,
      avg_chunk_length: 150,
      min_chunk_length: 50,
      max_chunk_length: 300,
      quality_score: 0.6,
      quality_issues: ["short_chunks"],
      created_at: "2024-01-02T00:00:00Z",
      updated_at: "2024-01-02T00:00:00Z",
    },
    {
      id: "doc-poor",
      kb_id: "kb-1",
      tenant_id: "tenant-1",
      filename: "poor-doc.pdf",
      content_type: "application/pdf",
      status: "processed" as const,
      chunk_count: 5,
      avg_chunk_length: 50,
      min_chunk_length: 20,
      max_chunk_length: 100,
      quality_score: 0.3,
      quality_issues: ["too_short", "low_diversity"],
      created_at: "2024-01-03T00:00:00Z",
      updated_at: "2024-01-03T00:00:00Z",
    },
  ];

  const qualityStats: DocumentQualityStat[] = [
    {
      document_id: "doc-poor",
      negative_feedback_count: 3,
      total_feedback_count: 5,
    },
  ];

  it("should display quality icons for different score levels", () => {
    renderWithProviders(
      <DocumentList kbId="kb-1" documents={documents} />,
    );

    // Good quality (>= 0.8) — green shield
    expect(screen.getByTestId("quality-good")).toBeInTheDocument();
    // Warning quality (>= 0.5, < 0.8) — yellow shield
    expect(screen.getByTestId("quality-warning")).toBeInTheDocument();
    // Poor quality (< 0.5) — red shield
    expect(screen.getByTestId("quality-poor")).toBeInTheDocument();
  });

  it("should display negative feedback badge when qualityStats are provided", () => {
    renderWithProviders(
      <DocumentList
        kbId="kb-1"
        documents={documents}
        qualityStats={qualityStats}
      />,
    );

    // doc-poor has 3 negative feedback
    expect(screen.getByTestId("negative-feedback-badge")).toBeInTheDocument();
    expect(screen.getByText("3 差評")).toBeInTheDocument();
  });
});
