"use client";

import { BotList } from "@/features/bot/components/bot-list";
import { CreateBotDialog } from "@/features/bot/components/create-bot-dialog";

export default function BotsPage() {
  return (
    <div className="h-full overflow-auto flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Bots</h2>
        <CreateBotDialog />
      </div>
      <BotList />
    </div>
  );
}
