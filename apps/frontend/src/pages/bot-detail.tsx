import { useParams, useNavigate } from "react-router-dom";
import { BotAuditLogList } from "@/features/bot/components/bot-audit-log-list";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { useBot, useUpdateBot, useDeleteBot } from "@/hooks/queries/use-bots";
import { PageBreadcrumb } from "@/components/shared/page-breadcrumb";
import { ROUTES } from "@/routes/paths";
import type { UpdateBotRequest } from "@/types/bot";

export default function BotDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: bot, isLoading, isError } = useBot(id!);
  const updateBot = useUpdateBot();
  const deleteBot = useDeleteBot();

  const handleSave = async (data: UpdateBotRequest) => {
    await updateBot.mutateAsync({ botId: id!, data });
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
      {/* Issue #71 — 租戶端變更紀錄：誰在何時改了哪些欄位 */}
      <section className="flex flex-col gap-3 border-t pt-6" aria-labelledby="bot-audit-heading">
        <div>
          <h3 id="bot-audit-heading" className="text-lg font-semibold">
            變更紀錄
          </h3>
          <p className="text-sm text-muted-foreground">
            此機器人的設定變更歷程（提示詞類只顯示字數增減）
          </p>
        </div>
        <BotAuditLogList botId={bot.id} />
      </section>
    </div>
  );
}
