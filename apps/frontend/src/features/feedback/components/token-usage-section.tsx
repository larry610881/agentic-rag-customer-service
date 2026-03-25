import { useState } from "react";
import { useTokenCostStats } from "@/hooks/queries/use-feedback";
import { BotUsageSummaryCards } from "./bot-usage-summary-cards";
import { TokenPeriodSelector } from "./token-period-selector";

function getDefaultRange() {
  const now = new Date();
  const y = now.getFullYear();
  const m = now.getMonth() + 1;
  const startDate = `${y}-${String(m).padStart(2, "0")}-01`;
  const next = new Date(y, m, 1);
  const endDate = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`;
  return { startDate, endDate };
}

export function TokenUsageSection() {
  const defaults = getDefaultRange();
  const [startDate, setStartDate] = useState(defaults.startDate);
  const [endDate, setEndDate] = useState(defaults.endDate);
  const costs = useTokenCostStats(startDate, endDate);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Token 用量</h3>
        <TokenPeriodSelector
          onChange={(s, e) => {
            setStartDate(s);
            setEndDate(e);
          }}
        />
      </div>
      <BotUsageSummaryCards data={costs.data} isLoading={costs.isLoading} />
    </div>
  );
}
