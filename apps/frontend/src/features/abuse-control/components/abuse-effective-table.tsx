import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AbuseOverrides } from "@/types/abuse-control";
import {
  buildFieldGroups,
  formatSettingValue,
} from "@/features/abuse-control/abuse-setting-labels";

export interface AbuseEffectiveLayer {
  label: string;
  overrides: AbuseOverrides | undefined;
}

interface AbuseEffectiveTableProps {
  values: Record<string, unknown>;
  /** 依序檢查哪一層提供了此鍵（例：租戶覆寫 → 方案），皆無則顯示 fallbackSource */
  layers?: AbuseEffectiveLayer[];
  fallbackSource?: string;
  allowedKeys?: string[];
}

export function AbuseEffectiveTable({
  values,
  layers = [],
  fallbackSource = "平台預設",
  allowedKeys,
}: AbuseEffectiveTableProps) {
  const groups = buildFieldGroups(allowedKeys ?? Object.keys(values));

  const sourceOf = (key: string): { label: string; overridden: boolean } => {
    for (const layer of layers) {
      if (layer.overrides && layer.overrides[key] !== undefined) {
        return { label: layer.label, overridden: true };
      }
    }
    return { label: fallbackSource, overridden: false };
  };

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <div key={group.key} className="space-y-2">
          <h3 className="text-sm font-medium">{group.label}</h3>
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-1/2">設定</TableHead>
                  <TableHead>生效值</TableHead>
                  <TableHead className="w-32">來源</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.fields.map((f) => {
                  const source = sourceOf(f.key);
                  return (
                    <TableRow key={f.key}>
                      <TableCell>{f.label}</TableCell>
                      <TableCell className="font-mono text-sm" data-testid={`effective-${f.key}`}>
                        {formatSettingValue(f.key, values[f.key])}
                      </TableCell>
                      <TableCell>
                        <Badge variant={source.overridden ? "default" : "outline"}>
                          {source.label}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      ))}
    </div>
  );
}
