import { useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useRetrievalTest } from "@/hooks/queries/use-kb-chunks";
import type { RetrievalHit } from "@/types/chunk";

interface RetrievalPlaygroundTabProps {
  kbId: string;
}

export function RetrievalPlaygroundTab({ kbId }: RetrievalPlaygroundTabProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [includeConv, setIncludeConv] = useState(false);
  const test = useRetrievalTest(kbId);

  const run = () => {
    if (!query.trim()) return;
    test.mutate({
      query: query.trim(),
      top_k: topK,
      include_conv_summaries: includeConv,
    });
  };

  const results = test.data?.results ?? [];
  const chunkResults = results.filter((r) => r.source === "chunk");
  const convResults = results.filter((r) => r.source === "conv_summary");

  return (
    <div className="space-y-4">
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
        <div className="flex items-center gap-6 text-sm">
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
            <Switch
              id="cross"
              checked={includeConv}
              onCheckedChange={setIncludeConv}
            />
            <Label htmlFor="cross">也搜尋對話摘要 (cross-search)</Label>
          </div>
        </div>
      </div>

      {test.data && (
        <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1">
          <div>
            <span className="text-muted-foreground">filter expression：</span>
            <span className="font-mono">{test.data.filter_expr}</span>
          </div>
          <div className="text-muted-foreground">
            query 向量維度：{test.data.query_vector_dim} · 結果 {results.length} 筆
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

function ResultSection({ title, hits }: { title: string; hits: RetrievalHit[] }) {
  return (
    <div className="space-y-2">
      <h3 className="font-semibold text-sm">{title}</h3>
      {hits.map((hit) => (
        <div
          key={`${hit.source}-${hit.chunk_id}`}
          className="rounded-md border bg-card p-3"
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground font-mono">
              {hit.chunk_id.slice(0, 12)}
            </span>
            <span className="text-xs font-mono text-emerald-600">
              score {hit.score.toFixed(4)}
            </span>
          </div>
          <div className="text-sm whitespace-pre-wrap line-clamp-4">
            {hit.content}
          </div>
        </div>
      ))}
    </div>
  );
}
