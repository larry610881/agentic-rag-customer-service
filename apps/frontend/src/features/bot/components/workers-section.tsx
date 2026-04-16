import { useState } from "react";
import { Plus, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ModelSelect } from "@/components/shared/model-select";
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
import {
  useWorkers,
  useCreateWorker,
  useUpdateWorker,
  useDeleteWorker,
} from "@/hooks/queries/use-workers";
import { useMcpRegistryAccessible } from "@/hooks/queries/use-mcp-registry";
import { useAuthStore } from "@/stores/use-auth-store";
import type { WorkerConfig } from "@/types/worker-config";
import type { ToolRagConfig } from "@/types/bot";
import {
  ToolRagConfigSection,
  type ModelOption,
  type ToolRagInherited,
} from "./tool-rag-config-section";

type EnabledModel = {
  provider_name: string;
  model_id: string;
  display_name: string;
};

type KnowledgeBaseInfo = {
  id: string;
  name: string;
};

type WorkersSectionProps = {
  botId: string;
  botTenantId: string;
  enabledModels?: EnabledModel[];
  knowledgeBases?: KnowledgeBaseInfo[];
  /** Bot 全域 RAG 預設，作為 worker 繼承的 fallback 值 */
  botDefaults?: ToolRagInherited;
  /** Bot per-tool 覆蓋，worker 未覆蓋時先繼承此層 */
  botToolConfigs?: Record<string, ToolRagConfig>;
  /** 需要顯示 per-tool 覆蓋 UI 的 tool 名稱白名單 */
  ragToolNames?: readonly string[];
  /** tool_name → 顯示 label 的對照表 */
  ragToolLabels?: Record<string, string>;
  rerankModelOptions?: ModelOption[];
};

/** 結合 bot per-tool 覆蓋 + bot 全域預設，算出 worker 視角的繼承值與來源 label。 */
function resolveWorkerInherited(
  toolName: string,
  botDefaults: ToolRagInherited,
  botToolConfig: ToolRagConfig | undefined,
): { inherited: ToolRagInherited; label: string } {
  if (botToolConfig && Object.keys(botToolConfig).length > 0) {
    return {
      inherited: {
        rag_top_k: botToolConfig.rag_top_k ?? botDefaults.rag_top_k,
        rag_score_threshold:
          botToolConfig.rag_score_threshold ?? botDefaults.rag_score_threshold,
        rerank_enabled:
          botToolConfig.rerank_enabled ?? botDefaults.rerank_enabled,
        rerank_model: botToolConfig.rerank_model ?? botDefaults.rerank_model,
        rerank_top_n: botToolConfig.rerank_top_n ?? botDefaults.rerank_top_n,
      },
      label: `繼承自 Bot 的 ${toolName}`,
    };
  }
  return { inherited: botDefaults, label: "繼承 Bot 預設" };
}

