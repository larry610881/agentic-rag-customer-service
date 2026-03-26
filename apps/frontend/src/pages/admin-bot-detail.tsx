import { useParams, Link } from "react-router-dom";
import { useBot } from "@/hooks/queries/use-bots";
import { useTenantNameMap } from "@/hooks/use-tenant-name-map";
import { ROUTES } from "@/routes/paths";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[180px_1fr] gap-4 py-2 border-b last:border-b-0">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value ?? "-"}</dd>
    </div>
  );
}

function PromptField({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-muted-foreground">{label}</h4>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md border bg-muted/50 p-4 text-sm">
        {value}
      </pre>
    </div>
  );
}

export default function AdminBotDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: bot, isLoading, isError } = useBot(id!);
  const tenantNameMap = useTenantNameMap();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full rounded" />
      </div>
    );
  }

  if (isError || !bot) {
    return (
      <div className="p-6">
        <p className="text-destructive">找不到此機器人。</p>
      </div>
    );
  }

  const tenantName = tenantNameMap.get(bot.tenant_id) ?? bot.tenant_id.slice(0, 8);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center gap-2">
        <Link
          to={ROUTES.ADMIN_BOTS}
          className="text-sm text-muted-foreground hover:underline"
        >
          所有機器人
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="text-sm">{bot.name}</span>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-semibold">{bot.name}</h2>
          <Badge variant={bot.is_active ? "default" : "secondary"}>
            {bot.is_active ? "啟用" : "停用"}
          </Badge>
        </div>
        <Badge variant="outline">唯讀</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>總覽</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
            <div>
              <dt className="text-sm text-muted-foreground">租戶</dt>
              <dd className="mt-1 font-medium">{tenantName}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">LLM</dt>
              <dd className="mt-1 font-medium">{bot.llm_model || bot.llm_provider || "-"}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">建立時間</dt>
              <dd className="mt-1 font-medium">
                {new Date(bot.created_at).toLocaleDateString("zh-TW")}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Tabs defaultValue="basic">
        <TabsList>
          <TabsTrigger value="basic">基本設定</TabsTrigger>
          <TabsTrigger value="llm">LLM 參數</TabsTrigger>
          <TabsTrigger value="prompt">Prompt</TabsTrigger>
          <TabsTrigger value="mcp">MCP 工具</TabsTrigger>
          <TabsTrigger value="rag">RAG 設定</TabsTrigger>
        </TabsList>

        <TabsContent value="basic">
          <Card>
            <CardContent className="pt-6">
              <dl>
                <FieldRow label="名稱" value={bot.name} />
                <FieldRow label="說明" value={bot.description || "-"} />
                <FieldRow label="Short Code" value={bot.short_code} />
                <FieldRow
                  label="狀態"
                  value={
                    <Badge variant={bot.is_active ? "default" : "secondary"}>
                      {bot.is_active ? "啟用" : "停用"}
                    </Badge>
                  }
                />
                <FieldRow
                  label="啟用工具"
                  value={
                    bot.enabled_tools.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {bot.enabled_tools.map((t) => (
                          <Badge key={t} variant="outline">
                            {t}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      "-"
                    )
                  }
                />
                <FieldRow
                  label="顯示來源"
                  value={bot.show_sources ? "是" : "否"}
                />
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="llm">
          <Card>
            <CardContent className="pt-6">
              <dl>
                <FieldRow label="LLM Provider" value={bot.llm_provider || "-"} />
                <FieldRow label="LLM Model" value={bot.llm_model || "-"} />
                <FieldRow label="Temperature" value={bot.temperature} />
                <FieldRow label="Max Tokens" value={bot.max_tokens} />
                <FieldRow label="History Limit" value={bot.history_limit} />
                <FieldRow label="Frequency Penalty" value={bot.frequency_penalty} />
                <FieldRow label="Reasoning Effort" value={bot.reasoning_effort} />
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="prompt">
          <Card>
            <CardContent className="flex flex-col gap-6 pt-6">
              <PromptField label="Base Prompt" value={bot.base_prompt} />
              <PromptField label="System Prompt" value={bot.system_prompt} />
              {!bot.base_prompt &&
                !bot.system_prompt && (
                  <p className="text-muted-foreground">未設定任何 Prompt。</p>
                )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="mcp">
          <Card>
            <CardContent className="pt-6">
              {bot.mcp_servers.length === 0 ? (
                <p className="text-muted-foreground">未綁定 MCP 伺服器。</p>
              ) : (
                <div className="space-y-4">
                  {bot.mcp_servers.map((server, idx) => (
                    <div key={idx} className="rounded-md border p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{server.name}</span>
                        {server.version && (
                          <Badge variant="outline">v{server.version}</Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground break-all">
                        {server.url}
                      </p>
                      {server.tools.length > 0 && (
                        <div>
                          <p className="text-xs text-muted-foreground mb-1">
                            可用工具 ({server.tools.length})
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {server.tools.map((tool) => (
                              <Badge
                                key={tool.name}
                                variant={
                                  server.enabled_tools.includes(tool.name)
                                    ? "default"
                                    : "secondary"
                                }
                                title={tool.description}
                              >
                                {tool.name}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rag">
          <Card>
            <CardContent className="pt-6">
              <dl>
                <FieldRow label="RAG Top-K" value={bot.rag_top_k} />
                <FieldRow label="RAG Score Threshold" value={bot.rag_score_threshold} />
                <FieldRow
                  label="Knowledge Base IDs"
                  value={
                    bot.knowledge_base_ids.length > 0 ? (
                      <div className="flex flex-col gap-1">
                        {bot.knowledge_base_ids.map((kbId) => (
                          <code key={kbId} className="text-xs">
                            {kbId}
                          </code>
                        ))}
                      </div>
                    ) : (
                      "-"
                    )
                  }
                />
                <FieldRow label="Audit Mode" value={bot.audit_mode} />
                <FieldRow label="Eval Depth" value={bot.eval_depth || "-"} />
                <FieldRow label="Eval Provider" value={bot.eval_provider || "-"} />
                <FieldRow label="Eval Model" value={bot.eval_model || "-"} />
                <FieldRow label="Max Tool Calls" value={bot.max_tool_calls} />
              </dl>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
