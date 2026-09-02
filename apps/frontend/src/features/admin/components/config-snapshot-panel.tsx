/** Issue #60 — 「當時生效設定」面板：依 hash 抓快照並分組顯示 */

import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format-date";
import { useConfigSnapshot } from "@/hooks/queries/use-config-snapshots";
import type { ConfigSnapshot } from "@/types/config-snapshot";
import { ConfigHashChip } from "./config-hash-chip";

interface ConfigSnapshotPanelProps {
  hash: string;
}

function Section({
  title,
  testId,
  children,
}: {
  title: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="space-y-2 rounded-lg border p-4"
      data-testid={testId}
    >
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 break-all">{value}</span>
    </div>
  );
}

function formatScalar(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value || "—";
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function BoolBadge({ value, yes = "啟用", no = "停用" }: { value: boolean; yes?: string; no?: string }) {
  return (
    <Badge variant={value ? "default" : "outline"} className="text-xs">
      {value ? yes : no}
    </Badge>
  );
}

function ListOrDash({ items }: { items: string[] }) {
  if (!items || items.length === 0) return <span>—</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {items.map((item) => (
        <Badge key={item} variant="secondary" className="font-mono text-xs">
          {item}
        </Badge>
      ))}
    </span>
  );
}

export function ConfigSnapshotContent({ snapshot }: { snapshot: ConfigSnapshot }) {
  const guard = snapshot.guard;
  const guardRules = guard?.input_rules ?? [];
  const llmParams = Object.entries(snapshot.llm_params ?? {});
  const extra = Object.entries(snapshot.extra ?? {});

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section title="提示詞" testId="snapshot-section-prompt">
        <div className="flex flex-wrap items-center gap-2">
          {snapshot.platform_prompt_fallback && (
            <Badge variant="outline" className="text-xs">
              使用平台預設提示詞
            </Badge>
          )}
          {snapshot.worker_name && (
            <Badge variant="secondary" className="text-xs">
              worker: {snapshot.worker_name}
            </Badge>
          )}
          <Badge variant="outline" className="text-xs">
            通路: {snapshot.channel || "—"}
          </Badge>
        </div>
        <pre
          data-testid="snapshot-system-prompt"
          className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-3 font-mono text-xs"
        >
          {snapshot.system_prompt || "（空）"}
        </pre>
      </Section>

      <Section title="模型與參數" testId="snapshot-section-model">
        <KV label="供應商" value={formatScalar(snapshot.llm_provider)} />
        <KV label="模型" value={formatScalar(snapshot.llm_model)} />
        <KV label="路由模型" value={formatScalar(snapshot.router_model)} />
        {llmParams.length > 0 ? (
          llmParams.map(([k, v]) => (
            <KV key={k} label={k} value={<span className="font-mono">{formatScalar(v)}</span>} />
          ))
        ) : (
          <KV label="參數" value="—" />
        )}
      </Section>

      <Section title="檢索" testId="snapshot-section-retrieval">
        <KV label="模式" value={<ListOrDash items={snapshot.retrieval?.modes ?? []} />} />
        <KV
          label="Rerank"
          value={
            <span className="flex flex-wrap items-center gap-2">
              <BoolBadge value={!!snapshot.retrieval?.rerank_enabled} />
              {snapshot.retrieval?.rerank_enabled && snapshot.retrieval.rerank_model && (
                <span className="font-mono text-xs">{snapshot.retrieval.rerank_model}</span>
              )}
              {snapshot.retrieval?.rerank_top_n != null && (
                <span className="text-xs text-muted-foreground">
                  top_n={snapshot.retrieval.rerank_top_n}
                </span>
              )}
            </span>
          }
        />
        <KV label="知識庫" value={<ListOrDash items={snapshot.retrieval?.kb_ids ?? []} />} />
        <KV
          label="快速道"
          value={
            snapshot.retrieval?.direct_retrieval == null ? (
              "—"
            ) : (
              <BoolBadge value={snapshot.retrieval.direct_retrieval} />
            )
          }
        />
      </Section>

      <Section title="工具" testId="snapshot-section-tools">
        <KV label="啟用工具" value={<ListOrDash items={snapshot.enabled_tools ?? []} />} />
        <KV label="最大工具呼叫" value={formatScalar(snapshot.max_tool_calls)} />
      </Section>

      <Section title="防護" testId="snapshot-section-guard">
        {guard ? (
          <>
            <KV
              label="輸入規則"
              value={
                <span className="space-y-1">
                  <span className="block">{guardRules.length} 條</span>
                  {guardRules.length > 0 && (
                    <ul className="space-y-0.5">
                      {guardRules.map((r) => (
                        <li key={r.id} className="flex items-start gap-2 text-xs">
                          <Badge
                            variant={r.enabled ? "secondary" : "outline"}
                            className="shrink-0 font-mono text-[10px]"
                          >
                            {r.id}
                          </Badge>
                          <code className="break-all text-muted-foreground">{r.pattern}</code>
                        </li>
                      ))}
                    </ul>
                  )}
                </span>
              }
            />
            <KV label="輸出關鍵字" value={<ListOrDash items={guard.output_keywords ?? []} />} />
            <KV label="攔截回覆" value={formatScalar(guard.blocked_response)} />
            <KV label="LLM 輸出防護" value={<BoolBadge value={guard.llm_guard_enabled} />} />
            <KV label="LLM 輸入防護" value={<BoolBadge value={guard.llm_input_guard_enabled} />} />
          </>
        ) : (
          <p className="text-sm text-muted-foreground">此設定未啟用防護</p>
        )}
      </Section>

      <Section title="記憶" testId="snapshot-section-memory">
        <KV label="長期記憶" value={<BoolBadge value={!!snapshot.memory_enabled} />} />
        {extra.map(([k, v]) => (
          <KV key={k} label={k} value={<span className="font-mono">{formatScalar(v)}</span>} />
        ))}
      </Section>
    </div>
  );
}

export function ConfigSnapshotPanel({ hash }: ConfigSnapshotPanelProps) {
  const { data, isLoading, error } = useConfigSnapshot(hash);

  if (isLoading) {
    return (
      <div className="space-y-3" data-testid="snapshot-loading">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <p className="text-sm text-destructive" data-testid="snapshot-error">
        {notFound
          ? "找不到此設定快照（可能已被清理）"
          : `載入設定快照失敗：${(error as Error).message}`}
      </p>
    );
  }

  if (!data) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="snapshot-error">
        找不到此設定快照
      </p>
    );
  }

  return (
    <div className="space-y-4" data-testid="config-snapshot-panel">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-muted-foreground">設定 hash</span>
        <ConfigHashChip hash={data.hash} copyable />
        <span className="text-xs text-muted-foreground">
          首次出現 {formatDateTime(data.first_seen_at)}
        </span>
        <Badge variant="outline" className="text-xs">
          schema v{String(data.schema)}
        </Badge>
      </div>
      <ConfigSnapshotContent snapshot={data.snapshot} />
    </div>
  );
}
