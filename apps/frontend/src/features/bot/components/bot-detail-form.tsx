import { useState, useEffect, useCallback, useRef } from "react";
// HARDCODE - 地端模型 A/B 測試，正式上線前移除此 import
import { useOllamaAbPresets, useOllamaModelStatus } from "@/hooks/queries/use-ollama";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  ArrowRight,
  Copy,
  Check,
  ImageIcon,
  Plus,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "@/routes/paths";
import { API_BASE, PUBLIC_API_URL } from "@/lib/api-config";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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
import { ChevronDown } from "lucide-react";
import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import { useBuiltInTools } from "@/hooks/queries/use-built-in-tools";
import { ModelSelect } from "@/components/shared/model-select";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import type { Bot, ToolRagConfig, UpdateBotRequest } from "@/types/bot";
import type { McpToolInfo } from "@/types/mcp";
import { useAuthStore } from "@/stores/use-auth-store";
import { McpBindingsSection } from "./mcp-bindings-section";
import { WorkersSection } from "./workers-section";
import {
  ToolRagConfigSection,
  type ModelOption,
} from "./tool-rag-config-section";

/** Tools 需要 per-tool RAG 覆蓋 UI 的白名單 */
const RAG_TOOL_NAMES = ["rag_query", "query_dm_with_image"] as const;

