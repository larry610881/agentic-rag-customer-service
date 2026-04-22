import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useRecalcHistory } from "@/hooks/queries/use-pricing";

export function PricingHistoryTable() {
  const { data, isLoading } = useRecalcHistory();

  if (isLoading) {
    return (
      <p className="text-muted-foreground text-sm">載入重算歷史中...</p>
    );
  }
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground text-sm">尚無重算紀錄</p>;
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>執行時間</TableHead>
            <TableHead>區間</TableHead>
            <TableHead>影響筆數</TableHead>
            <TableHead>成本差</TableHead>
            <TableHead>執行者</TableHead>
            <TableHead>理由</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((a) => (
            <TableRow key={a.id}>
              <TableCell className="whitespace-nowrap">
                {new Date(a.executed_at).toLocaleString()}
              </TableCell>
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                {new Date(a.recalc_from).toLocaleString()}
                <br />
                → {new Date(a.recalc_to).toLocaleString()}
              </TableCell>
              <TableCell>{a.affected_rows}</TableCell>
              <TableCell
                className={`font-mono text-sm ${
                  a.cost_delta >= 0 ? "text-amber-600" : "text-emerald-600"
                }`}
              >
                {a.cost_delta >= 0 ? "+" : ""}${a.cost_delta.toFixed(6)}
              </TableCell>
              <TableCell>{a.executed_by}</TableCell>
              <TableCell className="max-w-[300px] truncate text-sm">
                {a.reason}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
