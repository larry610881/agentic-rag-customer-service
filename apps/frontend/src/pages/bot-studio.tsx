import { useParams } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { useBot } from "@/hooks/queries/use-bots";
import { PageBreadcrumb } from "@/components/shared/page-breadcrumb";
import { ROUTES } from "@/routes/paths";
import { BotStudioWorkspace } from "@/features/bot/components/bot-studio-canvas";

export default function BotStudioPage() {
  const { id } = useParams<{ id: string }>();
  const { data: bot, isLoading, isError } = useBot(id!);

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">載入中...</p>
      </div>
    );
  }

  if (isError || !bot) {
    return (
      <div className="p-6">
        <p className="text-destructive">載入機器人失敗。</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <PageBreadcrumb
          items={[
            { label: "機器人", to: ROUTES.BOTS },
            { label: bot.name, to: ROUTES.BOT_DETAIL.replace(":id", bot.id) },
            { label: "工作室" },
          ]}
        />
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Sparkles className="h-4 w-4 text-violet-500" />
          設定即時試運轉 — 對話以 <code className="rounded bg-muted px-1">studio</code> 來源寫入 trace，與正式對話分流
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <BotStudioWorkspace bot={bot} />
      </div>
    </div>
  );
}
