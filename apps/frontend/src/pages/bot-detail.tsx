import { useParams, useNavigate, Link } from "react-router-dom";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { useBot, useUpdateBot, useDeleteBot } from "@/hooks/queries/use-bots";
import { ROUTES } from "@/routes/paths";

export default function BotDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: bot, isLoading, isError } = useBot(id!);
  const updateBot = useUpdateBot();
  const deleteBot = useDeleteBot();

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
    <div className="h-full overflow-auto flex flex-col gap-6 p-6">
      <div className="flex items-center gap-2">
        <Link to="/bots" className="text-sm text-muted-foreground hover:underline">
          機器人
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="text-sm">{bot.name}</span>
      </div>
      <h2 className="text-2xl font-semibold">{bot.name}</h2>
      <BotDetailForm
        bot={bot}
        onSave={(data) => updateBot.mutate({ botId: id!, data })}
        onDelete={handleDelete}
        isSaving={updateBot.isPending}
        isDeleting={deleteBot.isPending}
      />
    </div>
  );
}
