"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { BotDetailForm } from "@/features/bot/components/bot-detail-form";
import { useBot, useUpdateBot, useDeleteBot } from "@/hooks/queries/use-bots";

export default function BotDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  const { data: bot, isLoading, isError } = useBot(params.id);
  const updateBot = useUpdateBot();
  const deleteBot = useDeleteBot();

  const handleDelete = () => {
    deleteBot.mutate(params.id, {
      onSuccess: () => {
        router.push("/bots");
      },
    });
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Loading bot...</p>
      </div>
    );
  }

  if (isError || !bot) {
    return (
      <div className="p-6">
        <p className="text-destructive">Failed to load bot.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center gap-2">
        <Link href="/bots" className="text-sm text-muted-foreground hover:underline">
          Bots
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="text-sm">{bot.name}</span>
      </div>
      <h2 className="text-2xl font-semibold">{bot.name}</h2>
      <BotDetailForm
        bot={bot}
        onSave={(data) => updateBot.mutate({ botId: params.id, data })}
        onDelete={handleDelete}
        isSaving={updateBot.isPending}
        isDeleting={deleteBot.isPending}
      />
    </div>
  );
}
