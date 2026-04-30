import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRetrievalTest } from "@/hooks/queries/use-kb-chunks";
import { useUpdateBot } from "@/hooks/queries/use-bots";
import { useAdminBots } from "@/hooks/queries/use-admin";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import type { RetrievalHit } from "@/types/chunk";
import type { RetrievalMode } from "@/types/bot";
import { RETRIEVAL_MODES } from "@/types/bot";

interface RetrievalPlaygroundTabProps {
  kbId: string;
}

const NONE_VALUE = "__none__";

const MODE_LABELS: Record<RetrievalMode, { label: string; hint: string }> = {
  raw: { label: "Raw", hint: "原始 query" },
  rewrite: { label: "Rewrite", hint: "LLM 改寫" },
  hyde: { label: "HyDE", hint: "LLM 假答案" },
};

export function RetrievalPlaygroundTab({ kbId }: RetrievalPlaygroundTabProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [includeConv, setIncludeConv] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Real-RAG 對齊參數
  const [scoreThreshold, setScoreThreshold] = useState(0.0);
  const [rerankEnabled, setRerankEnabled] = useState(false);
  const [rerankModel, setRerankModel] = useState("");
  const [rerankTopN, setRerankTopN] = useState(20);

  // Issue #43 — multi-mode retrieval state
  const [modes, setModes] = useState<RetrievalMode[]>(["raw"]);
  const [rewriteModel, setRewriteModel] = useState("");
  const [rewriteExtraHint, setRewriteExtraHint] = useState("");
  const [hydeModel, setHydeModel] = useState("");
  const [hydeExtraHint, setHydeExtraHint] = useState("");
  const [botId, setBotId] = useState("");

  // 「套用到 Bot」狀態
  const [applyTargetBotId, setApplyTargetBotId] = useState("");

  const test = useRetrievalTest(kbId);
  const updateBot = useUpdateBot();
  // KB Studio 只 system_admin 可進 → 用 admin 跨租戶 endpoint 列所有 bots
  // 否則 useBots() 只回 SYSTEM_TENANT 的 bots（通常 0 筆）
  const { data: botsData } = useAdminBots(undefined, 1, 200);
  const { data: enabledModels } = useEnabledModels();

  const toggleMode = (mode: RetrievalMode) => {
    setModes((prev) =>
      prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode],
    );
  };

  const run = () => {
    if (!query.trim()) return;
    if (modes.length === 0) {
      toast.error("請至少選 1 個 retrieval mode");
      return;
    }
    test.mutate({
      query: query.trim(),
      top_k: topK,
      include_conv_summaries: includeConv,
      score_threshold: scoreThreshold,
      rerank_enabled: rerankEnabled,
      rerank_model: rerankModel,
      rerank_top_n: rerankTopN,
      retrieval_modes: modes,
      query_rewrite_model: rewriteModel,
      query_rewrite_extra_hint: rewriteExtraHint,
      hyde_model: hydeModel,
      hyde_extra_hint: hydeExtraHint,
      bot_id: botId,
    });
  };

  const applyToBot = () => {
    if (!applyTargetBotId) {
      toast.error("請先選擇要套用的 bot");
      return;
    }
    if (modes.length === 0) {
      toast.error("modes 為空，無法套用");
      return;
    }
    updateBot.mutate(
      {
        botId: applyTargetBotId,
        data: {
          rag_retrieval_modes: modes,
          query_rewrite_enabled: modes.includes("rewrite"),
          query_rewrite_model: rewriteModel,
          query_rewrite_extra_hint: rewriteExtraHint,
          hyde_enabled: modes.includes("hyde"),
          hyde_model: hydeModel,
          hyde_extra_hint: hydeExtraHint,
          rerank_enabled: rerankEnabled,
          rerank_model: rerankModel,
          rerank_top_n: rerankTopN,
          rag_top_k: topK,
          rag_score_threshold: scoreThreshold,
        },
      },
      {
        onSuccess: () => {
          toast.success("✓ 已套用到 Bot");
        },
        onError: (e) => {
          toast.error(`套用失敗：${(e as Error).message}`);
        },
      },
    );
  };

  const results = test.data?.results ?? [];
  const chunkResults = results.filter((r) => r.source === "chunk");
  const convResults = results.filter((r) => r.source === "conv_summary");
  const modeQueries = test.data?.mode_queries ?? {};
  const rewrittenQuery = test.data?.rewritten_query ?? "";

  // 為了「每條候選 query 命中哪些 chunks」用：當前 result 的 chunk_id ↔ 命中 modes
  // Note：後端目前沒回 per-chunk modes，這裡顯示「mode → query」對照表即可。
  // 真實 multi-query 命中分佈會留到後端 trace metadata 補。
  const hasMultiQuery = useMemo(
    () => Object.keys(modeQueries).length > 1,
    [modeQueries],
  );

  return (
    <div className="space-y-4 pb-24">
      <div className="rounded-md border p-4 space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="輸入查詢句測試 RAG 檢索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
          <Button
            onClick={run}
            disabled={
              test.isPending || !query.trim() || modes.length === 0
            }
          >
            <Search className="h-4 w-4 mr-1" />
            {test.isPending ? "查詢中..." : "查詢"}
          </Button>
        </div>

        {/* Issue #43 — Retrieval modes（必選） */}
        <div className="rounded-md border bg-muted/20 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
            <Label className="text-sm font-medium">
              Retrieval Modes（至少選 1 個）
            </Label>
            <span className="text-xs text-muted-foreground">
              {modes.length} 條 query 並行檢索
            </span>
          </div>
          <div className="flex gap-2 flex-wrap">
            {RETRIEVAL_MODES.map((mode) => {
              const checked = modes.includes(mode);
              const meta = MODE_LABELS[mode];
              return (
                <label
                  key={mode}
                  className={`flex items-center gap-2 rounded border px-3 py-1.5 cursor-pointer transition-colors text-sm ${
                    checked
                      ? "border-primary bg-primary/5"
                      : "hover:bg-muted/50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleMode(mode)}
                    className="rounded border-input"
                  />
                  <span className="font-medium">{meta.label}</span>
                  <span className="text-xs text-muted-foreground">
                    {meta.hint}
                  </span>
                </label>
              );
            })}
          </div>
          {modes.length === 0 && (
            <p className="text-sm text-destructive">
              ⚠️ 至少選 1 個 mode 才能查詢
            </p>
          )}
        </div>

        <div className="flex items-center gap-6 text-sm flex-wrap">
          <div className="flex items-center gap-2">
            <Label htmlFor="topk">Top-K</Label>
            <Input
              id="topk"
              type="number"
              min={1}
              max={50}
              className="w-20"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value) || 5)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="threshold">Score 門檻</Label>
            <Input
              id="threshold"
              type="number"
              min={0}
              max={1}
              step={0.05}
              className="w-20"
              value={scoreThreshold}
              onChange={(e) => {
                const v = Number(e.target.value);
                setScoreThreshold(Math.max(0, Math.min(1, v)));
              }}
            />
            <span className="text-xs text-muted-foreground">
              （real RAG 預設 0.3；Playground 預設 0.0 看完整 top-K）
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="cross"
              checked={includeConv}
              onCheckedChange={setIncludeConv}
            />
            <Label htmlFor="cross">也搜尋對話摘要</Label>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          {showAdvanced ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          <Sparkles className="h-3.5 w-3.5" />
          進階：mode model + extra_hint + rerank（對齊真實對話）
        </button>

        {showAdvanced && (
          <div className="rounded bg-muted/40 p-3 space-y-3 text-sm">
            {modes.includes("rewrite") && (
              <div className="space-y-2">
                <div className="font-medium flex items-center gap-2">
                  <Sparkles className="h-3.5 w-3.5 text-amber-600" />
                  LLM Rewrite 設定
                </div>
                <div className="ml-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <Label className="w-24">Model</Label>
                    <Select
                      value={rewriteModel || NONE_VALUE}
                      onValueChange={(v) =>
                        setRewriteModel(v === NONE_VALUE ? "" : v)
                      }
                    >
                      <SelectTrigger className="w-72">
                        <SelectValue placeholder="預設 (haiku-4-5)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NONE_VALUE}>
                          預設 (claude-haiku-4-5)
                        </SelectItem>
                        {(enabledModels ?? []).map((m) => {
                          const spec = `${m.provider_name}:${m.model_id}`;
                          return (
                            <SelectItem key={spec} value={spec}>
                              {m.display_name || spec}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-start gap-2">
                    <Label className="w-24 mt-2">額外提示詞</Label>
                    <Textarea
                      rows={2}
                      placeholder="例：永遠保留品牌名前綴"
                      value={rewriteExtraHint}
                      onChange={(e) => setRewriteExtraHint(e.target.value)}
                      className="flex-1"
                    />
                  </div>
                </div>
              </div>
            )}

            {modes.includes("hyde") && (
              <div className="space-y-2 border-t pt-2">
                <div className="font-medium flex items-center gap-2">
                  <Sparkles className="h-3.5 w-3.5 text-purple-600" />
                  HyDE 設定
                </div>
                <div className="ml-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <Label className="w-24">Model</Label>
                    <Select
                      value={hydeModel || NONE_VALUE}
                      onValueChange={(v) =>
                        setHydeModel(v === NONE_VALUE ? "" : v)
                      }
                    >
                      <SelectTrigger className="w-72">
                        <SelectValue placeholder="預設 (haiku-4-5)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NONE_VALUE}>
                          預設 (claude-haiku-4-5)
                        </SelectItem>
                        {(enabledModels ?? []).map((m) => {
                          const spec = `${m.provider_name}:${m.model_id}`;
                          return (
                            <SelectItem key={spec} value={spec}>
                              {m.display_name || spec}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-start gap-2">
                    <Label className="w-24 mt-2">額外提示詞</Label>
                    <Textarea
                      rows={2}
                      placeholder="例：答案應提到具體分店名稱"
                      value={hydeExtraHint}
                      onChange={(e) => setHydeExtraHint(e.target.value)}
                      className="flex-1"
                    />
                  </div>
                </div>
              </div>
            )}

            {(modes.includes("rewrite") || modes.includes("hyde")) && (
              <div className="space-y-2 border-t pt-2">
                <div className="flex items-center gap-2">
                  <Label className="w-24">Bot context</Label>
                  <Select
                    value={botId || NONE_VALUE}
                    onValueChange={(v) =>
                      setBotId(v === NONE_VALUE ? "" : v)
                    }
                  >
                    <SelectTrigger className="w-72">
                      <SelectValue placeholder="不指定 (通用)" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NONE_VALUE}>
                        不指定（通用 prompt）
                      </SelectItem>
                      {(botsData?.items ?? []).map((b) => (
                        <SelectItem key={b.id} value={b.id}>
                          {b.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="text-xs text-muted-foreground">
                    指定後 rewrite/hyde 帶該 bot 的 system prompt 作 context
                  </span>
                </div>
              </div>
            )}

            <div className="space-y-2 border-t pt-2">
              <div className="flex items-center gap-2">
                <Switch
                  id="rerank"
                  checked={rerankEnabled}
                  onCheckedChange={setRerankEnabled}
                />
                <Label htmlFor="rerank" className="font-medium">
                  LLM Rerank — 先撈 top-N 再用 LLM 二次排序
                </Label>
              </div>
              {rerankEnabled && (
                <div className="ml-10 space-y-2">
                  <div className="flex items-center gap-2">
                    <Label className="w-24">Rerank top-N</Label>
                    <Input
                      type="number"
                      min={1}
                      max={100}
                      className="w-20"
                      value={rerankTopN}
                      onChange={(e) =>
                        setRerankTopN(Number(e.target.value) || 20)
                      }
                    />
                    <span className="text-xs text-muted-foreground">
                      召回多少筆送 LLM 排序（之後 LLM 再選 top-{topK}）
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Label className="w-24">Rerank model</Label>
                    <Select
                      value={rerankModel || NONE_VALUE}
                      onValueChange={(v) =>
                        setRerankModel(v === NONE_VALUE ? "" : v)
                      }
                    >
                      <SelectTrigger className="w-72">
                        <SelectValue placeholder="預設 (haiku-4-5)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NONE_VALUE}>
                          預設 (claude-haiku-4-5)
                        </SelectItem>
                        {(enabledModels ?? []).map((m) => {
                          const spec = `${m.provider_name}:${m.model_id}`;
                          return (
                            <SelectItem key={spec} value={spec}>
                              {m.display_name || spec}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </div>

            <p className="text-xs text-muted-foreground border-t pt-2">
              💡 modes + Bot context + rerank ≈ 真實對話檢索流程，差只剩
              ReAct agent 決定要不要呼叫 rag_query 那層
            </p>
          </div>
        )}
      </div>

      {/* 「✓ 套用到 Bot」按鈕 */}
      {test.data && (
        <div className="rounded-md border bg-emerald-50/50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800 p-3 flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-emerald-700 dark:text-emerald-300">
            ✓ 套用此設定到 Bot：
          </span>
          <Select
            value={applyTargetBotId || NONE_VALUE}
            onValueChange={(v) =>
              setApplyTargetBotId(v === NONE_VALUE ? "" : v)
            }
          >
            <SelectTrigger className="w-64">
              <SelectValue placeholder="選擇 bot" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE_VALUE}>—</SelectItem>
              {(botsData?.items ?? []).map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            onClick={applyToBot}
            disabled={
              !applyTargetBotId ||
              modes.length === 0 ||
              updateBot.isPending
            }
          >
            {updateBot.isPending ? "套用中..." : "套用"}
          </Button>
          <span className="text-xs text-muted-foreground">
            modes + 各 mode model/hint + rerank/threshold/topK 全部寫入該 bot
          </span>
        </div>
      )}

      {test.data && (
        <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1">
          {hasMultiQuery && (
            <div className="rounded bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-2 mb-2 space-y-1">
              <div className="font-semibold text-amber-700 dark:text-amber-300">
                ✨ Multi-mode queries（{Object.keys(modeQueries).length} 條）
              </div>
              {Object.entries(modeQueries).map(([mode, q]) => (
                <div key={mode} className="font-mono">
                  <span className="text-muted-foreground">{mode}：</span>
                  <span className="text-emerald-700 dark:text-emerald-400">
                    {q}
                  </span>
                </div>
              ))}
            </div>
          )}
          {!hasMultiQuery && rewrittenQuery && rewrittenQuery !== query && (
            <div className="rounded bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 p-2 mb-2">
              <div className="font-semibold text-amber-700 dark:text-amber-300">
                ✨ Query rewrite
              </div>
              <div className="font-mono mt-1">
                <span className="text-muted-foreground">原 query：</span>
                {query}
              </div>
              <div className="font-mono">
                <span className="text-muted-foreground">改寫後：</span>
                <span className="text-emerald-700 dark:text-emerald-400">
                  {rewrittenQuery}
                </span>
              </div>
            </div>
          )}
          <div>
            <span className="text-muted-foreground">filter expression：</span>
            <span className="font-mono">{test.data.filter_expr}</span>
          </div>
          <div className="text-muted-foreground">
            query 向量維度：{test.data.query_vector_dim} · 結果{" "}
            {results.length} 筆
            {modes.length > 1 && (
              <span className="ml-2 rounded bg-purple-100 dark:bg-purple-900/40 px-1.5 py-0.5 text-purple-700 dark:text-purple-300">
                multi-query × {modes.length}
              </span>
            )}
            {rerankEnabled && (
              <span className="ml-2 rounded bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-300">
                rerank
              </span>
            )}
            {scoreThreshold > 0 && (
              <span className="ml-2 rounded bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-blue-700 dark:text-blue-300">
                threshold ≥ {scoreThreshold.toFixed(2)}
              </span>
            )}
          </div>
        </div>
      )}

      {chunkResults.length > 0 && (
        <ResultSection title="📄 知識庫片段" hits={chunkResults} />
      )}
      {convResults.length > 0 && (
        <ResultSection title="💬 對話摘要" hits={convResults} />
      )}

      {test.error && (
        <div className="text-sm text-destructive">
          檢索失敗：{(test.error as Error).message}
        </div>
      )}
    </div>
  );
}

function ResultSection({
  title,
  hits,
}: {
  title: string;
  hits: RetrievalHit[];
}) {
  return (
    <div className="space-y-2">
      <h3 className="font-semibold text-sm">{title}</h3>
      {hits.map((hit, idx) => {
        const scoreColor =
          hit.score >= 0.5
            ? "text-emerald-600 dark:text-emerald-400"
            : hit.score >= 0.3
              ? "text-yellow-600 dark:text-yellow-400"
              : "text-red-600 dark:text-red-400";
        return (
          <div
            key={`${hit.source}-${hit.chunk_id}`}
            className="rounded-md border bg-card p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground font-mono">
                #{idx + 1} · {hit.chunk_id.slice(0, 12)}
              </span>
              <span className={`text-xs font-mono ${scoreColor}`}>
                score {hit.score.toFixed(4)}
              </span>
            </div>
            <div className="text-sm whitespace-pre-wrap line-clamp-4">
              {hit.content}
            </div>
          </div>
        );
      })}
    </div>
  );
}