function WorkerCard({
  worker,
  botId,
  enabledModels,
  mcpServers,
  knowledgeBases,
  botDefaults,
  botToolConfigs,
  ragToolNames,
  ragToolLabels,
  rerankModelOptions,
}: {
  worker: WorkerConfig;
  botId: string;
  enabledModels: EnabledModel[];
  mcpServers: { id: string; name: string }[];
  knowledgeBases: { id: string; name: string }[];
  botDefaults?: ToolRagInherited;
  botToolConfigs?: Record<string, ToolRagConfig>;
  ragToolNames?: readonly string[];
  ragToolLabels?: Record<string, string>;
  rerankModelOptions?: ModelOption[];
}) {
  const [expanded, setExpanded] = useState(false);
  const updateMutation = useUpdateWorker(botId);
  const deleteMutation = useDeleteWorker(botId);

  const handleFieldUpdate = (
    field: string,
    value:
      | string
      | number
      | boolean
      | string[]
      | null
      | Record<string, ToolRagConfig>,
  ) => {
    updateMutation.mutate(
      { workerId: worker.id, data: { [field]: value } },
      {
        onError: () => toast.error("更新失敗"),
      },
    );
  };

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <button
          type="button"
          className="flex items-center gap-2 text-left"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          <span className="font-medium">{worker.name || "未命名"}</span>
          {worker.llm_model && (
            <Badge variant="secondary" className="text-xs">
              {worker.llm_model}
            </Badge>
          )}
          {worker.knowledge_base_ids.length > 0 && (
            <Badge variant="outline" className="text-xs">
              {worker.knowledge_base_ids.length} KB
            </Badge>
          )}
          {worker.enabled_mcp_ids.length > 0 && (
            <Badge variant="outline" className="text-xs">
              {worker.enabled_mcp_ids.length} tools
            </Badge>
          )}
        </button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>刪除 Sub-agent？</AlertDialogTitle>
              <AlertDialogDescription>
                確定刪除「{worker.name}」？此操作無法復原。
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                onClick={() =>
                  deleteMutation.mutate(worker.id, {
                    onSuccess: () => toast.success("已刪除"),
                    onError: () => toast.error("刪除失敗"),
                  })
                }
              >
                確定刪除
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      {expanded && (
        <div className="space-y-4 pt-2">
          {/* Name + Description */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">名稱</Label>
              <Input
                defaultValue={worker.name}
                onBlur={(e) => handleFieldUpdate("name", e.target.value)}
                placeholder="Sub-agent 名稱"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">路由描述（給 AI 分類器看）</Label>
              <Input
                defaultValue={worker.description}
                onBlur={(e) =>
                  handleFieldUpdate("description", e.target.value)
                }
                placeholder="例：客戶表達不滿或投訴"
              />
            </div>
          </div>

          {/* System Prompt */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs">專屬提示詞</Label>
            <Textarea
              defaultValue={worker.worker_prompt}
              onBlur={(e) =>
                handleFieldUpdate("worker_prompt", e.target.value)
              }
              rows={4}
              placeholder="此 Sub-agent 的系統提示詞"
            />
          </div>

          {/* LLM Model */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">LLM 模型（空 = Bot 預設）</Label>
              <ModelSelect
                value={
                  worker.llm_model
                    ? `${worker.llm_provider ?? ""}:${worker.llm_model}`
                    : "__none__"
                }
                onValueChange={(v) => {
                  if (v === "__none__") {
                    handleFieldUpdate("llm_provider", null);
                    handleFieldUpdate("llm_model", null);
                  } else {
                    const [provider, ...rest] = v.split(":");
                    handleFieldUpdate("llm_provider", provider);
                    handleFieldUpdate("llm_model", rest.join(":"));
                  }
                }}
                enabledModels={enabledModels}
                allowEmpty
                emptyLabel="Bot 預設"
                placeholder="Bot 預設"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">最大迭代次數</Label>
              <Input
                type="number"
                defaultValue={worker.max_tool_calls}
                onBlur={(e) =>
                  handleFieldUpdate(
                    "max_tool_calls",
                    parseInt(e.target.value) || 5,
                  )
                }
                min={1}
                max={20}
              />
            </div>
          </div>

          {/* Temperature + Max tokens */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">Temperature</Label>
              <Input
                type="number"
                step={0.1}
                defaultValue={worker.temperature}
                onBlur={(e) =>
                  handleFieldUpdate(
                    "temperature",
                    parseFloat(e.target.value) || 0.7,
                  )
                }
                min={0}
                max={2}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs">Max Tokens</Label>
              <Input
                type="number"
                defaultValue={worker.max_tokens}
                onBlur={(e) =>
                  handleFieldUpdate(
                    "max_tokens",
                    parseInt(e.target.value) || 1024,
                  )
                }
                min={100}
                max={128000}
              />
            </div>
          </div>

          {/* Knowledge Bases */}
          {knowledgeBases.length > 0 && (
            <div className="flex flex-col gap-2">
              <Label className="text-xs">知識庫（空 = 使用 Bot 預設）</Label>
              <div className="flex flex-wrap gap-2">
                {knowledgeBases.map((kb) => {
                  const selected = worker.knowledge_base_ids.includes(kb.id);
                  return (
                    <Badge
                      key={kb.id}
                      variant={selected ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        const next = selected
                          ? worker.knowledge_base_ids.filter((id) => id !== kb.id)
                          : [...worker.knowledge_base_ids, kb.id];
                        handleFieldUpdate("knowledge_base_ids", next);
                      }}
                    >
                      {kb.name}
                    </Badge>
                  );
                })}
              </div>
            </div>
          )}

          {/* Per-tool RAG 覆蓋 */}
          {botDefaults && ragToolNames && ragToolNames.length > 0 && (
            <div className="flex flex-col gap-2">
              <Label className="text-xs">
                Per-tool RAG 參數覆蓋（未填 = 繼承 Bot）
              </Label>
              <div className="flex flex-col gap-2">
                {ragToolNames.map((toolName) => {
                  const botToolCfg = botToolConfigs?.[toolName];
                  const { inherited, label } = resolveWorkerInherited(
                    toolName,
                    botDefaults,
                    botToolCfg,
                  );
                  const currentValue = worker.tool_configs?.[toolName];
                  const toolLabel =
                    ragToolLabels?.[toolName] ?? toolName;
                  return (
                    <ToolRagConfigSection
                      key={toolName}
                      toolName={toolName}
                      toolLabel={toolLabel}
                      value={currentValue}
                      inherited={inherited}
                      inheritedLabel={label}
                      rerankModelOptions={rerankModelOptions}
                      onChange={(next) => {
                        const nextMap = {
                          ...(worker.tool_configs ?? {}),
                        } as Record<string, ToolRagConfig>;
                        if (next === undefined) {
                          delete nextMap[toolName];
                        } else {
                          nextMap[toolName] = next;
                        }
                        handleFieldUpdate("tool_configs", nextMap);
                      }}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* MCP Tools */}
          {mcpServers.length > 0 && (
            <div className="flex flex-col gap-2">
              <Label className="text-xs">可用 MCP Tools（從 Bot 綁定中選取子集）</Label>
              <div className="flex flex-wrap gap-2">
                {mcpServers.map((s) => {
                  const selected = worker.enabled_mcp_ids.includes(s.id);
                  return (
                    <Badge
                      key={s.id}
                      variant={selected ? "default" : "outline"}
                      className="cursor-pointer"
                      onClick={() => {
                        const next = selected
                          ? worker.enabled_mcp_ids.filter(
                              (id) => id !== s.id,
                            )
                          : [...worker.enabled_mcp_ids, s.id];
                        handleFieldUpdate("enabled_mcp_ids", next);
                      }}
                    >
                      {s.name}
                    </Badge>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function WorkersSection({
  botId,
  botTenantId,
  enabledModels = [],
  knowledgeBases = [],
  botDefaults,
  botToolConfigs,
  ragToolNames,
  ragToolLabels,
  rerankModelOptions,
}: WorkersSectionProps) {
  const { data: workers, isLoading } = useWorkers(botId);
  const createMutation = useCreateWorker(botId);
  const { data: mcpServers } = useMcpRegistryAccessible(botTenantId);

  const mcpList = (mcpServers ?? []).map((s) => ({
    id: s.id,
    name: s.name,
  }));

  const handleAdd = () => {
    createMutation.mutate(
      { name: `Sub-agent ${(workers?.length ?? 0) + 1}` },
      {
        onSuccess: () => toast.success("已新增 Sub-agent"),
        onError: () => toast.error("新增失敗"),
      },
    );
  };

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Sub-agent</h3>
          <p className="text-sm text-muted-foreground">
            每個 Sub-agent 是獨立 ReAct Agent，有自己的模型、工具、提示詞。
            未命中時使用 Bot 預設設定。
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAdd}
          disabled={createMutation.isPending}
        >
          <Plus className="h-4 w-4 mr-1" />
          新增 Sub-agent
        </Button>
      </div>

      {isLoading && (
        <div className="text-center py-8 text-muted-foreground">
          載入中...
        </div>
      )}

      {!isLoading && (!workers || workers.length === 0) && (
        <div className="text-center py-8 text-muted-foreground border border-dashed rounded-lg">
          未設定 Sub-agent，所有訊息將使用 Bot 預設設定處理
        </div>
      )}

      {workers?.map((w) => (
        <WorkerCard
          key={w.id}
          worker={w}
          botId={botId}
          enabledModels={enabledModels}
          mcpServers={mcpList}
          knowledgeBases={knowledgeBases}
          botDefaults={botDefaults}
          botToolConfigs={botToolConfigs}
          ragToolNames={ragToolNames}
          ragToolLabels={ragToolLabels}
          rerankModelOptions={rerankModelOptions}
        />
      ))}
    </section>
  );
}
