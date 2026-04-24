import { Link } from "react-router-dom";
import { useConversationTokenUsage } from "@/hooks/queries/use-conversation-insights";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getRequestTypeLabel, inferUsageSource } from "@/types/token-usage";

const CHANNEL_LABELS: Record<string, string> = {
  web: "Web",
  widget: "Widget",
  line: "LINE",
  studio: "Studio",
};

interface Props {
  conversationId: string;
}

export function ConversationTokenUsageTab({ conversationId }: Props) {
  const { data, isLoading, error } = useConversationTokenUsage(conversationId);

  if (isLoading) return <Skeleton className="h-48 w-full" />;

  if (error) {
    return (
      <p className="text-destructive text-sm">
        載入失敗：{(error as Error).message}
      </p>
    );
  }

  if (!data) return null;

  const { totals, by_request_type } = data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="訊息數" value={totals.message_count.toLocaleString()} />
        <Stat label="Input tokens" value={totals.input_tokens.toLocaleString()} />
        <Stat label="Output tokens" value={totals.output_tokens.toLocaleString()} />
        <Stat
          label="預估成本"
          value={`$${totals.estimated_cost.toFixed(4)}`}
          highlight
        />
      </div>

      {by_request_type.length === 0 ? (
        <p className="text-muted-foreground py-6 text-center border rounded-md">
          此對話沒有 token 用量紀錄
        </p>
      ) : (
        <div className="border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>類型</TableHead>
                <TableHead>來源</TableHead>
                <TableHead>模型</TableHead>
                <TableHead className="text-right">次數</TableHead>
                <TableHead className="text-right">Input</TableHead>
                <TableHead className="text-right">Output</TableHead>
                <TableHead className="text-right">快取讀</TableHead>
                <TableHead className="text-right">預估成本</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {by_request_type.map((r, idx) => {
                const src = inferUsageSource({
                  tenant_id: "",
                  tenant_name: "",
                  bot_id: r.bot_id ?? null,
                  bot_name: r.bot_name ?? null,
                  kb_id: r.kb_id ?? null,
                  kb_name: r.kb_name ?? null,
                  model: r.model,
                  request_type: r.request_type,
                  input_tokens: r.input_tokens,
                  output_tokens: r.output_tokens,
                  total_tokens: 0,
                  estimated_cost: r.estimated_cost,
                  cache_read_tokens: r.cache_read_tokens,
                  cache_creation_tokens: r.cache_creation_tokens,
                  message_count: r.message_count,
                });
                const channelLabel =
                  r.channel_source && CHANNEL_LABELS[r.channel_source]
                    ? CHANNEL_LABELS[r.channel_source]
                    : null;
                return (
                  <TableRow key={`${r.request_type}-${r.model}-${idx}`}>
                    <TableCell>{getRequestTypeLabel(r.request_type)}</TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        {src.href ? (
                          <Link
                            to={src.href}
                            className="inline-flex items-center gap-1 hover:underline underline-offset-4"
                          >
                            <span>{src.icon}</span>
                            <span>{src.name}</span>
                          </Link>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                            <span>{src.icon}</span>
                            <span>{src.name}</span>
                          </span>
                        )}
                        {channelLabel && (
                          <Badge
                            variant="outline"
                            className="w-fit px-1.5 py-0 text-[10px] font-normal text-muted-foreground"
                          >
                            📡 {channelLabel}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">{r.model}</TableCell>
                    <TableCell className="text-right">
                      {r.message_count.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {r.input_tokens.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {r.output_tokens.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {r.cache_read_tokens.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      ${r.estimated_cost.toFixed(4)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded-md border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          highlight
            ? "text-lg font-bold text-emerald-600"
            : "text-lg font-semibold"
        }
      >
        {value}
      </div>
    </div>
  );
}
