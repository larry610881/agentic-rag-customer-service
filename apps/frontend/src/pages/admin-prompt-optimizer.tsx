import { Link } from "react-router-dom";
import { Wand2, Play, Database, History } from "lucide-react";
import { ROUTES } from "@/routes/paths";

export default function AdminPromptOptimizerPage() {
  const cards = [
    { title: "啟動優化", description: "選擇 Bot 與情境集，開始自動優化", icon: Play, href: ROUTES.ADMIN_PROMPT_OPTIMIZER_START },
    { title: "情境集管理", description: "建立與管理評估用的測試情境集", icon: Database, href: ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASETS },
    { title: "歷史紀錄", description: "查看過往優化紀錄與 Rollback", icon: History, href: ROUTES.ADMIN_PROMPT_OPTIMIZER_RUNS },
  ];

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Wand2 className="h-6 w-6" />
          Prompt 自動優化
        </h1>
        <p className="mt-1 text-muted-foreground">
          AutoResearch Prompt Optimizer — 自動迭代優化 Bot 的系統提示詞
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {cards.map((card) => (
          <Link
            key={card.href}
            to={card.href}
            className="rounded-lg border p-6 shadow-sm hover:shadow-md transition-shadow duration-200"
          >
            <card.icon className="mb-3 h-8 w-8 text-primary" />
            <h2 className="text-lg font-semibold">{card.title}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{card.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
