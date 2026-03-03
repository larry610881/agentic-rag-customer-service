import { useState, useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
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
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    },
  });

  const enabledTools = watch("enabled_tools") ?? [];

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
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    });
  }, [bot, reset]);

  const onSubmit = async (data: BotFormValues) => {
    // Validation: active bot must have at least one tool enabled
    if (data.is_active && data.enabled_tools.length === 0) {
      toast.error("啟用中的機器人至少需要選擇一個工具");
      setActiveTab(TAB_KEYS.KNOWLEDGE);
      return;
    }
    // Validation: rag_query tool requires at least one knowledge base
    if (
      data.enabled_tools.includes("rag_query") &&
      data.knowledge_base_ids.length === 0
    ) {
      toast.error("已啟用「知識庫查詢」工具，請至少綁定一個知識庫");
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
            RAG 知識庫
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

          {/* 啟用工具 */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">啟用工具</h3>
            <p className="text-sm text-muted-foreground">
              選擇此機器人可使用的工具。若未選擇任何工具，機器人將直接透過 LLM 回覆。
            </p>
            <Controller
              name="enabled_tools"
              control={control}
              render={({ field }) => (
                <div className="flex flex-col gap-2">
                  {AVAILABLE_TOOLS.map((tool) => (
                    <label
                      key={tool.value}
                      className="flex items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={field.value.includes(tool.value)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            field.onChange([...field.value, tool.value]);
                          } else {
                            field.onChange(
                              field.value.filter((v) => v !== tool.value),
                            );
                          }
                        }}
                        className="rounded border-input"
                      />
                      {tool.label}
                    </label>
                  ))}
                </div>
              )}
            />
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
        <TabsContent value={TAB_KEYS.LINE} className="flex flex-col gap-4 pt-4">
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
