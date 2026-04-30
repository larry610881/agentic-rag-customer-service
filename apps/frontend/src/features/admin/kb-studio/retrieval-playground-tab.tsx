import { useState } from "react";
import { ChevronDown, ChevronRight, Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useRetrievalTest } from "@/hooks/queries/use-kb-chunks";
import { useBots } from "@/hooks/queries/use-bots";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import type { RetrievalHit } from "@/types/chunk";

interface RetrievalPlaygroundTabProps {
  kbId: string;
}

const NONE_VALUE = "__none__";

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
  const [queryRewriteEnabled, setQueryRewriteEnabled] = useState(false);
  const [queryRewriteModel, setQueryRewriteModel] = useState("");
  const [botId, setBotId] = useState("");

  const test = useRetrievalTest(kbId);
  const { data: botsData } = useBots(1, 50);
  const { data: enabledModels } = useEnabledModels();

  const run = () => {
    if (!query.trim()) return;
    test.mutate({
      query: query.trim(),
      top_k: topK,
      include_conv_summaries: includeConv,
      score_threshold: scoreThreshold,
      rerank_enabled: rerankEnabled,
      rerank_model: rerankModel,
      rerank_top_n: rerankTopN,
      query_rewrite_enabled: queryRewriteEnabled,
      query_rewrite_model: queryRewriteModel,
      bot_id: botId,
    });
  };

  const results = test.data?.results ?? [];
  const chunkResults = results.filter((r) => r.source === "chunk");
  const convResults = results.filter((r) => r.source === "conv_summary");
  const rewrittenQuery = test.data?.rewritten_query ?? "";

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
          <Button onClick={run} disabled={test.isPending || !query.trim()}>
            <Search className="h-4 w-4 mr-1" />
            {test.isPending ? "查詢中..." : "查詢"}
          </Button>
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
          進階：Query rewrite + Rerank（對齊真實對話）
        </button>

        {showAdvanced && (
          <div className="rounded bg-muted/40 p-3 space-y-3 text-sm">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Switch
                  id="rewrite"
                  checked={queryRewriteEnabled}
                  onCheckedChange={setQueryRewriteEnabled}
                />
                <Label htmlFor="rewrite" className="font-medium">
                  Query rewrite — LLM 把使用者問題改寫成檢索友善版本
                </Label>
              </div>
              {queryRewriteEnabled && (
                <div className="ml-10 space-y-2">
                  <div className="flex items-center gap-2">
                    <Label className="w-24">Rewrite model</Label>
                    <Select
                      value={queryRewriteModel || NONE_VALUE}
                      onValueChange={(v) =>
                        setQueryRewriteModel(v === NONE_VALUE ? "" : v)
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
                  <div className="flex items-center gap-2">
                    <Label className="w-24">Bot context</Label>
                    <Select
                      value={botId || NONE_VALUE}
                      onValueChange={(v) =>
                        setBotId(v === NONE_VALUE ? "" : v)
                      }
                    >
                      <SelectTrigger className="w-72">
                        <SelectValue placeholder="不指定 (通用 rewrite)" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NONE_VALUE}>
                          不指定（通用 rewrite）
                        </SelectItem>
                        {(botsData?.items ?? []).map((b) => (
                          <SelectItem key={b.id} value={b.id}>
                            {b.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <span className="text-xs text-muted-foreground">
                      指定後 rewrite 帶該 bot 的 system prompt 作 context
                    </span>
                  </div>
                </div>
              )}
            </div>

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
              💡 開兩個開關 + 選 bot ≈ 真實對話檢索流程，差只剩
              ReAct agent 決定要不要呼叫 rag_query 那層
            </p>
          </div>
        )}
      </div>

      {test.data && (
        <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1">
          {rewrittenQuery && rewrittenQuery !== query && (
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
