import { useState, useEffect, useCallback } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Copy, Check, Search, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { PROVIDER_LABELS } from "@/types/provider-setting";
import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import type { Bot, UpdateBotRequest } from "@/types/bot";
import { useDiscoverMcpTools } from "@/hooks/queries/use-mcp";
import type { McpToolInfo } from "@/types/mcp";

const AVAILABLE_TOOLS = [
  { value: "rag_query", label: "知識庫查詢" },
] as const;

const botFormSchema = z.object({
  name: z.string().min(1, "請輸入名稱"),
  description: z.string().optional(),
  is_active: z.boolean(),
  system_prompt: z.string().optional(),
  knowledge_base_ids: z.array(z.string()),
  enabled_tools: z.array(z.string()),
  llm_provider: z.string().optional(),
  llm_model: z.string().optional(),
  temperature: z.coerce.number().min(0).max(1),
  max_tokens: z.coerce.number().int().min(128).max(4096),
  history_limit: z.coerce.number().int().min(0).max(35),
  frequency_penalty: z.coerce.number().min(0).max(1),
  reasoning_effort: z.enum(["low", "medium", "high"]),
  rag_top_k: z.coerce.number().int().min(1).max(20),
  rag_score_threshold: z.coerce.number().min(0).max(1),
  show_sources: z.boolean(),
  agent_mode: z.enum(["router", "react"]),
  audit_mode: z.enum(["minimal", "full"]),
  eval_provider: z.string().optional(),
  eval_model: z.string().optional(),
  eval_depth: z.enum(["L1", "L1+L2", "L1+L2+L3"]),
  mcp_server_url: z.string().nullable().optional(),
  mcp_enabled_tools: z.array(z.string()),
  max_tool_calls: z.coerce.number().int().min(1).max(20),
  line_channel_secret: z.string().nullable().optional(),
  line_channel_access_token: z.string().nullable().optional(),
});

type BotFormValues = z.infer<typeof botFormSchema>;

interface BotDetailFormProps {
  bot: Bot;
  onSave: (data: UpdateBotRequest) => Promise<void>;
  onDelete: () => void;
  isSaving: boolean;
  isDeleting: boolean;
}

const TAB_KEYS = {
  KNOWLEDGE: "knowledge",
  PROMPT: "prompt",
  LLM: "llm",
  LINE: "line",
} as const;

function WebhookCopyButton({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(url);
    toast.success("已複製 Webhook URL");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [url]);

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      onClick={handleCopy}
      aria-label="複製 Webhook URL"
    >
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}

