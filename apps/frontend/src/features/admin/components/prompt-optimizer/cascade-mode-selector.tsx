import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface CascadeModeSelectorProps {
  value: "single" | "cascade";
  onChange: (value: "single" | "cascade") => void;
  targetField?: string;
  onTargetFieldChange?: (field: string) => void;
}

const TARGET_FIELDS = [
  { value: "base_prompt", label: "基礎 Prompt" },
  { value: "router_prompt", label: "Router 模式 Prompt" },
  { value: "react_prompt", label: "ReAct 模式 Prompt" },
  { value: "system_prompt", label: "系統 Prompt" },
] as const;

export function CascadeModeSelector({
  value,
  onChange,
  targetField,
  onTargetFieldChange,
}: CascadeModeSelectorProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>優化模式</Label>
        <p className="text-xs text-muted-foreground">評估永遠使用完整組合 Prompt</p>
        <div className="flex gap-4">
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="radio"
              name="optimization-mode"
              value="single"
              checked={value === "single"}
              onChange={() => onChange("single")}
              className="accent-primary"
            />
            <div>
              <span className="text-sm">單一層級</span>
              <p className="text-xs text-muted-foreground">
                只優化一個 Prompt 層級，其他層級保持不動
              </p>
            </div>
          </label>
          <label className="flex cursor-pointer items-start gap-2">
            <input
              type="radio"
              name="optimization-mode"
              value="cascade"
              checked={value === "cascade"}
              onChange={() => onChange("cascade")}
              className="mt-1 accent-primary"
            />
            <div>
              <span className="text-sm">串聯優化</span>
              <p className="text-xs text-muted-foreground">
                依序優化多個層級，每層的最佳結果作為下一層的固定 context
              </p>
            </div>
          </label>
        </div>
      </div>

      {value === "single" && (
        <div className="space-y-2 rounded-md border bg-muted/30 p-3">
          <Label>目標 Prompt 層級</Label>
          <Select value={targetField} onValueChange={onTargetFieldChange}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="選擇層級" />
            </SelectTrigger>
            <SelectContent>
              {TARGET_FIELDS.map((f) => (
                <SelectItem key={f.value} value={f.value}>
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            選擇要優化的 Prompt 層級。評估時仍使用完整組合 Prompt（base + mode + bot），但只修改你選擇的那一層。
          </p>
        </div>
      )}

      {value === "cascade" && (
        <div className="space-y-2 rounded-md border bg-muted/30 p-3">
          <p className="text-sm font-medium">串聯順序</p>
          <div className="flex items-center gap-2 text-sm">
            <span className="rounded bg-primary/10 px-2 py-0.5">基礎 Prompt</span>
            <span className="text-muted-foreground">→</span>
            <span className="rounded bg-primary/10 px-2 py-0.5">模式 Prompt</span>
            <span className="text-xs text-muted-foreground">(Router/ReAct)</span>
            <span className="text-muted-foreground">→</span>
            <span className="rounded bg-primary/10 px-2 py-0.5">Bot 系統 Prompt</span>
          </div>
          <p className="text-xs text-muted-foreground">
            先優化基礎 Prompt 取得最佳版本，鎖定後再優化模式 Prompt，最後優化 Bot 專屬 Prompt。每一層都在前一層的最佳結果上疊加。
          </p>
        </div>
      )}
    </div>
  );
}
