import { useState, useMemo } from "react";
import { ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { ToolRagConfig } from "@/types/bot";

export interface ModelOption {
  value: string;
  label: string;
}

export interface ToolRagInherited {
  rag_top_k: number;
  rag_score_threshold: number;
  rerank_enabled: boolean;
  rerank_model: string;
  rerank_top_n: number;
}

export interface ToolRagConfigSectionProps {
  /** Tool 識別名稱（e.g. "rag_query"），用於組 DOM id */
  toolName: string;
  /** Tool 顯示名稱（e.g. "知識庫查詢"） */
  toolLabel: string;
  /** 當前覆蓋值；undefined 代表完全繼承 */
  value?: ToolRagConfig;
  /** 繼承值（用於 placeholder 顯示），所有欄位必填 */
  inherited: ToolRagInherited;
  /** placeholder 附加說明（例："繼承 Bot 預設" / "繼承自 Bot 的 rag_query"） */
  inheritedLabel?: string;
  onChange: (v: ToolRagConfig | undefined) => void;
  /** rerank_model 下拉選項 */
  rerankModelOptions?: ModelOption[];
  /** 外部控制展開狀態；未傳則 uncontrolled */
  defaultExpanded?: boolean;
  className?: string;
}

const INHERIT_SENTINEL = "__inherit__";

/**
 * 正規化 override：過濾掉 undefined / null / "" 的 key，
 * 若 override 為空則回傳 undefined（代表完全繼承）。
 */
function normalize(override: ToolRagConfig): ToolRagConfig | undefined {
  const out: ToolRagConfig = {};
  if (override.rag_top_k !== undefined) out.rag_top_k = override.rag_top_k;
  if (override.rag_score_threshold !== undefined)
    out.rag_score_threshold = override.rag_score_threshold;
  if (override.rerank_enabled !== undefined)
    out.rerank_enabled = override.rerank_enabled;
  if (override.rerank_model !== undefined && override.rerank_model !== "")
    out.rerank_model = override.rerank_model;
  if (override.rerank_top_n !== undefined)
    out.rerank_top_n = override.rerank_top_n;
  return Object.keys(out).length === 0 ? undefined : out;
}

export function ToolRagConfigSection({
  toolName,
  toolLabel,
  value,
  inherited,
  inheritedLabel = "繼承預設",
  onChange,
  rerankModelOptions = [],
  defaultExpanded = false,
  className,
}: ToolRagConfigSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const overridden = value !== undefined && Object.keys(value).length > 0;

  const placeholders = useMemo(
    () => ({
      topK: `${inherited.rag_top_k}（${inheritedLabel}）`,
      threshold: `${inherited.rag_score_threshold}（${inheritedLabel}）`,
      rerankModel: `${inherited.rerank_model || "未設定"}（${inheritedLabel}）`,
      rerankTopN: `${inherited.rerank_top_n}（${inheritedLabel}）`,
    }),
    [inherited, inheritedLabel],
  );

  const patchField = (
    field: keyof ToolRagConfig,
    next: number | boolean | string | undefined,
  ) => {
    const merged: ToolRagConfig = { ...(value ?? {}) };
    if (next === undefined || next === "" || (typeof next === "number" && Number.isNaN(next))) {
      delete merged[field];
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (merged as any)[field] = next;
    }
    onChange(normalize(merged));
  };

  const handleReset = () => {
    onChange(undefined);
  };

  const rerankEnabledValue: string =
    value?.rerank_enabled === true
      ? "true"
      : value?.rerank_enabled === false
        ? "false"
        : INHERIT_SENTINEL;

  const idPrefix = `tool-rag-${toolName}`;

  return (
    <div
      className={cn(
        "rounded-md border bg-muted/20 px-3 py-2 flex flex-col gap-2",
        className,
      )}
      data-tool-name={toolName}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium">{toolLabel}</span>
          {overridden && (
            <span
              className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary"
              data-testid={`${idPrefix}-overridden-badge`}
            >
              自訂
            </span>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={() => setExpanded((prev) => !prev)}
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          進階設定
        </Button>
      </div>

      {expanded && (
        <div className="flex flex-col gap-3 pt-1">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${idPrefix}-top-k`} className="text-xs">
                Top K（1-50）
              </Label>
              <Input
                id={`${idPrefix}-top-k`}
                type="number"
                min={1}
                max={50}
                value={value?.rag_top_k ?? ""}
                placeholder={placeholders.topK}
                onChange={(e) => {
                  const raw = e.target.value;
                  patchField("rag_top_k", raw === "" ? undefined : Number(raw));
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${idPrefix}-threshold`} className="text-xs">
                分數閾值（0-1）
              </Label>
              <Input
                id={`${idPrefix}-threshold`}
                type="number"
                step={0.05}
                min={0}
                max={1}
                value={value?.rag_score_threshold ?? ""}
                placeholder={placeholders.threshold}
                onChange={(e) => {
                  const raw = e.target.value;
                  patchField(
                    "rag_score_threshold",
                    raw === "" ? undefined : Number(raw),
                  );
                }}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${idPrefix}-rerank-enabled`} className="text-xs">
                Reranking
              </Label>
              <Select
                value={rerankEnabledValue}
                onValueChange={(v) => {
                  if (v === INHERIT_SENTINEL) {
                    patchField("rerank_enabled", undefined);
                  } else {
                    patchField("rerank_enabled", v === "true");
                  }
                }}
              >
                <SelectTrigger id={`${idPrefix}-rerank-enabled`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={INHERIT_SENTINEL}>
                    跟隨繼承（{inherited.rerank_enabled ? "開" : "關"}）
                  </SelectItem>
                  <SelectItem value="true">強制開啟</SelectItem>
                  <SelectItem value="false">強制關閉</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${idPrefix}-rerank-top-n`} className="text-xs">
                Rerank Top N（5-50）
              </Label>
              <Input
                id={`${idPrefix}-rerank-top-n`}
                type="number"
                min={5}
                max={50}
                value={value?.rerank_top_n ?? ""}
                placeholder={placeholders.rerankTopN}
                onChange={(e) => {
                  const raw = e.target.value;
                  patchField(
                    "rerank_top_n",
                    raw === "" ? undefined : Number(raw),
                  );
                }}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`${idPrefix}-rerank-model`} className="text-xs">
              Rerank 模型
            </Label>
            <Select
              value={value?.rerank_model ?? INHERIT_SENTINEL}
              onValueChange={(v) => {
                if (v === INHERIT_SENTINEL) {
                  patchField("rerank_model", undefined);
                } else {
                  patchField("rerank_model", v);
                }
              }}
            >
              <SelectTrigger id={`${idPrefix}-rerank-model`}>
                <SelectValue placeholder={placeholders.rerankModel} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={INHERIT_SENTINEL}>
                  {placeholders.rerankModel}
                </SelectItem>
                {rerankModelOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex justify-end pt-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={handleReset}
              disabled={!overridden}
            >
              <RotateCcw className="h-3.5 w-3.5" />
              重設為繼承
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
