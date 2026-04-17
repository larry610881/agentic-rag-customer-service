import { useBots } from "@/hooks/queries/use-bots";
import { BotCard } from "@/features/bot/components/bot-card";
import { Skeleton } from "@/components/ui/skeleton";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { AdminEmptyStateHint } from "@/components/shared/admin-empty-state-hint";
import { usePagination } from "@/hooks/use-pagination";

export function BotList() {
  const { page, setPage } = usePagination();
  const { data, isLoading, isError } = useBots(page);

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-36 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <p className="text-destructive">載入機器人失敗。</p>;
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <AdminEmptyStateHint resource="bots" isEmpty />
        <p className="text-muted-foreground">
          尚無機器人，請建立一個來開始使用。
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.items.map((bot) => (
          <BotCard key={bot.id} bot={bot} />
        ))}
      </div>
      <PaginationControls
        page={page}
        totalPages={data.total_pages}
        onPageChange={setPage}
      />
    </div>
  );
}
