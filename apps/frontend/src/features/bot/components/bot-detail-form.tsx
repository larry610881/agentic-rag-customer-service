import { useState, useEffect, useCallback } from "react";
import { useForm, Controller, type UseFormRegister } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Copy, Check, ChevronRight, Globe } from "lucide-react";
import { apiFetch } from "@/lib/api-client";
import { useTenants } from "@/hooks/queries/use-tenants";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { PUBLIC_API_URL } from "@/lib/api-config";
import { queryKeys } from "@/hooks/queries/keys";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
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
import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import { AvatarPreview } from "./avatar-preview";
import { ModelSelect } from "./model-select";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import type { Bot, UpdateBotRequest } from "@/types/bot";
import type { McpToolInfo } from "@/types/mcp";
import { useAuthStore } from "@/stores/use-auth-store";
import { McpBindingsSection } from "./mcp-bindings-section";
import { useSystemPrompts } from "@/hooks/queries/use-system-prompts";

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
  audit_mode: z.enum(["off", "minimal", "full"]),
  eval_provider: z.string().optional(),
  eval_model: z.string().optional(),
  eval_depth: z.string(),
  mcp_servers: z.array(z.object({
    url: z.string(),
    name: z.string(),
    enabled_tools: z.array(z.string()),
    tools: z.array(z.object({ name: z.string(), description: z.string() })).default([]),
    version: z.string().default(""),
  })),
  max_tool_calls: z.coerce.number().int().min(1).max(20),
  base_prompt: z.string().default(""),
  router_prompt: z.string().default(""),
  react_prompt: z.string().default(""),
  widget_enabled: z.boolean().default(false),
  widget_allowed_origins: z.string().default(""),
  widget_keep_history: z.boolean().default(true),
  avatar_type: z.enum(["none", "live2d", "vrm"]).default("none"),
  avatar_model_url: z.string().default(""),
  widget_welcome_message: z.string().max(500).default(""),
  widget_placeholder_text: z.string().max(200).default(""),
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

interface AvatarPreset {
  name: string;
  label: string;
  type: "live2d" | "vrm";
  url: string;
}

const TAB_KEYS = {
  KNOWLEDGE: "knowledge",
  PROMPT: "prompt",
  LLM: "llm",
  WIDGET: "widget",
  LINE: "line",
} as const;

