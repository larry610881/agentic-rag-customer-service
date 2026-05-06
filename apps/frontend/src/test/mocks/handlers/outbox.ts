import { http, HttpResponse } from "msw";
import type { OutboxEvent, OutboxStats } from "@/types/outbox";

let mockEvents: OutboxEvent[] = [
  {
    id: "evt-aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
    tenant_id: "tenant-1",
    aggregate_type: "document",
    aggregate_id: "doc-1",
    event_type: "vector.delete",
    payload: { collection: "kb_kb-1", filters: { document_id: ["doc-1"] } },
    status: "dead",
    attempts: 8,
    max_attempts: 8,
    last_error: "ConnectionError: milvus down",
    next_attempt_at: new Date().toISOString(),
    created_at: new Date(Date.now() - 3600_000).toISOString(),
    completed_at: null,
    age_seconds: 3600,
  },
  {
    id: "evt-bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb",
    tenant_id: "tenant-2",
    aggregate_type: "knowledge_base",
    aggregate_id: "kb-9",
    event_type: "vector.drop_collection",
    payload: { collection: "kb_kb-9" },
    status: "dead",
    attempts: 8,
    max_attempts: 8,
    last_error: "TimeoutError",
    next_attempt_at: new Date().toISOString(),
    created_at: new Date(Date.now() - 7200_000).toISOString(),
    completed_at: null,
    age_seconds: 7200,
  },
];

const stats: OutboxStats = {
  pending_count: 0,
  in_progress_count: 0,
  done_count: 100,
  dead_count: 2,
  oldest_pending_age_seconds: null,
};

export const outboxHandlers = [
  http.get("*/api/v1/admin/outbox/dead-letter", ({ request }) => {
    const url = new URL(request.url);
    const eventType = url.searchParams.get("event_type");
    const tenantId = url.searchParams.get("tenant_id");
    let events = [...mockEvents];
    if (eventType) events = events.filter((e) => e.event_type === eventType);
    if (tenantId) events = events.filter((e) => e.tenant_id === tenantId);
    return HttpResponse.json(events);
  }),
  http.get("*/api/v1/admin/outbox/stats", () => {
    return HttpResponse.json({
      ...stats,
      dead_count: mockEvents.length,
    });
  }),
  http.post(
    "*/api/v1/admin/outbox/dead-letter/:id/retry",
    ({ params }) => {
      const evt = mockEvents.find((e) => e.id === params.id);
      if (!evt) {
        return HttpResponse.json({ detail: "not found" }, { status: 404 });
      }
      evt.status = "pending";
      evt.attempts = 0;
      mockEvents = mockEvents.filter((e) => e.id !== params.id);
      return HttpResponse.json(evt);
    },
  ),
  http.post(
    "*/api/v1/admin/outbox/dead-letter/bulk-retry",
    () => {
      const ids = mockEvents.map((e) => e.id);
      mockEvents = [];
      return HttpResponse.json({
        requeued_count: ids.length,
        event_ids: ids,
      });
    },
  ),
  http.delete("*/api/v1/admin/outbox/dead-letter/:id", ({ params }) => {
    mockEvents = mockEvents.filter((e) => e.id !== params.id);
    return new HttpResponse(null, { status: 204 });
  }),
];

/** Reset mock state between tests */
export function resetOutboxMocks(): void {
  mockEvents = [
    {
      id: "evt-aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa",
      tenant_id: "tenant-1",
      aggregate_type: "document",
      aggregate_id: "doc-1",
      event_type: "vector.delete",
      payload: { collection: "kb_kb-1", filters: { document_id: ["doc-1"] } },
      status: "dead",
      attempts: 8,
      max_attempts: 8,
      last_error: "ConnectionError: milvus down",
      next_attempt_at: new Date().toISOString(),
      created_at: new Date(Date.now() - 3600_000).toISOString(),
      completed_at: null,
      age_seconds: 3600,
    },
    {
      id: "evt-bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb",
      tenant_id: "tenant-2",
      aggregate_type: "knowledge_base",
      aggregate_id: "kb-9",
      event_type: "vector.drop_collection",
      payload: { collection: "kb_kb-9" },
      status: "dead",
      attempts: 8,
      max_attempts: 8,
      last_error: "TimeoutError",
      next_attempt_at: new Date().toISOString(),
      created_at: new Date(Date.now() - 7200_000).toISOString(),
      completed_at: null,
      age_seconds: 7200,
    },
  ];
}
