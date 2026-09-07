import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { USAGE_CATEGORIES } from "@/constants/usage-categories";

interface PlanCategoryMultiplierTableProps {
  /** category → 輸入原文；空字串 = 沿用預設倍率 */
  value: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  /** 顯示於 placeholder 的預設倍率 */
  defaultMultiplier: number;
  disabled?: boolean;
}

/** Issue #74 — 點數制方案的類別倍率表（列來源 USAGE_CATEGORIES） */
export function PlanCategoryMultiplierTable({
  value,
  onChange,
  defaultMultiplier,
  disabled,
}: PlanCategoryMultiplierTableProps) {
  return (
    <div className="max-h-64 overflow-y-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>類別</TableHead>
            <TableHead className="w-[140px]">倍率</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {USAGE_CATEGORIES.map((cat) => (
            <TableRow key={cat.value}>
              <TableCell className="text-sm">
                <label htmlFor={`mult-${cat.value}`}>{cat.label}</label>
                <span className="ml-1 font-mono text-xs text-muted-foreground">
                  {cat.value}
                </span>
              </TableCell>
              <TableCell>
                <Input
                  id={`mult-${cat.value}`}
                  type="number"
                  step="0.001"
                  min="0"
                  className="h-8"
                  placeholder={`預設 ${defaultMultiplier}`}
                  value={value[cat.value] ?? ""}
                  disabled={disabled}
                  onChange={(e) =>
                    onChange({ ...value, [cat.value]: e.target.value })
                  }
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
