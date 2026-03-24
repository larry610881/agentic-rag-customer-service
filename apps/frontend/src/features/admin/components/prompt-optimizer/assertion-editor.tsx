import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Trash2 } from "lucide-react";

interface AssertionConfig {
  type: string;
  params: Record<string, unknown>;
}

interface AssertionEditorProps {
  assertions: AssertionConfig[];
  onChange: (assertions: AssertionConfig[]) => void;
}

// 26 assertion types grouped by category — matches backend assertions.py
const ASSERTION_GROUPS = [
  {
    group: "格式",
    items: [
      { value: "max_length", label: "最大長度限制", params: ["max_chars"] },
      { value: "min_length", label: "最小長度限制", params: ["min_chars"] },
      { value: "language_match", label: "語言匹配", params: ["expected"] },
      { value: "starts_with_any", label: "開頭匹配", params: ["prefixes"] },
      { value: "latency_under", label: "延遲限制 (ms)", params: ["max_ms"] },
    ],
  },
  {
    group: "內容",
    items: [
      { value: "contains_all", label: "包含所有關鍵字", params: ["keywords"] },
      { value: "contains_any", label: "包含任一關鍵字", params: ["keywords"] },
      { value: "not_contains", label: "不包含敏感詞", params: ["keywords"] },
      { value: "regex_match", label: "正則匹配", params: ["pattern"] },
      {
        value: "no_hallucination_markers",
        label: "無幻覺標記",
        params: [] as string[],
      },
      { value: "has_citations", label: "包含引用來源", params: ["min_count"] },
      {
        value: "references_history",
        label: "引用歷史對話",
        params: ["must_reference"],
      },
    ],
  },
  {
    group: "行為",
    items: [
      {
        value: "tool_was_called",
        label: "呼叫特定工具",
        params: ["tool_name"],
      },
      {
        value: "tool_not_called",
        label: "不呼叫特定工具",
        params: ["tool_name"],
      },
      {
        value: "tool_call_count",
        label: "工具呼叫次數",
        params: ["min", "max"],
      },
      {
        value: "refused_gracefully",
        label: "優雅拒絕",
        params: [] as string[],
      },
    ],
  },
  {
    group: "品質與成本",
    items: [
      {
        value: "source_relevance_above",
        label: "來源相關度",
        params: ["min_score"],
      },
      {
        value: "response_not_empty",
        label: "回應非空",
        params: [] as string[],
      },
      {
        value: "sentiment_positive",
        label: "正面語氣",
        params: [] as string[],
      },
      {
        value: "token_count_under",
        label: "Token 數量限制",
        params: ["max_tokens"],
      },
      { value: "cost_under", label: "成本限制", params: ["max_cost"] },
      {
        value: "output_tokens_under",
        label: "輸出 Token 限制",
        params: ["max_tokens"],
      },
    ],
  },
  {
    group: "安全",
    items: [
      {
        value: "no_system_prompt_leak",
        label: "不洩露系統提示詞",
        params: ["prompt_fragments"],
      },
      {
        value: "no_role_switch",
        label: "不接受角色切換",
        params: [] as string[],
      },
      { value: "no_pii_leak", label: "不洩露個資", params: [] as string[] },
      {
        value: "no_instruction_override",
        label: "不執行偽指令",
        params: ["forbidden"],
      },
    ],
  },
];

// Params that should be arrays (comma-separated input → string[])
const ARRAY_PARAMS = new Set([
  "keywords",
  "prefixes",
  "prompt_fragments",
  "forbidden",
  "must_reference",
]);

// Params that should be numbers
const NUMBER_PARAMS = new Set([
  "max_chars",
  "min_chars",
  "max_ms",
  "max_tokens",
  "min_count",
  "min",
  "max",
]);

// Params that should be floats
const FLOAT_PARAMS = new Set(["min_score", "max_cost"]);

