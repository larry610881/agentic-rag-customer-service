import { useParams, useNavigate } from "react-router-dom";
import { useState } from "react";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { useBot, useUpdateBot, useDeleteBot } from "@/hooks/queries/use-bots";
import { PageBreadcrumb } from "@/components/shared/page-breadcrumb";
import { ROUTES } from "@/routes/paths";
import type { UpdateBotRequest } from "@/types/bot";
// HARDCODE - 地端模型切換 loading dialog，正式上線前移除
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function BotDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: bot, isLoading, isError } = useBot(id!);
  const updateBot = useUpdateBot();
  const deleteBot = useDeleteBot();
  // HARDCODE - 地端模型切換 loading 狀態，正式上線前移除
  const [isWarmingUp, setIsWarmingUp] = useState(false);

  const handleSave = async (data: UpdateBotRequest) => {
    // HARDCODE - 偵測 Ollama 模型切換，顯示等待 dialog，正式上線前移除
    const isOllamaSave = data.llm_provider === "ollama";
    if (isOllamaSave) setIsWarmingUp(true);
    try {
      await updateBot.mutateAsync({ botId: id!, data });
    } finally {
      if (isOllamaSave) setIsWarmingUp(false);
    }
  };

  const handleDelete = () => {
    deleteBot.mutate(id!, {
      onSuccess: () => {
        navigate(ROUTES.BOTS);
      },
    });
  };

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
    <>
      {/* HARDCODE - 地端模型切換 loading dialog，正式上線前移除 */}
      <Dialog open={isWarmingUp} onOpenChange={() => {}}>
        <DialogContent
          className="sm:max-w-sm"
          onInteractOutside={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span className="animate-spin">⏳</span>
              切換模型中...
            </DialogTitle>
            <DialogDescription>
              正在將地端模型載入 GPU，請稍候（約 30–90 秒）。
              <br />
              完成後頁面將自動更新。
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>

    <div className="flex flex-col gap-6 p-6">
      <PageBreadcrumb
        items={[
          { label: "機器人", to: ROUTES.BOTS },
          { label: bot.name },
        ]}
      />
      <h2 className="text-2xl font-semibold">{bot.name}</h2>
      <BotDetailForm
        bot={bot}
        onSave={handleSave}
        onDelete={handleDelete}
        isSaving={updateBot.isPending}
        isDeleting={deleteBot.isPending}
      />
    </div>
    </>
  );
}