export function BotDetailForm({
  bot,
  onSave,
  onDelete,
  isSaving,
  isDeleting,
}: BotDetailFormProps) {
  const { data: knowledgeBases } = useKnowledgeBases();
  const { data: enabledModels } = useEnabledModels();
  const [activeTab, setActiveTab] = useState<string>(TAB_KEYS.KNOWLEDGE);

  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<BotFormValues>({
    resolver: zodResolver(botFormSchema),
    defaultValues: {
      name: bot.name,
      description: bot.description,
      is_active: bot.is_active,
      system_prompt: bot.system_prompt,
      knowledge_base_ids: bot.knowledge_base_ids,
      enabled_tools: bot.enabled_tools,
      llm_provider: bot.llm_provider,
      llm_model: bot.llm_model,
      temperature: bot.temperature,
      max_tokens: bot.max_tokens,
      history_limit: bot.history_limit,
      frequency_penalty: bot.frequency_penalty,
      reasoning_effort: bot.reasoning_effort,
      rag_top_k: bot.rag_top_k,
      rag_score_threshold: bot.rag_score_threshold,
      show_sources: bot.show_sources,
      agent_mode: bot.agent_mode ?? "router",
      audit_mode: bot.audit_mode ?? "minimal",
      eval_provider: bot.eval_provider ?? "",
      eval_model: bot.eval_model ?? "",
      eval_depth: bot.eval_depth ?? "L1",
      mcp_server_url: bot.mcp_server_url,
      mcp_enabled_tools: bot.mcp_enabled_tools ?? [],
      max_tool_calls: bot.max_tool_calls ?? 5,
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    },
  });

  const enabledTools = watch("enabled_tools") ?? [];
  const agentMode = watch("agent_mode");
  const mcpServerUrl = watch("mcp_server_url");

  // MCP Discovery state
  const [discoveredTools, setDiscoveredTools] = useState<McpToolInfo[]>([]);
  const discoverMcp = useDiscoverMcpTools();

  const handleDiscoverTools = useCallback(async () => {
    if (!mcpServerUrl) {
      toast.error("請先輸入 MCP Server URL");
      return;
    }
    try {
      const result = await discoverMcp.mutateAsync(mcpServerUrl);
      setDiscoveredTools(result.tools);
      // Select all tools by default
      const allToolNames = result.tools.map((t) => t.name);
      setValue("mcp_enabled_tools", allToolNames);
      toast.success(`發現 ${result.tools.length} 個 Tools（${result.server_name}）`);
    } catch {
      toast.error("無法連線 MCP Server");
      setDiscoveredTools([]);
    }
  }, [mcpServerUrl, discoverMcp, setValue]);

  useEffect(() => {
    reset({
      name: bot.name,
      description: bot.description,
      is_active: bot.is_active,
      system_prompt: bot.system_prompt,
      knowledge_base_ids: bot.knowledge_base_ids,
      enabled_tools: bot.enabled_tools,
      llm_provider: bot.llm_provider,
      llm_model: bot.llm_model,
      temperature: bot.temperature,
      max_tokens: bot.max_tokens,
      history_limit: bot.history_limit,
      frequency_penalty: bot.frequency_penalty,
      reasoning_effort: bot.reasoning_effort,
      rag_top_k: bot.rag_top_k,
      rag_score_threshold: bot.rag_score_threshold,
      show_sources: bot.show_sources,
      agent_mode: bot.agent_mode ?? "router",
      audit_mode: bot.audit_mode ?? "minimal",
      eval_provider: bot.eval_provider ?? "",
      eval_model: bot.eval_model ?? "",
      eval_depth: bot.eval_depth ?? "L1",
      mcp_server_url: bot.mcp_server_url,
      mcp_enabled_tools: bot.mcp_enabled_tools ?? [],
      max_tool_calls: bot.max_tool_calls ?? 5,
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    });
  }, [bot, reset]);

  const onSubmit = async (data: BotFormValues) => {
    // rag_query is always enabled
    data.enabled_tools = ["rag_query"];
    // Validation: rag_query requires at least one knowledge base
    if (data.knowledge_base_ids.length === 0) {
      toast.error("請至少綁定一個知識庫");
      setActiveTab(TAB_KEYS.KNOWLEDGE);
      return;
    }
    try {
      await onSave(data);
      toast.success("機器人設定已儲存");
    } catch {
      toast.error("儲存失敗，請稍後再試");
    }
  };

  /** Build the combined select value from provider + model */
  const currentModelValue =
    bot.llm_provider && bot.llm_model
      ? `${bot.llm_provider}:${bot.llm_model}`
      : "";

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      {/* Top section: basic info (always visible) */}
      <section className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-name">名稱</Label>
          <Input id="bot-name" {...register("name")} />
          {errors.name && (
            <p className="text-sm text-destructive">{errors.name.message}</p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-description">描述</Label>
          <Textarea id="bot-description" {...register("description")} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-active">狀態</Label>
          <Controller
            name="is_active"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value ? "active" : "inactive"}
                onValueChange={(v) => field.onChange(v === "active")}
              >
                <SelectTrigger id="bot-active" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">啟用</SelectItem>
                  <SelectItem value="inactive">停用</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>
      </section>

      {/* 4-Tab section */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full">
          <TabsTrigger value={TAB_KEYS.KNOWLEDGE} className="flex-1">
            RAG / Agent
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.PROMPT} className="flex-1">
            系統提示詞
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.LLM} className="flex-1">
            LLM 參數
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.LINE} className="flex-1">
            LINE 頻道
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: RAG 知識庫 */}
        <TabsContent value={TAB_KEYS.KNOWLEDGE} className="flex flex-col gap-6 pt-4">
          {/* Agent 模式 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Agent 模式</h3>
            <p className="text-sm text-muted-foreground">
              Router 使用純 RAG 查詢；ReAct 額外支援 MCP Tools（如資料庫查詢）。
            </p>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-agent-mode">模式</Label>
              <Controller
                name="agent_mode"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="bot-agent-mode" className="w-48">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="router">Router（純 RAG）</SelectItem>
                      <SelectItem value="react">ReAct（RAG + Tools）</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </section>

          {/* Audit 模式 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Audit 記錄模式</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-audit-mode">記錄模式</Label>
              <Controller
                name="audit_mode"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="bot-audit-mode" className="w-64">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="minimal">Minimal（基本記錄）</SelectItem>
                      <SelectItem value="full">Full（完整記錄含 input/output）</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              <p className="text-xs text-muted-foreground">
                Full 模式會記錄工具的輸入參數和輸出結果，適合除錯和品質分析
              </p>
            </div>
          </section>

          {/* RAG Evaluation 設定 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">RAG 品質評估</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-eval-provider">評估用 Provider</Label>
                <Input
                  id="bot-eval-provider"
                  {...register("eval_provider")}
                  placeholder="例: openai"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-eval-model">評估用 Model</Label>
                <Input
                  id="bot-eval-model"
                  {...register("eval_model")}
                  placeholder="例: gpt-4o-mini"
                />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-eval-depth">評估深度</Label>
              <Controller
                name="eval_depth"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="bot-eval-depth">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="L1">L1 — 檢索品質（Context Precision/Recall）</SelectItem>
                      <SelectItem value="L1+L2">L1+L2 — 加上回答品質（Faithfulness/Relevancy）</SelectItem>
                      <SelectItem value="L1+L2+L3">L1+L2+L3 — 加上 Agent 決策品質（僅 ReAct）</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </section>

          {/* 啟用工具 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">啟用工具</h3>
            <div className="flex flex-col gap-2">
              {AVAILABLE_TOOLS.map((tool) => (
                <label
                  key={tool.value}
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                >
                  <input
                    type="checkbox"
                    checked
                    disabled
                    className="rounded border-input"
                  />
                  {tool.label}（預設啟用）
                </label>
              ))}
            </div>
          </section>

          {/* 知識庫綁定 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">知識庫</h3>
            <div className="flex flex-col gap-2">
              <Label>已綁定的知識庫</Label>
              <Controller
                name="knowledge_base_ids"
                control={control}
                render={({ field }) => (
                  <div className="flex flex-col gap-2">
                    {knowledgeBases?.map((kb) => (
                      <label
                        key={kb.id}
                        className="flex items-center gap-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={field.value.includes(kb.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              field.onChange([...field.value, kb.id]);
                            } else {
                              field.onChange(
                                field.value.filter((id) => id !== kb.id),
                              );
                            }
                          }}
                          className="rounded border-input"
                        />
                        {kb.name}
                      </label>
                    ))}
                    {(!knowledgeBases || knowledgeBases.length === 0) && (
                      <p className="text-sm text-muted-foreground">
                        目前沒有可用的知識庫。
                      </p>
                    )}
                  </div>
                )}
              />
            </div>
          </section>

          {/* RAG 參數 (conditional) */}
          {enabledTools.includes("rag_query") && (
            <section className="flex flex-col gap-4">
              <h3 className="text-lg font-semibold">RAG 參數</h3>
              <p className="text-sm text-muted-foreground">
                設定知識庫查詢工具的檢索參數。
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="bot-rag-top-k">Top K（1-20）</Label>
                  <Input
                    id="bot-rag-top-k"
                    type="number"
                    min="1"
                    max="20"
                    {...register("rag_top_k")}
                  />
                  {errors.rag_top_k && (
                    <p className="text-sm text-destructive">
                      {errors.rag_top_k.message}
                    </p>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="bot-rag-score-threshold">
                    分數閾值（0-1）
                  </Label>
                  <Input
                    id="bot-rag-score-threshold"
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    {...register("rag_score_threshold")}
                  />
                  {errors.rag_score_threshold && (
                    <p className="text-sm text-destructive">
                      {errors.rag_score_threshold.message}
                    </p>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* MCP 設定 (ReAct 模式才顯示) */}
          {agentMode === "react" && (
            <section className="flex flex-col gap-4">
              <h3 className="text-lg font-semibold">MCP 設定</h3>
              <p className="text-sm text-muted-foreground">
                設定 ReAct 模式的 MCP Server 連線，探索可用的 Tools。
              </p>

              {/* URL + Discover Button */}
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-mcp-server-url">MCP Server URL</Label>
                <div className="flex gap-2">
                  <Input
                    id="bot-mcp-server-url"
                    {...register("mcp_server_url")}
                    placeholder="例如：http://localhost:9000/sse"
                    className="flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleDiscoverTools}
                    disabled={discoverMcp.isPending || !mcpServerUrl}
                  >
                    {discoverMcp.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Search className="mr-2 h-4 w-4" />
                    )}
                    探索 Tools
                  </Button>
                </div>
              </div>

              {/* Discovered Tools Checkbox List */}
              {discoveredTools.length > 0 && (
                <div className="flex flex-col gap-2">
                  <Label>可用 Tools</Label>
                  <Controller
                    name="mcp_enabled_tools"
                    control={control}
                    render={({ field }) => (
                      <div className="flex flex-col gap-2 rounded-md border p-3">
                        {discoveredTools.map((tool) => (
                          <label
                            key={tool.name}
                            className="flex items-start gap-2 text-sm"
                          >
                            <input
                              type="checkbox"
                              checked={field.value.includes(tool.name)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  field.onChange([...field.value, tool.name]);
                                } else {
                                  field.onChange(
                                    field.value.filter((n) => n !== tool.name),
                                  );
                                }
                              }}
                              className="mt-0.5 rounded border-input"
                            />
                            <div>
                              <span className="font-mono text-xs font-medium">
                                {tool.name}
                              </span>
                              <span className="ml-2 text-muted-foreground">
                                {tool.description.length > 60
                                  ? tool.description.slice(0, 60) + "..."
                                  : tool.description}
                              </span>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                  />
                </div>
              )}

              {/* Max Tool Calls */}
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-max-tool-calls">最大 Tool 呼叫次數（1-20）</Label>
                <Input
                  id="bot-max-tool-calls"
                  type="number"
                  min="1"
                  max="20"
                  className="w-32"
                  {...register("max_tool_calls")}
                />
                {errors.max_tool_calls && (
                  <p className="text-sm text-destructive">
                    {errors.max_tool_calls.message}
                  </p>
                )}
              </div>
            </section>
          )}

          {/* 回覆顯示設定 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">回覆顯示</h3>
            <Controller
              name="show_sources"
              control={control}
              render={({ field }) => (
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                    className="rounded border-input"
                  />
                  顯示資料來源
                </label>
              )}
            />
            <p className="text-sm text-muted-foreground">
              關閉後，對話回覆將不會顯示「參考來源」區塊。
            </p>
          </section>
        </TabsContent>

        {/* Tab 2: 系統提示詞 */}
        <TabsContent value={TAB_KEYS.PROMPT} className="flex flex-col gap-4 pt-4">
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">系統提示詞</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-system-prompt">自訂系統提示詞</Label>
              <Textarea
                id="bot-system-prompt"
                {...register("system_prompt")}
                rows={10}
                placeholder="輸入此機器人的自訂系統提示詞..."
              />
            </div>
          </section>
        </TabsContent>

        {/* Tab 3: LLM 參數 */}
        <TabsContent value={TAB_KEYS.LLM} className="flex flex-col gap-6 pt-4">
          {/* LLM 模型選擇 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">LLM 模型</h3>
            <p className="text-sm text-muted-foreground">
              選擇此機器人使用的 LLM 模型。可用模型由「系統設定 &gt; 供應商設定」管理。
            </p>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-llm-model">模型</Label>
              <Controller
                name="llm_model"
                control={control}
                render={({ field }) => {
                  const selectValue =
                    watch("llm_provider") && field.value
                      ? `${watch("llm_provider")}:${field.value}`
                      : currentModelValue;

                  return (
                    <Select
                      value={selectValue || undefined}
                      onValueChange={(v) => {
                        const [provider, ...modelParts] = v.split(":");
                        const model = modelParts.join(":");
                        setValue("llm_provider", provider);
                        field.onChange(model);
                      }}
                    >
                      <SelectTrigger id="bot-llm-model">
                        <SelectValue placeholder="請選擇模型" />
                      </SelectTrigger>
                      <SelectContent>
                        {enabledModels && enabledModels.length > 0 ? (
                          Object.entries(
                            enabledModels.reduce<
                              Record<
                                string,
                                typeof enabledModels
                              >
                            >((groups, m) => {
                              (groups[m.provider_name] ??= []).push(m);
                              return groups;
                            }, {}),
                          ).map(([provider, models]) => (
                            <SelectGroup key={provider}>
                              <SelectLabel>
                                {PROVIDER_LABELS[provider] ?? provider}
                              </SelectLabel>
                              {models.map((m) => (
                                <SelectItem
                                  key={`${m.provider_name}:${m.model_id}`}
                                  value={`${m.provider_name}:${m.model_id}`}
                                >
                                  {m.display_name} ({m.price})
                                </SelectItem>
                              ))}
                            </SelectGroup>
                          ))
                        ) : (
                          <SelectItem value="__none__" disabled>
                            尚未啟用任何模型
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                  );
                }}
              />
            </div>
          </section>

          {/* LLM 參數 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">LLM 參數</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-temperature">溫度（0-1）</Label>
                <Input
                  id="bot-temperature"
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  {...register("temperature")}
                />
                {errors.temperature && (
                  <p className="text-sm text-destructive">
                    {errors.temperature.message}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-max-tokens">最大 Token 數（128-4096）</Label>
                <Input
                  id="bot-max-tokens"
                  type="number"
                  min="128"
                  max="4096"
                  {...register("max_tokens")}
                />
                {errors.max_tokens && (
                  <p className="text-sm text-destructive">
                    {errors.max_tokens.message}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-history-limit">歷史訊息數（0-35）</Label>
                <Input
                  id="bot-history-limit"
                  type="number"
                  min="0"
                  max="35"
                  {...register("history_limit")}
                />
                {errors.history_limit && (
                  <p className="text-sm text-destructive">
                    {errors.history_limit.message}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-frequency-penalty">
                  頻率懲罰（0-1）
                </Label>
                <Input
                  id="bot-frequency-penalty"
                  type="number"
                  step="0.1"
                  min="0"
                  max="1"
                  {...register("frequency_penalty")}
                />
                {errors.frequency_penalty && (
                  <p className="text-sm text-destructive">
                    {errors.frequency_penalty.message}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-reasoning-effort">推理強度</Label>
                <Controller
                  name="reasoning_effort"
                  control={control}
                  render={({ field }) => (
                    <Select value={field.value} onValueChange={field.onChange}>
                      <SelectTrigger id="bot-reasoning-effort">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">低</SelectItem>
                        <SelectItem value="medium">中</SelectItem>
                        <SelectItem value="high">高</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </div>
            </div>
          </section>
        </TabsContent>

        {/* Tab 4: LINE 頻道 */}
        <TabsContent value={TAB_KEYS.LINE} className="flex flex-col gap-6 pt-4">
          {/* Webhook URL */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Webhook URL</h3>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Input
                  readOnly
                  value={`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/webhook/line/${bot.short_code}`}
                  className="font-mono text-sm"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <WebhookCopyButton
                  url={`${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1/webhook/line/${bot.short_code}`}
                />
              </div>
              <p className="text-sm text-muted-foreground">
                將此 URL 貼至 LINE Developer Console 的 Webhook URL 設定。
              </p>
            </div>
          </section>

          {/* LINE 頻道密鑰 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">LINE 頻道</h3>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-line-secret">頻道密鑰</Label>
                <Input
                  id="bot-line-secret"
                  type="password"
                  {...register("line_channel_secret")}
                  placeholder="輸入 LINE 頻道密鑰"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-line-token">存取權杖</Label>
                <Input
                  id="bot-line-token"
                  type="password"
                  {...register("line_channel_access_token")}
                  placeholder="輸入 LINE 存取權杖"
                />
              </div>
            </div>
          </section>
        </TabsContent>
      </Tabs>

      {/* Bottom: action buttons (always visible) */}
      <div className="flex items-center justify-between">
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              type="button"
              variant="destructive"
              disabled={isDeleting}
            >
              {isDeleting ? "刪除中..." : "刪除機器人"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>確定要刪除機器人？</AlertDialogTitle>
              <AlertDialogDescription>
                確定要刪除機器人「{bot.name}」嗎？此操作無法復原。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={onDelete}>
                確定刪除
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "儲存中..." : "儲存變更"}
        </Button>
      </div>
    </form>
  );
}