function WebhookCopyButton({ url, label = "Webhook URL" }: { url: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(url);
    toast.success(`已複製${label}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [url, label]);

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      onClick={handleCopy}
      aria-label={`複製 ${label}`}
    >
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}

function PromptOverrideField({
  id,
  label,
  description,
  register,
  fieldName,
  systemDefault,
}: {
  id: string;
  label: string;
  description: string;
  register: UseFormRegister<BotFormValues>;
  fieldName: "base_prompt" | "router_prompt" | "react_prompt";
  systemDefault?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const placeholder = systemDefault
    ? systemDefault.slice(0, 80) + (systemDefault.length > 80 ? "..." : "")
    : "";

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <Label htmlFor={id}>
          {label}（{description}）
        </Label>
        {systemDefault && (
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setExpanded(!expanded)}
          >
            <ChevronRight
              className={`h-3 w-3 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}
            />
            查看目前系統預設
          </button>
        )}
        {expanded && systemDefault && (
          <pre className="whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs text-muted-foreground max-h-40 overflow-y-auto">
            {systemDefault}
          </pre>
        )}
      </div>
      <Textarea
        id={id}
        {...register(fieldName)}
        rows={5}
        placeholder={placeholder}
      />
    </section>
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
  const { data: systemPrompts } = useSystemPrompts();
  const [activeTab, setActiveTab] = useState<string>(TAB_KEYS.KNOWLEDGE);

  // Tenant permission check for agent modes
  const tenantId = useAuthStore((s) => s.tenantId);
  const token = useAuthStore((s) => s.token);
  const { data: fetchedTenants } = useTenants();
  const currentTenant = fetchedTenants?.find((t) => t.id === tenantId);
  const allowedModes = currentTenant?.allowed_agent_modes ?? ["router"];
  const allowedWidgetAvatar = currentTenant?.allowed_widget_avatar ?? false;

  const { data: avatarPresets } = useQuery({
    queryKey: queryKeys.bots.avatarPresets,
    queryFn: async () => {
      const raw = await apiFetch<Record<string, Omit<AvatarPreset, "name">>>(
        API_ENDPOINTS.bots.avatarPresets,
        {},
        token ?? undefined,
      );
      return Object.entries(raw).map(([name, preset]) => ({
        name,
        ...preset,
      }));
    },
    enabled: !!token,
  });

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
      mcp_servers: bot.mcp_servers ?? [],
      max_tool_calls: bot.max_tool_calls ?? 5,
      base_prompt: bot.base_prompt ?? "",
      router_prompt: bot.router_prompt ?? "",
      react_prompt: bot.react_prompt ?? "",
      widget_enabled: bot.widget_enabled ?? false,
      widget_allowed_origins: (bot.widget_allowed_origins ?? []).join("\n"),
      widget_keep_history: bot.widget_keep_history ?? true,
      avatar_type: bot.avatar_type ?? "none",
      avatar_model_url: bot.avatar_model_url ?? "",
      widget_welcome_message: bot.widget_welcome_message ?? "",
      widget_placeholder_text: bot.widget_placeholder_text ?? "",
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    },
  });

  const enabledTools = watch("enabled_tools") ?? [];
  const agentMode = watch("agent_mode");
  const mcpServers = watch("mcp_servers") ?? [];

  // MCP server tools metadata (shared with McpBindingsSection)
  const [serverToolsMap, setServerToolsMap] = useState<Record<string, McpToolInfo[]>>({});

  // Initialize serverToolsMap from persisted server.tools (no auto-discover).
  useEffect(() => {
    for (const server of bot.mcp_servers ?? []) {
      if (!serverToolsMap[server.url]) {
        const toolsMeta: McpToolInfo[] = server.tools?.length
          ? server.tools.map((t) => ({ name: t.name, description: t.description, parameters: [] }))
          : server.enabled_tools.map((name) => ({ name, description: "", parameters: [] }));
        setServerToolsMap((prev) => ({ ...prev, [server.url]: toolsMeta }));
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bot.mcp_servers]);

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
      mcp_servers: bot.mcp_servers ?? [],
      max_tool_calls: bot.max_tool_calls ?? 5,
      base_prompt: bot.base_prompt ?? "",
      router_prompt: bot.router_prompt ?? "",
      react_prompt: bot.react_prompt ?? "",
      widget_enabled: bot.widget_enabled ?? false,
      widget_allowed_origins: (bot.widget_allowed_origins ?? []).join("\n"),
      widget_keep_history: bot.widget_keep_history ?? true,
      avatar_type: bot.avatar_type ?? "none",
      avatar_model_url: bot.avatar_model_url ?? "",
      widget_welcome_message: bot.widget_welcome_message ?? "",
      widget_placeholder_text: bot.widget_placeholder_text ?? "",
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
    // Convert widget_allowed_origins from newline-separated string to array
    const originsStr = data.widget_allowed_origins as string;
    const payload = {
      ...data,
      widget_allowed_origins: originsStr
        ? originsStr.split("\n").map((s) => s.trim()).filter(Boolean)
        : [],
    };
    try {
      await onSave(payload);
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
          <TabsTrigger value={TAB_KEYS.WIDGET} className="flex-1">
            Widget
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
                      <SelectItem
                        value="react"
                        disabled={!allowedModes.includes("react")}
                      >
                        ReAct（RAG + Tools）{!allowedModes.includes("react") && " — 租戶未啟用"}
                      </SelectItem>
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
                      <SelectItem value="off">Off（不記錄）</SelectItem>
                      <SelectItem value="minimal">Minimal（基本記錄）</SelectItem>
                      <SelectItem value="full">Full（完整記錄含 input/output）</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              <p className="text-xs text-muted-foreground">
                Off 模式不記錄任何工具呼叫；Full 模式會記錄輸入參數和輸出結果
              </p>
            </div>
          </section>

          {/* RAG Evaluation 設定 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">RAG 品質評估</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-eval-model">評估用模型</Label>
              <ModelSelect
                id="bot-eval-model"
                value={
                  watch("eval_provider") && watch("eval_model")
                    ? `${watch("eval_provider")}:${watch("eval_model")}`
                    : ""
                }
                onValueChange={(v) => {
                  if (v === "__none__") {
                    setValue("eval_provider", "");
                    setValue("eval_model", "");
                  } else {
                    const [provider, ...modelParts] = v.split(":");
                    setValue("eval_provider", provider);
                    setValue("eval_model", modelParts.join(":"));
                  }
                }}
                enabledModels={enabledModels}
                allowEmpty
                placeholder="選擇評估模型（可不選）"
              />
              <p className="text-xs text-muted-foreground">
                未選擇模型時不執行 RAG 品質評估
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label>評估維度</Label>
              <Controller
                name="eval_depth"
                control={control}
                render={({ field }) => {
                  const layers = field.value && field.value !== "off"
                    ? field.value.split("+")
                    : [];
                  const toggle = (layer: string) => {
                    const next = layers.includes(layer)
                      ? layers.filter((l) => l !== layer)
                      : [...layers, layer].sort();
                    field.onChange(next.length > 0 ? next.join("+") : "off");
                  };
                  return (
                    <div className="flex flex-col gap-2">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={layers.includes("L1")}
                          onChange={() => toggle("L1")}
                          className="rounded border-input"
                        />
                        L1 — 檢索品質（Context Precision / Recall）
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={layers.includes("L2")}
                          onChange={() => toggle("L2")}
                          className="rounded border-input"
                        />
                        L2 — 回答品質（Faithfulness / Relevancy）
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={layers.includes("L3")}
                          onChange={() => toggle("L3")}
                          className="rounded border-input"
                        />
                        L3 — Agent 決策品質（僅 ReAct 模式）
                      </label>
                    </div>
                  );
                }}
              />
              <p className="text-xs text-muted-foreground">
                未勾選任何維度或未選擇評估模型時，不會執行 RAG 品質評估。
                MCP-only 場景會自動跳過 L1（無檢索語義）。
              </p>
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
            <McpBindingsSection
              mcpServers={mcpServers}
              onMcpServersChange={(servers) => setValue("mcp_servers", servers)}
              serverToolsMap={serverToolsMap}
              setServerToolsMap={setServerToolsMap}
              registerMaxToolCalls={register("max_tool_calls")}
              maxToolCallsError={errors.max_tool_calls?.message}
            />
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
        <TabsContent value={TAB_KEYS.PROMPT} className="flex flex-col gap-6 pt-4">
          {/* 自訂指令 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">自訂指令</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-system-prompt">Bot 自訂指令</Label>
              <Textarea
                id="bot-system-prompt"
                {...register("system_prompt")}
                rows={6}
                placeholder="輸入此機器人的自訂指令..."
              />
              <p className="text-xs text-muted-foreground">
                此指令會附加在系統提示詞最後，用於定義 Bot 的個性、語調等。
              </p>
            </div>
          </section>

          {/* 基礎 Prompt */}
          <PromptOverrideField
            id="bot-base-prompt"
            label="基礎 Prompt"
            description="留空則採用系統預設"
            register={register}
            fieldName="base_prompt"
            systemDefault={systemPrompts?.base_prompt}
          />

          {/* Router 模式 Prompt */}
          <PromptOverrideField
            id="bot-router-prompt"
            label="Router 模式 Prompt"
            description="留空則採用系統預設"
            register={register}
            fieldName="router_prompt"
            systemDefault={systemPrompts?.router_mode_prompt}
          />

          {/* ReAct 模式 Prompt */}
          <PromptOverrideField
            id="bot-react-prompt"
            label="ReAct 模式 Prompt"
            description="留空則採用系統預設"
            register={register}
            fieldName="react_prompt"
            systemDefault={systemPrompts?.react_mode_prompt}
          />
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
                    <ModelSelect
                      id="bot-llm-model"
                      value={selectValue}
                      onValueChange={(v) => {
                        const [provider, ...modelParts] = v.split(":");
                        const model = modelParts.join(":");
                        setValue("llm_provider", provider);
                        field.onChange(model);
                      }}
                      enabledModels={enabledModels}
                    />
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

        {/* Tab 4: Widget 設定 */}
        <TabsContent value={TAB_KEYS.WIDGET} className="flex flex-col gap-6 pt-4">
          {/* Widget 開關 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Web Widget</h3>
            <p className="text-sm text-muted-foreground">
              啟用後，外部網站可嵌入聊天機器人。
            </p>
            <Controller
              name="widget_enabled"
              control={control}
              render={({ field }) => (
                <div className="flex items-center gap-3">
                  <Switch
                    id="widget-enabled"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                  <Label htmlFor="widget-enabled">
                    {field.value ? "已啟用" : "未啟用"}
                  </Label>
                </div>
              )}
            />
          </section>

          {/* 允許來源 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">允許來源</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="widget-origins">
                允許的網域（每行一個）
              </Label>
              <Textarea
                id="widget-origins"
                {...register("widget_allowed_origins")}
                rows={4}
                placeholder={"https://shop.example.com\nhttps://www.example.com"}
              />
              <p className="text-xs text-muted-foreground">
                只有在此清單中的網域可以呼叫 Widget API。留空則不允許任何來源。
              </p>
            </div>
          </section>

          {/* 對話歷史保留 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">對話歷史</h3>
            <Controller
              name="widget_keep_history"
              control={control}
              render={({ field }) => (
                <div className="flex items-center gap-3">
                  <Switch
                    id="widget-keep-history"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                  <Label htmlFor="widget-keep-history">
                    {field.value ? "保留對話歷史" : "每次獨立對話"}
                  </Label>
                </div>
              )}
            />
            <p className="text-sm text-muted-foreground">
              關閉後，每次對話都是獨立的，適合純 FAQ 場景。
            </p>
          </section>

          {/* Avatar 角色選擇 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Avatar 角色選擇</h3>
            <Controller
              name="avatar_type"
              control={control}
              render={({ field: avatarField }) => {
                // Build a combined select value for preset matching
                const avatarUrl = watch("avatar_model_url");
                const selectValue = (() => {
                  if (avatarField.value === "none") return "__none__";
                  // Check if current URL matches a preset
                  const matched = avatarPresets?.find(
                    (p) => p.type === avatarField.value && p.url === avatarUrl,
                  );
                  if (matched) return `preset:${matched.name}`;
                  return "__custom__";
                })();

                return (
                  <div className="flex flex-col gap-3">
                    <Select
                      value={selectValue}
                      onValueChange={(v) => {
                        if (v === "__none__") {
                          avatarField.onChange("none");
                          setValue("avatar_model_url", "");
                        } else if (v === "__custom__") {
                          avatarField.onChange("vrm");
                          setValue("avatar_model_url", "");
                        } else if (v.startsWith("preset:")) {
                          const presetName = v.replace("preset:", "");
                          const preset = avatarPresets?.find((p) => p.name === presetName);
                          if (preset) {
                            avatarField.onChange(preset.type);
                            setValue("avatar_model_url", preset.url);
                          }
                        }
                      }}
                      disabled={!allowedWidgetAvatar}
                    >
                      <SelectTrigger className="w-64">
                        <SelectValue placeholder="選擇角色" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">無角色</SelectItem>
                        {avatarPresets?.map((preset) => (
                          <SelectItem
                            key={preset.name}
                            value={`preset:${preset.name}`}
                          >
                            {preset.label}
                          </SelectItem>
                        ))}
                        <SelectItem value="__custom__">自訂 URL（進階）</SelectItem>
                      </SelectContent>
                    </Select>
                    {!allowedWidgetAvatar && (
                      <p className="text-xs text-muted-foreground">
                        租戶未啟用此功能，請聯絡系統管理員開啟 Widget Avatar 權限。
                      </p>
                    )}
                    {selectValue === "__custom__" && (
                      <div className="flex flex-col gap-2">
                        <Label htmlFor="avatar-model-url">模型 URL</Label>
                        <Input
                          id="avatar-model-url"
                          {...register("avatar_model_url")}
                          placeholder="https://example.com/model.vrm"
                        />
                      </div>
                    )}
                    {allowedWidgetAvatar && (
                      <AvatarPreview
                        avatarType={watch("avatar_type") as "none" | "live2d" | "vrm"}
                        avatarModelUrl={watch("avatar_model_url") || ""}
                      />
                    )}
                  </div>
                );
              }}
            />
          </section>

          {/* 歡迎訊息 + Placeholder */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Widget 文字設定</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="widget-welcome-msg">歡迎訊息</Label>
              <Input
                id="widget-welcome-msg"
                {...register("widget_welcome_message")}
                placeholder="你好！有什麼可以幫你的嗎？"
                maxLength={500}
              />
              {errors.widget_welcome_message && (
                <p className="text-sm text-destructive">
                  {errors.widget_welcome_message.message}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Widget 開啟時顯示的歡迎訊息（最多 500 字）
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="widget-placeholder">輸入框提示文字</Label>
              <Input
                id="widget-placeholder"
                {...register("widget_placeholder_text")}
                placeholder="請輸入訊息..."
                maxLength={200}
              />
              {errors.widget_placeholder_text && (
                <p className="text-sm text-destructive">
                  {errors.widget_placeholder_text.message}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Widget 輸入框的 placeholder 文字（最多 200 字）
              </p>
            </div>
          </section>

          {/* 嵌入碼預覽 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">嵌入碼</h3>
            <div className="flex flex-col gap-2">
              <div className="flex items-start gap-2">
                <pre className="flex-1 whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs font-mono select-all">
                  {`<script src="${PUBLIC_API_URL}/static/widget.js"\n        data-bot="${bot.short_code}"\n        data-theme="light">\n</script>`}
                </pre>
                <WebhookCopyButton
                  url={`<script src="${PUBLIC_API_URL}/static/widget.js"\n        data-bot="${bot.short_code}"\n        data-theme="light">\n</script>`}
                  label="嵌入碼"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                將此程式碼貼入外部網站的 HTML 即可嵌入聊天機器人。
              </p>
            </div>
          </section>
        </TabsContent>

        {/* Tab 5: LINE 頻道 */}
        <TabsContent value={TAB_KEYS.LINE} className="flex flex-col gap-6 pt-4">
          {/* Webhook URL */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">Webhook URL</h3>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Input
                  readOnly
                  value={`${PUBLIC_API_URL}/api/v1/webhook/line/${bot.short_code}`}
                  className="font-mono text-sm"
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                />
                <WebhookCopyButton
                  url={`${PUBLIC_API_URL}/api/v1/webhook/line/${bot.short_code}`}
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
