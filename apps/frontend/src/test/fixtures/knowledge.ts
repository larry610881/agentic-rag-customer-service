import type {
  DocumentResponse,
  KnowledgeBase,
  TaskResponse,
  UploadDocumentResponse,
} from "@/types/knowledge";

export const mockKnowledgeBases: KnowledgeBase[] = [
  {
    id: "kb-1",
    tenant_id: "tenant-1",
    name: "Product Documentation",
    description: "All product-related documents",
    document_count: 5,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-15T00:00:00Z",
  },
  {
    id: "kb-2",
    tenant_id: "tenant-1",
    name: "FAQ",
    description: "Frequently asked questions",
    document_count: 3,
    created_at: "2024-02-01T00:00:00Z",
    updated_at: "2024-02-10T00:00:00Z",
  },
];

export const mockDocuments: DocumentResponse[] = [
  {
    id: "doc-1",
    kb_id: "kb-1",
    tenant_id: "tenant-1",
    filename: "product-guide.pdf",
    content_type: "application/pdf",
    status: "processed",
    chunk_count: 42,
    avg_chunk_length: 250,
    min_chunk_length: 80,
    max_chunk_length: 500,
    quality_score: 0.9,
    quality_issues: [],
    created_at: "2024-01-05T00:00:00Z",
    updated_at: "2024-01-05T00:01:00Z",
  },
  {
    id: "doc-2",
    kb_id: "kb-1",
    tenant_id: "tenant-1",
    filename: "setup-manual.pdf",
    content_type: "application/pdf",
    status: "processing",
    chunk_count: 0,
    avg_chunk_length: 0,
    min_chunk_length: 0,
    max_chunk_length: 0,
    quality_score: 0.0,
    quality_issues: [],
    created_at: "2024-01-06T00:00:00Z",
    updated_at: "2024-01-06T00:00:00Z",
  },
];

export const mockUploadResponse: UploadDocumentResponse = {
  document: {
    id: "doc-3",
    kb_id: "kb-1",
    tenant_id: "tenant-1",
    filename: "new-doc.txt",
    content_type: "text/plain",
    status: "pending",
    chunk_count: 0,
    avg_chunk_length: 0,
    min_chunk_length: 0,
    max_chunk_length: 0,
    quality_score: 0.0,
    quality_issues: [],
    created_at: "2024-01-07T00:00:00Z",
    updated_at: "2024-01-07T00:00:00Z",
  },
  task_id: "task-1",
};

export const mockTaskResponse: TaskResponse = {
  id: "task-1",
  status: "completed",
  progress: 100,
  result: { chunks: 42 },
};

export const mockTaskPending: TaskResponse = {
  id: "task-1",
  status: "processing",
  progress: 50,
};