const RERANK_MODEL_OPTIONS: ModelOption[] = [
  { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
];

const toolRagConfigSchema = z
  .object({
    rag_top_k: z.coerce.number().int().min(1).max(50).optional(),
    rag_score_threshold: z.coerce.number().min(0).max(1).optional(),
    rerank_enabled: z.boolean().optional(),
    rerank_model: z.string().optional(),
    rerank_top_n: z.coerce.number().int().min(5).max(50).optional(),
  })
  .partial();

const botFormSchema = z.object({
  name: z.string().min(1, "請輸入名稱"),
  description: z.string().optional(),
  is_active: z.boolean(),
  bot_prompt: z.string().optional(),
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
  eval_provider: z.string().optional(),
  eval_model: z.string().optional(),
  eval_depth: z.string(),
  mcp_servers: z.array(
    z.object({
      url: z.string(),
      name: z.string(),
      enabled_tools: z.array(z.string()),
      tools: z
        .array(z.object({ name: z.string(), description: z.string() }))
        .default([]),
      version: z.string().default(""),
    }),
  ),
  max_tool_calls: z.coerce.number().int().min(1).max(20),
  base_prompt: z.string().default(""),
  widget_enabled: z.boolean().default(false),
  widget_allowed_origins: z.string().default(""),
  widget_keep_history: z.boolean().default(true),
  widget_welcome_message: z.string().max(500).default(""),
  widget_placeholder_text: z.string().max(200).default(""),
  widget_greeting_messages: z.array(z.string().max(100)).default([]),
  widget_greeting_animation: z
    .enum(["fade", "slide", "typewriter"])
    .default("fade"),
  busy_reply_message: z
    .string()
    .max(500)
    .default("小編正在努力回覆中，請稍等一下喔～"),
  line_channel_secret: z.string().nullable().optional(),
  line_channel_access_token: z.string().nullable().optional(),
  line_show_sources: z.boolean().default(false),
  intent_routes: z
    .array(
      z.object({
        name: z.string().min(1, "請輸入名稱").max(50),
        description: z.string().min(1, "請輸入描述").max(500),
        bot_prompt: z.string().min(1, "請輸入提示詞").max(10000),
      }),
    )
    .max(10)
    .default([]),
  router_model: z.string().default(""),
  summary_model: z.string().default(""),
  rerank_enabled: z.boolean().default(false),
  rerank_model: z.string().default(""),
  rerank_top_n: z.coerce.number().int().min(5).max(50).default(20),
  tool_configs: z.record(z.string(), toolRagConfigSchema).default({}),
  customer_service_url: z.string().default(""),
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
  LLM_PROMPT: "llm-prompt",
  CAPABILITIES: "capabilities",
  SUBAGENT: "subagent",
  STUDIO: "studio",
  WIDGET: "widget",
  LINE: "line",
} as const;

function WebhookCopyButton({
  url,
  label = "Webhook URL",
}: {
  url: string;
  label?: string;
}) {
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

export function BotDetailForm({
  bot,
  onSave,
  onDelete,
  isSaving,
  isDeleting,
}: BotDetailFormProps) {
  const { data: kbData } = useKnowledgeBases();
  const { data: enabledModels } = useEnabledModels();
  const { data: builtInTools = [] } = useBuiltInTools();
  const [activeTab, setActiveTab] = useState<string>(TAB_KEYS.LLM_PROMPT);
  const navigate = useNavigate();

  // HARDCODE - 地端模型 A/B 測試狀態，正式上線前移除
  const { data: abPresets = [] } = useOllamaAbPresets();
  const [pollModel, setPollModel] = useState<string | null>(null);
  const { data: ollamaStatus } = useOllamaModelStatus(pollModel, !!pollModel);
  const savedOllamaModel = useRef<string | null>(null);
  const [selectedAbModel, setSelectedAbModel] = useState<string | null>(
    bot.llm_provider === "ollama" ? (bot.llm_model ?? null) : null,
  );

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
      bot_prompt: bot.bot_prompt,
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
      eval_provider: bot.eval_provider ?? "",
      eval_model: bot.eval_model ?? "",
      eval_depth: bot.eval_depth ?? "L1",
      mcp_servers: bot.mcp_servers ?? [],
      max_tool_calls: bot.max_tool_calls ?? 5,
      base_prompt: bot.base_prompt ?? "",
      widget_enabled: bot.widget_enabled ?? false,
      widget_allowed_origins: (bot.widget_allowed_origins ?? []).join("\n"),
      widget_keep_history: bot.widget_keep_history ?? true,
      widget_welcome_message: bot.widget_welcome_message ?? "",
      widget_placeholder_text: bot.widget_placeholder_text ?? "",
      widget_greeting_messages: bot.widget_greeting_messages ?? [],
      widget_greeting_animation: bot.widget_greeting_animation ?? "fade",
      rerank_enabled: bot.rerank_enabled ?? false,
      rerank_model: bot.rerank_model ?? "",
      rerank_top_n: bot.rerank_top_n ?? 20,
      intent_routes: bot.intent_routes ?? [],
      router_model: bot.router_model ?? "",
      summary_model: bot.summary_model ?? "",
      busy_reply_message:
        bot.busy_reply_message ?? "小編正在努力回覆中，請稍等一下喔～",
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
      line_show_sources: bot.line_show_sources ?? false,
      tool_configs: bot.tool_configs ?? {},
      customer_service_url: bot.customer_service_url ?? "",
    },
  });

  // Legacy: intent_routes field array (Workers tab replaces this UI)
  useFieldArray({
    control,
    name: "intent_routes",
  });

  const enabledTools = watch("enabled_tools") ?? [];
  const showSources = watch("show_sources");
  const greetingMessages = watch("widget_greeting_messages") ?? [];
  const mcpServers = watch("mcp_servers") ?? [];
  const currentLlmProvider = watch("llm_provider");
  const currentLlmModel = watch("llm_model");
  const toolConfigs = (watch("tool_configs") ?? {}) as Record<
    string,
    ToolRagConfig
  >;

  // HARDCODE - 模型就緒後停止 polling
  useEffect(() => {
    if (ollamaStatus?.status === "ready") {
      setPollModel(null);
    }
  }, [ollamaStatus?.status]);

  // LINE show_sources 連動：主開關關閉時，LINE 也關閉
  useEffect(() => {
    if (!showSources) {
      setValue("line_show_sources", false);
    }
  }, [showSources, setValue]);

  // MCP server tools metadata (shared with McpBindingsSection)
  const [serverToolsMap, setServerToolsMap] = useState<
    Record<string, McpToolInfo[]>
  >({});

  // Initialize serverToolsMap from persisted server.tools (no auto-discover).
  useEffect(() => {
    for (const server of bot.mcp_servers ?? []) {
      if (!serverToolsMap[server.url]) {
        const toolsMeta: McpToolInfo[] = server.tools?.length
          ? server.tools.map((t) => ({
              name: t.name,
              description: t.description,
              parameters: [],
            }))
          : server.enabled_tools.map((name) => ({
              name,
              description: "",
              parameters: [],
            }));
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
      bot_prompt: bot.bot_prompt,
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
      eval_provider: bot.eval_provider ?? "",
      eval_model: bot.eval_model ?? "",
      eval_depth: bot.eval_depth ?? "L1",
      mcp_servers: bot.mcp_servers ?? [],
      max_tool_calls: bot.max_tool_calls ?? 5,
      base_prompt: bot.base_prompt ?? "",
      widget_enabled: bot.widget_enabled ?? false,
      widget_allowed_origins: (bot.widget_allowed_origins ?? []).join("\n"),
      widget_keep_history: bot.widget_keep_history ?? true,
      widget_welcome_message: bot.widget_welcome_message ?? "",
      widget_placeholder_text: bot.widget_placeholder_text ?? "",
      widget_greeting_messages: bot.widget_greeting_messages ?? [],
      widget_greeting_animation: bot.widget_greeting_animation ?? "fade",
      rerank_enabled: bot.rerank_enabled ?? false,
      rerank_model: bot.rerank_model ?? "",
      rerank_top_n: bot.rerank_top_n ?? 20,
      intent_routes: bot.intent_routes ?? [],
      router_model: bot.router_model ?? "",
      summary_model: bot.summary_model ?? "",
      busy_reply_message:
        bot.busy_reply_message ?? "小編正在努力回覆中，請稍等一下喔～",
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
      line_show_sources: bot.line_show_sources ?? false,
      tool_configs: bot.tool_configs ?? {},
      customer_service_url: bot.customer_service_url ?? "",
    });
  }, [bot, reset]);

  // HARDCODE - Ollama polling 結果 toast，正式上線前移除
  useEffect(() => {
    if (!ollamaStatus || !savedOllamaModel.current) return;
    if (ollamaStatus.status === "ready") {
      toast.success(`✅ 模型 ${ollamaStatus.model} 已就緒`);
      setPollModel(null);
      savedOllamaModel.current = null;
    } else if (ollamaStatus.status === "unreachable") {
      toast.error("無法連線至 Ollama，請確認 RunPod Pod 已啟動");
      setPollModel(null);
      savedOllamaModel.current = null;
    }
  }, [ollamaStatus]);

  const onSubmit = async (data: BotFormValues) => {
    if (data.enabled_tools.length === 0) {
      toast.error("請至少啟用一個工具");
      setActiveTab(TAB_KEYS.CAPABILITIES);
      return;
    }
    if (data.knowledge_base_ids.length === 0) {
      toast.error("請至少綁定一個知識庫");
      setActiveTab(TAB_KEYS.CAPABILITIES);
      return;
    }
    const originsStr = data.widget_allowed_origins as string;
    const payload = {
      ...data,
      widget_allowed_origins: originsStr
        ? originsStr
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean)
        : [],
    };
    try {
      await onSave(payload);
      // HARDCODE - Ollama 存檔後啟動 polling 確認模型就緒，正式上線前移除
      if (payload.llm_provider === "ollama" && payload.llm_model) {
        savedOllamaModel.current = payload.llm_model as string;
        setPollModel(payload.llm_model as string);
        toast.success("機器人設定已儲存，正在確認模型狀態...");
      } else {
        toast.success("機器人設定已儲存");
      }
    } catch {
      toast.error("儲存失敗，請稍後再試");
    }
  };

  /** Build the combined select value from provider + model */
  const currentModelValue =
    bot.llm_provider && bot.llm_model
      ? `${bot.llm_provider}:${bot.llm_model}`
      : "";

  const handleToolConfigChange = (
    toolName: string,
    next: ToolRagConfig | undefined,
  ) => {
    const currentMap = { ...(watch("tool_configs") ?? {}) } as Record<
      string,
      ToolRagConfig
    >;
    if (next === undefined) {
      delete currentMap[toolName];
    } else {
      currentMap[toolName] = next;
    }
    setValue("tool_configs", currentMap, { shouldDirty: true });
  };

  const botGlobalInherited = {
    rag_top_k: Number(watch("rag_top_k") ?? 5),
    rag_score_threshold: Number(watch("rag_score_threshold") ?? 0.3),
    rerank_enabled: Boolean(watch("rerank_enabled") ?? false),
    rerank_model: watch("rerank_model") ?? "",
    rerank_top_n: Number(watch("rerank_top_n") ?? 20),
  };

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

      {/* 5-Tab section */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full">
          <TabsTrigger value={TAB_KEYS.LLM_PROMPT} className="flex-1">
            LLM &amp; Prompt
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.CAPABILITIES} className="flex-1">
            能力
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.SUBAGENT} className="flex-1">
            Sub-agent
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.STUDIO} className="flex-1">
            <Sparkles className="mr-1 h-3.5 w-3.5" />
            工作室
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.WIDGET} className="flex-1">
            Widget
          </TabsTrigger>
          <TabsTrigger value={TAB_KEYS.LINE} className="flex-1">
            LINE
          </TabsTrigger>
        </TabsList>

        {/* ================================================================ */}
        {/* Tab 1: LLM & Prompt                                                */}
        {/* ================================================================ */}
        <TabsContent
          value={TAB_KEYS.LLM_PROMPT}
          className="flex flex-col gap-6 pt-4"
        >
          {/* LLM 模型選擇 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">LLM 模型</h3>
            <p className="text-sm text-muted-foreground">
              選擇此機器人使用的 LLM 模型。可用模型由「系統設定 &gt;
              供應商設定」管理。
            </p>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-llm-model">模型</Label>
              <Controller
                name="llm_model"
                control={control}
                render={({ field }) => {
                  const selectValue = selectedAbModel
                    ? ""
                    : watch("llm_provider") && field.value
                      ? `${watch("llm_provider")}:${field.value}`
                      : currentModelValue;

                  return (
                    <ModelSelect
                      key={selectedAbModel ? "ollama" : "cloud"}
                      id="bot-llm-model"
                      value={selectValue}
                      onValueChange={(v) => {
                        const [provider, ...modelParts] = v.split(":");
                        const model = modelParts.join(":");
                        setSelectedAbModel(null);
                        setValue("llm_provider", provider, { shouldDirty: true });
                        field.onChange(model);
                      }}
                      enabledModels={enabledModels}
                    />
                  );
                }}
              />
            </div>

            {/* HARDCODE - 地端模型 A/B 快速切換，正式上線前移除 */}
            {abPresets.length > 0 && (
              <div className="flex flex-col gap-2">
                <Label className="text-xs text-muted-foreground">
                  地端模型快速切換（測試用）
                </Label>
                <div className="flex gap-2">
                  {abPresets.map((preset) => {
                    const isActive = selectedAbModel === preset.model;
                    return (
                      <Button
                        key={preset.label}
                        type="button"
                        size="sm"
                        variant={isActive ? "default" : "outline"}
                        onClick={() => {
                          setSelectedAbModel(preset.model);
                          setValue("llm_provider", "ollama", { shouldDirty: true });
                          setValue("llm_model", preset.model, { shouldDirty: true });
                        }}
                      >
                        {preset.label}：{preset.description}
                        {selectedAbModel === preset.model && pollModel === preset.model && (
                          <span className="ml-1 animate-spin">⏳</span>
                        )}
                        {selectedAbModel === preset.model &&
                          ollamaStatus?.status === "ready" &&
                          !pollModel && (
                            <span className="ml-1 text-green-500">✓</span>
                          )}
                      </Button>
                    );
                  })}
                </div>
                {pollModel && (
                  <p className="text-xs text-muted-foreground animate-pulse">
                    正在確認模型 {pollModel} 是否就緒...
                  </p>
                )}
              </div>
            )}
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
            <p className="text-xs text-muted-foreground">
              提示：Reranking 等檢索屬性已移至「能力」頁的「知識庫與檢索」區塊。
            </p>
          </section>

          {/* 自訂指令 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">自訂指令</h3>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bot-system-prompt">Bot 自訂指令</Label>
              <Textarea
                id="bot-system-prompt"
                {...register("bot_prompt")}
                rows={6}
                placeholder="輸入此機器人的自訂指令..."
              />
              <p className="text-xs text-muted-foreground">
                此指令會附加在系統提示詞最後，用於定義 Bot 的個性、語調等。
              </p>
            </div>
          </section>

          {/* 進階：子流程模型覆寫（S-KB-Followup.2） */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">進階：子流程模型覆寫</h3>
            <p className="text-sm text-muted-foreground">
              主對話用上方「LLM 模型」。下面兩個小任務可另指定 model（未指定則用
              系統管理 → 供應商設定的預設）。
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-router-model">
                  意圖分類（Intent Classifier）
                </Label>
                <Controller
                  name="router_model"
                  control={control}
                  render={({ field }) => (
                    <ModelSelect
                      id="bot-router-model"
                      value={field.value ?? ""}
                      onValueChange={(v) =>
                        field.onChange(v === "__none__" ? "" : v)
                      }
                      enabledModels={enabledModels}
                      placeholder="使用系統預設"
                      allowEmpty
                      emptyLabel="使用系統預設"
                    />
                  )}
                />
                <p className="text-xs text-muted-foreground">
                  判斷使用者意圖走哪個 worker；模型品質影響路由正確性
                </p>
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-summary-model">
                  對話摘要（Conversation Summary）
                </Label>
                <Controller
                  name="summary_model"
                  control={control}
                  render={({ field }) => (
                    <ModelSelect
                      id="bot-summary-model"
                      value={field.value ?? ""}
                      onValueChange={(v) =>
                        field.onChange(v === "__none__" ? "" : v)
                      }
                      enabledModels={enabledModels}
                      placeholder="使用系統預設"
                      allowEmpty
                      emptyLabel="使用系統預設"
                    />
                  )}
                />
                <p className="text-xs text-muted-foreground">
                  對話結束時自動產生摘要（用於搜尋與分析）；便宜 model 即可
                </p>
              </div>
            </div>
          </section>
        </TabsContent>

        {/* ================================================================ */}
        {/* Tab 2: 能力                                                        */}
        {/* ================================================================ */}
        <TabsContent
          value={TAB_KEYS.CAPABILITIES}
          className="flex flex-col gap-6 pt-4"
        >
          {/* 知識庫與檢索（合併：KB 綁定 + 預設檢索參數 + 預設 Reranking） */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">知識庫與檢索</h3>
            <p className="text-sm text-muted-foreground">
              綁定此機器人可以使用的知識庫，以及預設的檢索行為。每個 RAG
              類工具可展開「進階設定」獨立覆蓋；未覆蓋時套用這裡的預設。
            </p>

            {/* 綁定知識庫 */}
            <div className="flex flex-col gap-2">
              <Label>綁定的知識庫（可多選）</Label>
              <Controller
                name="knowledge_base_ids"
                control={control}
                render={({ field }) => (
                  <div className="flex flex-col gap-2">
                    {kbData?.items?.map((kb) => (
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
                    {(!kbData?.items || kbData.items.length === 0) && (
                      <p className="text-sm text-muted-foreground">
                        目前沒有可用的知識庫。
                      </p>
                    )}
                  </div>
                )}
              />
            </div>

            {/* 預設檢索參數 */}
            <div className="flex flex-col gap-3 rounded-md border bg-muted/20 px-3 py-3">
              <div className="flex flex-col">
                <Label className="text-sm font-medium">預設檢索參數</Label>
                <p className="text-xs text-muted-foreground">
                  未被 per-tool 覆蓋時，RAG 類工具會使用以下值。
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="bot-rag-top-k" className="text-xs">
                    Top K（1-20）
                  </Label>
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
                  <Label htmlFor="bot-rag-score-threshold" className="text-xs">
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

              {/* 預設 Reranking（折疊；已啟用時預設展開） */}
              <Collapsible defaultOpen={!!watch("rerank_enabled")}>
                <CollapsibleTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 justify-start gap-2 px-2 text-sm"
                  >
                    <ChevronDown className="h-4 w-4 transition-transform data-[state=open]:rotate-180" />
                    <span>
                      預設 Reranking：
                      <span className="font-medium">
                        {watch("rerank_enabled") ? "已啟用" : "未啟用"}
                      </span>
                    </span>
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="flex flex-col gap-3 pt-2">
                  <Controller
                    name="rerank_enabled"
                    control={control}
                    render={({ field }) => (
                      <div className="flex items-center justify-between">
                        <div>
                          <Label className="text-sm">啟用 Reranking</Label>
                          <p className="text-xs text-muted-foreground">
                            用 LLM 對 RAG 召回結果重新評分排序
                          </p>
                        </div>
                        <Switch
                          checked={field.value ?? false}
                          onCheckedChange={(v) => {
                            field.onChange(v);
                            if (v && !watch("rerank_model")) {
                              setValue(
                                "rerank_model",
                                "claude-haiku-4-5-20251001",
                              );
                            }
                          }}
                        />
                      </div>
                    )}
                  />
                  {watch("rerank_enabled") && (
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="flex flex-col gap-2">
                        <Label htmlFor="rerank-model" className="text-xs">
                          Rerank 模型
                        </Label>
                        <Controller
                          name="rerank_model"
                          control={control}
                          render={({ field }) => (
                            <Select
                              value={
                                field.value || "claude-haiku-4-5-20251001"
                              }
                              onValueChange={(v) => field.onChange(v)}
                            >
                              <SelectTrigger id="rerank-model">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {RERANK_MODEL_OPTIONS.map((opt) => (
                                  <SelectItem
                                    key={opt.value}
                                    value={opt.value}
                                  >
                                    {opt.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label htmlFor="rerank-top-n" className="text-xs">
                          召回數量
                        </Label>
                        <Input
                          id="rerank-top-n"
                          type="number"
                          {...register("rerank_top_n")}
                          min={5}
                          max={50}
                        />
                        <p className="text-xs text-muted-foreground">
                          Embedding 搜尋筆數（rerank 後取 RAG Top K 筆給 LLM）
                        </p>
                      </div>
                    </div>
                  )}
                </CollapsibleContent>
              </Collapsible>
            </div>
          </section>

          {/* 啟用工具 + per-tool RAG 覆蓋 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">啟用工具</h3>
            <p className="text-xs text-muted-foreground">
              至少勾選 1 個。rag_query 與 query_dm_with_image 通常擇一啟用
              — 兩者都會打知識庫，後者額外推送 LINE Flex 圖卡。
              RAG 類工具可展開「進階設定」獨立覆蓋檢索參數。
            </p>
            <Controller
              name="enabled_tools"
              control={control}
              render={({ field }) => (
                <div className="flex flex-col gap-3">
                  {builtInTools.map((tool) => {
                    const checked = field.value?.includes(tool.name) ?? false;
                    const isRagTool = (
                      RAG_TOOL_NAMES as readonly string[]
                    ).includes(tool.name);
                    return (
                      <div
                        key={tool.name}
                        className="rounded-md border px-3 py-2 hover:bg-muted/30 transition-colors flex flex-col gap-2"
                      >
                        <label className="flex items-start gap-2 text-sm cursor-pointer">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              const current = field.value ?? [];
                              if (e.target.checked) {
                                field.onChange([...current, tool.name]);
                              } else {
                                field.onChange(
                                  current.filter((t) => t !== tool.name),
                                );
                              }
                            }}
                            className="mt-0.5 rounded border-input"
                          />
                          <span className="flex flex-col gap-0.5">
                            <span className="font-medium">{tool.label}</span>
                            <span className="text-xs text-muted-foreground">
                              {tool.description}
                            </span>
                          </span>
                        </label>
                        {checked && isRagTool && (
                          <ToolRagConfigSection
                            toolName={tool.name}
                            toolLabel={`${tool.label} 檢索參數`}
                            value={toolConfigs[tool.name]}
                            inherited={botGlobalInherited}
                            inheritedLabel="繼承 Bot 預設"
                            onChange={(next) =>
                              handleToolConfigChange(tool.name, next)
                            }
                            rerankModelOptions={RERANK_MODEL_OPTIONS}
                          />
                        )}
                        {checked && tool.name === "transfer_to_human_agent" && (
                          <div className="rounded-md border bg-muted/20 px-3 py-3 flex flex-col gap-2">
                            <Label
                              htmlFor="bot-customer-service-url"
                              className="text-xs font-medium"
                            >
                              客服頁面 URL
                            </Label>
                            <Input
                              id="bot-customer-service-url"
                              type="url"
                              placeholder="https://example.com/customer-service"
                              {...register("customer_service_url")}
                            />
                            <p className="text-[11px] text-muted-foreground">
                              使用者被轉接時會顯示此 URL 按鈕。POC 階段先接網頁；
                              未來整合電話撥號會改用 <code>tel:</code>。未設定
                              時此工具會回傳「未設定客服資訊」訊息。
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {builtInTools.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      載入工具清單中...
                    </p>
                  )}
                </div>
              )}
            />
          </section>

          {/* MCP 設定 */}
          <McpBindingsSection
            mcpServers={mcpServers}
            onMcpServersChange={(servers) => setValue("mcp_servers", servers)}
            serverToolsMap={serverToolsMap}
            setServerToolsMap={setServerToolsMap}
            registerMaxToolCalls={register("max_tool_calls")}
            maxToolCallsError={errors.max_tool_calls?.message}
          />

          {/* RAG 品質評估 */}
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
                  const layers =
                    field.value && field.value !== "off"
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

        {/* ================================================================ */}
        {/* Tab 3: Sub-agent                                                   */}
        {/* ================================================================ */}
        <TabsContent
          value={TAB_KEYS.SUBAGENT}
          className="flex flex-col gap-6 pt-4"
        >
          <WorkersSection
            botId={bot.id}
            botTenantId={bot.tenant_id}
            enabledModels={enabledModels}
            knowledgeBases={(kbData?.items ?? []).map((kb) => ({
              id: kb.id,
              name: kb.name,
            }))}
            botDefaults={botGlobalInherited}
            botToolConfigs={toolConfigs}
            ragToolNames={RAG_TOOL_NAMES}
            ragToolLabels={builtInTools
              .filter((t) =>
                (RAG_TOOL_NAMES as readonly string[]).includes(t.name),
              )
              .reduce<Record<string, string>>((acc, t) => {
                acc[t.name] = t.label;
                return acc;
              }, {})}
            botEnabledTools={watch("enabled_tools") ?? []}
            builtInToolsLabels={builtInTools.reduce<Record<string, string>>(
              (acc, t) => {
                acc[t.name] = t.label;
                return acc;
              },
              {},
            )}
            rerankModelOptions={RERANK_MODEL_OPTIONS}
          />
        </TabsContent>

        {/* ================================================================ */}
        {/* Tab 4: Studio — 設定即時試運轉（獨立頁面）                       */}
        {/* ================================================================ */}
        <TabsContent
          value={TAB_KEYS.STUDIO}
          className="flex flex-col gap-4 pt-4"
        >
          <div className="rounded-lg border bg-gradient-to-br from-violet-50 to-fuchsia-50 p-6 dark:from-violet-950 dark:to-fuchsia-950">
            <div className="mb-2 flex items-center gap-2 text-base font-semibold">
              <Sparkles className="h-5 w-5 text-violet-500" />
              Bot 工作室 — 設定即時試運轉
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              送出測試訊息後，藍圖中對應的 agent / tool 會點亮、失敗節點會紅框 ping，
              結束後顯示完整執行 DAG。對話以 <code className="rounded bg-muted px-1">studio</code> 來源寫入 trace，跟正式對話分流。
            </p>
            <ul className="mb-4 space-y-1 text-xs text-muted-foreground">
              <li>· 左側儀表板：藍圖 + 執行紀錄 + 完整 DAG</li>
              <li>· 右側對話：多輪測試 + 演示模式（可慢速展示給客戶看）</li>
              <li>· 多 worker 場景能精準看出路由到哪個 worker</li>
            </ul>
            <Button
              type="button"
              onClick={() =>
                navigate(ROUTES.BOT_STUDIO.replace(":id", bot.id))
              }
              className="bg-violet-600 hover:bg-violet-700"
            >
              開啟工作室
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </TabsContent>

        {/* ================================================================ */}
        {/* Tab 5: Widget                                                     */}
        {/* ================================================================ */}
        <TabsContent
          value={TAB_KEYS.WIDGET}
          className="flex flex-col gap-6 pt-4"
        >
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
                    placeholder={
                      "https://shop.example.com\nhttps://www.example.com"
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    只有在此清單中的網域可以呼叫 Widget API。留空則不允許任何來源。
                  </p>
                </div>
              </section>

              {/* 對話歷史 */}
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

              {/* FAB 按鈕圖示 */}
              <section className="flex flex-col gap-4">
                <h3 className="text-lg font-semibold">FAB 按鈕圖示</h3>
                <p className="text-sm text-muted-foreground">
                  自訂 FAB 按鈕的圖片（支援 PNG / JPG / WebP，最大 256KB）
                </p>
                <div className="flex items-center gap-4">
                  {bot.fab_icon_url ? (
                    <img
                      src={`${API_BASE}${bot.fab_icon_url}`}
                      alt="FAB icon"
                      className="h-14 w-14 rounded-full object-cover border"
                    />
                  ) : (
                    <div className="flex h-14 w-14 items-center justify-center rounded-full border bg-muted">
                      <ImageIcon className="h-6 w-6 text-muted-foreground" />
                    </div>
                  )}
                  <div className="flex flex-col gap-2">
                    <p className="text-sm text-muted-foreground">
                      {bot.fab_icon_url ? "已上傳自訂圖示" : "尚未上傳自訂圖示"}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const input = document.createElement("input");
                          input.type = "file";
                          input.accept = "image/png,image/jpeg,image/webp";
                          input.onchange = async (e) => {
                            const file = (e.target as HTMLInputElement)
                              .files?.[0];
                            if (!file) return;
                            const formData = new FormData();
                            formData.append("file", file);
                            const token = useAuthStore.getState().token;
                            try {
                              const res = await fetch(
                                `${API_BASE}/api/v1/bots/${bot.id}/icon`,
                                {
                                  method: "POST",
                                  headers: {
                                    Authorization: `Bearer ${token}`,
                                  },
                                  body: formData,
                                },
                              );
                              if (!res.ok) {
                                const body = await res
                                  .json()
                                  .catch(() => ({}));
                                toast.error(body.detail || "上傳失敗");
                                return;
                              }
                              toast.success("FAB 圖示已上傳");
                              window.location.reload();
                            } catch {
                              toast.error("上傳失敗");
                            }
                          };
                          input.click();
                        }}
                      >
                        <Upload className="mr-1 h-4 w-4" />
                        上傳圖片
                      </Button>
                      {bot.fab_icon_url && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={async () => {
                            const token = useAuthStore.getState().token;
                            try {
                              await fetch(
                                `${API_BASE}/api/v1/bots/${bot.id}/icon`,
                                {
                                  method: "DELETE",
                                  headers: {
                                    Authorization: `Bearer ${token}`,
                                  },
                                },
                              );
                              toast.success("FAB 圖示已移除");
                              window.location.reload();
                            } catch {
                              toast.error("移除失敗");
                            }
                          }}
                        >
                          <Trash2 className="mr-1 h-4 w-4" />
                          移除
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
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

              {/* 歡迎招呼語 */}
              <section className="flex flex-col gap-4">
                <h3 className="text-lg font-semibold">歡迎招呼語</h3>
                <p className="text-xs text-muted-foreground">
                  聊天面板關閉時，按鈕旁會自動輪播這些招呼語氣泡，吸引訪客開啟對話。
                </p>
                <div className="flex flex-col gap-2">
                  {greetingMessages.map((_msg: string, idx: number) => (
                    <div key={idx} className="flex items-center gap-2">
                      <Input
                        value={greetingMessages[idx]}
                        onChange={(e) => {
                          const updated = [...greetingMessages];
                          updated[idx] = e.target.value;
                          setValue("widget_greeting_messages", updated, {
                            shouldDirty: true,
                          });
                        }}
                        placeholder={`招呼語 ${idx + 1}`}
                        maxLength={100}
                        className="flex-1"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          const updated = greetingMessages.filter(
                            (_: string, i: number) => i !== idx,
                          );
                          setValue("widget_greeting_messages", updated, {
                            shouldDirty: true,
                          });
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="self-start"
                    onClick={() => {
                      setValue(
                        "widget_greeting_messages",
                        [...greetingMessages, ""],
                        { shouldDirty: true },
                      );
                    }}
                  >
                    <Plus className="mr-1 h-4 w-4" />
                    新增招呼語
                  </Button>
                </div>
                <div className="flex flex-col gap-2">
                  <Label>動畫效果</Label>
                  <Controller
                    name="widget_greeting_animation"
                    control={control}
                    render={({ field }) => (
                      <Select
                        value={field.value}
                        onValueChange={field.onChange}
                      >
                        <SelectTrigger className="w-48">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="fade">淡入淡出 (Fade)</SelectItem>
                          <SelectItem value="slide">滑動 (Slide)</SelectItem>
                          <SelectItem value="typewriter">
                            打字機 (Typewriter)
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                  <p className="text-xs text-muted-foreground">
                    招呼語輪播時的切換動畫效果
                  </p>
                </div>
              </section>

              {/* 嵌入碼預覽 */}
              <section className="flex flex-col gap-4">
                <h3 className="text-lg font-semibold">嵌入碼</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-start gap-2">
                    <pre className="flex-1 whitespace-pre-wrap rounded-md bg-muted/50 p-3 text-xs font-mono select-all">
                      {`<script src="${PUBLIC_API_URL}/static/widget.js"\n        data-bot="${bot.short_code}"\n        data-theme="light"\n        crossorigin="anonymous">\n</script>`}
                    </pre>
                    <WebhookCopyButton
                      url={`<script src="${PUBLIC_API_URL}/static/widget.js"\n        data-bot="${bot.short_code}"\n        data-theme="light"\n        crossorigin="anonymous">\n</script>`}
                      label="嵌入碼"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    將此程式碼貼入外部網站的 HTML 即可嵌入聊天機器人。
                  </p>
                </div>
              </section>
        </TabsContent>

        {/* ================================================================ */}
        {/* Tab 5: LINE                                                        */}
        {/* ================================================================ */}
        <TabsContent
          value={TAB_KEYS.LINE}
          className="flex flex-col gap-6 pt-4"
        >
              {/* Webhook URL */}
              <section className="flex flex-col gap-4">
                <h3 className="text-lg font-semibold">Webhook URL</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <Input
                      readOnly
                      value={`${PUBLIC_API_URL}/api/v1/webhook/line/${bot.short_code}`}
                      className="font-mono text-sm"
                      onClick={(e) =>
                        (e.target as HTMLInputElement).select()
                      }
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
                <Controller
                  name="line_show_sources"
                  control={control}
                  render={({ field }) => (
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center justify-between">
                        <Label
                          htmlFor="line_show_sources"
                          className={
                            !showSources ? "text-muted-foreground" : ""
                          }
                        >
                          LINE 顯示來源引用
                        </Label>
                        <Switch
                          id="line_show_sources"
                          checked={field.value ?? false}
                          onCheckedChange={field.onChange}
                          disabled={!showSources}
                        />
                      </div>
                      {!showSources && (
                        <p className="text-xs text-muted-foreground">
                          需先在「基本設定」頁籤開啟「顯示資料來源」
                        </p>
                      )}
                    </div>
                  )}
                />
              </section>

              {/* 忙碌中回覆訊息 */}
              <section className="flex flex-col gap-4">
                <h3 className="text-lg font-semibold">忙碌中回覆訊息</h3>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="bot-busy-reply">
                    當使用者連續發送訊息時，以 reply（免費）回覆忙碌提示
                  </Label>
                  <Input
                    id="bot-busy-reply"
                    {...register("busy_reply_message")}
                    placeholder="小編正在努力回覆中，請稍等一下喔～"
                    maxLength={500}
                  />
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
