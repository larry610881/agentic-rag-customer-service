import { useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useConvSummarySearch } from "@/hooks/queries/use-conv-summaries";

interface SearchPanelProps {
  tenantId: string;
  botId?: string | null;
}

export function ConvSummarySearchPanel({ tenantId, botId }: SearchPanelProps) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const search = useConvSummarySearch();

  const run = () => {
    if (!query.trim()) return;
    search.mutate({ query: query.trim(), tenant_id: tenantId, bot_id: botId, top_k: topK });
  };

  return (
    <div className="space-y-3">
      <div className="rounded-md border p-4 space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="輸入查詢測試對話摘要語義搜尋"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
          />
          <Button onClick={run} disabled={search.isPending || !query.trim()}>
            <Search className="h-4 w-4 mr-1" />
            {search.isPending ? "查詢中..." : "查詢"}
          </Button>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Label htmlFor="topk-conv">Top-K</Label>
          <Input
            id="topk-conv"
            type="number"
            min={1}
            max={50}
            className="w-20"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value) || 10)}
          />
        </div>
      </div>

      {search.error && (
        <div className="text-sm text-destructive">
          搜尋失敗：{(search.error as Error).message}
        </div>
      )}

      <div className="space-y-2">
        {(search.data?.results ?? []).map((hit) => (
          <div key={hit.id} className="rounded-md border bg-card p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground font-mono">
                {hit.id.slice(0, 12)}
                {hit.bot_id ? ` · bot ${hit.bot_id.slice(0, 8)}` : ""}
              </span>
              <span className="text-xs font-mono text-emerald-600">
                score {hit.score.toFixed(4)}
              </span>
            </div>
            <p className="text-sm whitespace-pre-wrap line-clamp-4">
              {hit.summary}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
