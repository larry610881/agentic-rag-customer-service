import { useState } from "react";
import type { Variants } from "framer-motion";
import { motion } from "framer-motion";
import { Search, Sparkles } from "lucide-react";
import { useConversationSearch } from "@/hooks/queries/use-conversation-search";
import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { AdminBotFilter } from "@/features/admin/components/admin-bot-filter";
import { ConversationSearchResultCard } from "@/features/admin/components/conversation-search-result-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";

const containerVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.3, ease: [0, 0, 0.2, 1] as const },
  },
};

export default function AdminConversationsPage() {
  const [mode, setMode] = useState<"keyword" | "semantic">("keyword");
  const [input, setInput] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [tenantId, setTenantId] = useState<string | undefined>();
  const [botId, setBotId] = useState<string | undefined>();

  const { data, isLoading, isError, refetch } = useConversationSearch({
    mode,
    query: submittedQuery,
    tenantId,
    botId,
    limit: 20,
    enabled: submittedQuery.length > 0,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittedQuery(input.trim());
  };

  const handleModeChange = (next: string) => {
    if (next === "keyword" || next === "semantic") {
      setMode(next);
      // 切 mode 後若已有 input，自動重 fetch
      if (input.trim()) {
        setSubmittedQuery(input.trim());
      }
    }
  };

  const items = data ?? [];

  return (
    <motion.div
      className="flex flex-col gap-6 p-6"
      variants={containerVariants}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={itemVariants}>
        <h1 className="text-2xl font-bold tracking-tight">對話搜尋</h1>
        <p className="text-muted-foreground">
          🔍 關鍵字搜 summary 字面 / 🧠 意思搜語意（系統管理員專用）
        </p>
      </motion.div>

      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">搜尋條件</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ToggleGroup
              type="single"
              value={mode}
              onValueChange={handleModeChange}
              className="w-fit border rounded-md"
            >
              <ToggleGroupItem value="keyword" className="px-4 text-sm">
                <Search className="mr-1.5 h-3.5 w-3.5" />
                關鍵字
              </ToggleGroupItem>
              <ToggleGroupItem value="semantic" className="px-4 text-sm">
                <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                意思
              </ToggleGroupItem>
            </ToggleGroup>

            <form
              className="flex flex-wrap items-center gap-3"
              onSubmit={handleSubmit}
            >
              <div className="relative flex-1 min-w-[280px]">
                <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder={
                    mode === "keyword"
                      ? "輸入關鍵字（如：退貨、訂單）"
                      : "用一句話描述（如：客戶不滿意）"
                  }
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  className="pl-8"
                />
              </div>
              <AdminTenantFilter
                value={tenantId}
                onChange={(v) => {
                  setTenantId(v);
                  setBotId(undefined);
                }}
              />
              <AdminBotFilter
                value={botId}
                onChange={setBotId}
                tenantId={tenantId}
              />
              <Button type="submit" disabled={!input.trim()}>
                搜尋
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => refetch()}
                disabled={!submittedQuery}
              >
                重新整理
              </Button>
            </form>
          </CardContent>
        </Card>
      </motion.div>

      <motion.div variants={itemVariants} className="space-y-3">
        {isError ? (
          <Card>
            <CardContent className="py-12 text-center text-destructive">
              搜尋失敗，請稍後重試
            </CardContent>
          </Card>
        ) : isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-32 w-full" />
            ))}
          </div>
        ) : !submittedQuery ? (
          <Card>
            <CardContent className="py-16 text-center text-muted-foreground">
              輸入關鍵字或一句話描述，按搜尋開始
            </CardContent>
          </Card>
        ) : items.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-muted-foreground">
              查無對應對話
            </CardContent>
          </Card>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              找到 {items.length} 筆對話
            </p>
            {items.map((item) => (
              <ConversationSearchResultCard
                key={item.conversation_id}
                item={item}
              />
            ))}
          </>
        )}
      </motion.div>
    </motion.div>
  );
}