// Placeholder hints
const PARAM_PLACEHOLDERS: Record<string, string> = {
  keywords: "退貨, 退款, 退換貨（逗號分隔）",
  prefixes: "您好, 歡迎（逗號分隔）",
  prompt_fragments: "行為準則, 推理策略（逗號分隔）",
  forbidden: "已停止營業, 競品（逗號分隔）",
  must_reference: "關鍵字1, 關鍵字2（逗號分隔）",
  pattern: "正則表達式，如 \\d+",
  tool_name: "rag_query / query_products / query_courses",
  expected: "zh-TW",
  max_chars: "2000",
  min_chars: "10",
  max_ms: "5000",
  max_tokens: "3000",
  min_count: "1",
  min: "0",
  max: "5",
  min_score: "0.5",
  max_cost: "0.01",
};

function findAssertionMeta(type: string) {
  for (const g of ASSERTION_GROUPS) {
    for (const item of g.items) {
      if (item.value === type) return item;
    }
  }
  return null;
}

function getDefaultParams(type: string): Record<string, unknown> {
  const meta = findAssertionMeta(type);
  if (!meta) return {};
  const params: Record<string, unknown> = {};
  for (const key of meta.params) {
    if (ARRAY_PARAMS.has(key)) params[key] = [];
    else if (NUMBER_PARAMS.has(key)) params[key] = 0;
    else if (FLOAT_PARAMS.has(key)) params[key] = 0;
    else params[key] = "";
  }
  return params;
}

/** Convert display value to stored value */
function parseParamValue(
  key: string,
  raw: string,
): string | number | string[] {
  if (ARRAY_PARAMS.has(key)) {
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (NUMBER_PARAMS.has(key)) return parseInt(raw, 10) || 0;
  if (FLOAT_PARAMS.has(key)) return parseFloat(raw) || 0;
  return raw;
}

/** Convert stored value to display value */
function formatParamValue(key: string, value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  return String(value ?? "");
}

export function AssertionEditor({ assertions, onChange }: AssertionEditorProps) {
  const addAssertion = () => {
    onChange([
      ...assertions,
      { type: "contains_any", params: { keywords: [] } },
    ]);
  };

  const removeAssertion = (index: number) => {
    onChange(assertions.filter((_, i) => i !== index));
  };

  const updateType = (index: number, type: string) => {
    const updated = [...assertions];
    updated[index] = { type, params: getDefaultParams(type) };
    onChange(updated);
  };

  const updateParam = (index: number, key: string, rawValue: string) => {
    const updated = [...assertions];
    updated[index] = {
      ...updated[index],
      params: {
        ...updated[index].params,
        [key]: parseParamValue(key, rawValue),
      },
    };
    onChange(updated);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>檢查規則</Label>
        <Button variant="outline" size="sm" onClick={addAssertion}>
          <Plus className="mr-1 size-4" />
          新增規則
        </Button>
      </div>

      {assertions.length === 0 && (
        <p className="py-4 text-center text-sm text-muted-foreground">
          尚未設定檢查規則，點擊「新增規則」開始設定
        </p>
      )}

      {assertions.map((assertion, index) => {
        const meta = findAssertionMeta(assertion.type);
        const paramKeys = meta?.params ?? Object.keys(assertion.params);
        const label = meta?.label ?? assertion.type;

        return (
          <div
            key={index}
            className="flex items-start gap-2 rounded-md border p-3"
          >
            <div className="flex-1 space-y-2">
              <Select
                value={assertion.type}
                onValueChange={(v) => updateType(index, v)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue>{label}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {ASSERTION_GROUPS.map((g) => (
                    <SelectGroup key={g.group}>
                      <SelectLabel>{g.group}</SelectLabel>
                      {g.items.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>

              {paramKeys.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {paramKeys.map((key) => (
                    <div key={key} className="min-w-[120px] flex-1">
                      <Label className="text-xs text-muted-foreground">
                        {key}
                      </Label>
                      <Input
                        placeholder={PARAM_PLACEHOLDERS[key] || key}
                        value={formatParamValue(
                          key,
                          assertion.params[key],
                        )}
                        onChange={(e) =>
                          updateParam(index, key, e.target.value)
                        }
                        className="h-8 text-sm"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => removeAssertion(index)}
              className="mt-0.5 text-destructive hover:text-destructive"
            >
              <Trash2 className="size-4" />
            </Button>
          </div>
        );
      })}
    </div>
  );
}

export type { AssertionConfig, AssertionEditorProps };
