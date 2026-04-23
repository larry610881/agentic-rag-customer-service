interface Props {
  summary: string | null | undefined;
  lastMessageAt: string | null | undefined;
  messageCount: number;
}

export function ConversationSummaryTab({
  summary,
  lastMessageAt,
  messageCount,
}: Props) {
  if (!summary) {
    return (
      <div className="rounded-md border bg-muted/30 p-6 text-center text-muted-foreground">
        <p>此對話尚未生成摘要</p>
        <p className="mt-2 text-xs">
          摘要由 cron 排程自動生成（通常對話結束後幾分鐘內）
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>訊息數：{messageCount}</span>
        {lastMessageAt && (
          <span>
            最後活動：{new Date(lastMessageAt).toLocaleString("zh-TW")}
          </span>
        )}
      </div>
      <div className="rounded-md border bg-card p-4">
        <h3 className="text-sm font-semibold mb-2">摘要</h3>
        <p className="text-sm whitespace-pre-wrap leading-relaxed">
          {summary}
        </p>
      </div>
    </div>
  );
}
