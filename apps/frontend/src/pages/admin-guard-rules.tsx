import { Fragment, useEffect, useState } from "react";
import {
  Plus,
  Trash2,
  RotateCcw,
  Loader2,
  Shield,
  ShieldAlert,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ModelSelect } from "@/components/shared/model-select";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import {
  useGuardRules,
  useUpdateGuardRules,
  useResetGuardRules,
  useGuardLogs,
  type GuardRuleItem,
  type OutputKeywordItem,
} from "@/features/security/hooks/use-guard-rules";

export default function AdminGuardRulesPage() {
  const [activeTab, setActiveTab] = useState<"rules" | "logs">("rules");
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(new Set());

  const toggleLogExpanded = (id: string) => {
    setExpandedLogIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6" />
          安全規則
        </h1>
        <p className="text-muted-foreground">
          管理 Prompt Injection 防護規則與攔截記錄。
        </p>
      </div>

      <div className="flex gap-2 border-b pb-2">
        <Button
          variant="ghost"
          size="sm"
          className={activeTab === "rules" ? "bg-muted font-semibold" : ""}
          onClick={() => setActiveTab("rules")}
        >
          防護規則
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={activeTab === "logs" ? "bg-muted font-semibold" : ""}
          onClick={() => setActiveTab("logs")}
        >
          攔截記錄
        </Button>
      </div>

      {activeTab === "rules" ? <GuardRulesEditor /> : <GuardLogsTable />}
    </div>
  );
}

function GuardRulesEditor() {
  const { data: config, isLoading } = useGuardRules();
  const updateMutation = useUpdateGuardRules();
  const resetMutation = useResetGuardRules();
  const { data: enabledModels } = useEnabledModels();

  const [inputRules, setInputRules] = useState<GuardRuleItem[]>([]);
  const [outputKeywords, setOutputKeywords] = useState<OutputKeywordItem[]>([]);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [llmModel, setLlmModel] = useState("");
  const [inputPrompt, setInputPrompt] = useState("");
  const [outputPrompt, setOutputPrompt] = useState("");
  const [blockedResponse, setBlockedResponse] = useState("");

  useEffect(() => {
    if (config) {
      setInputRules(config.input_rules);
      setOutputKeywords(config.output_keywords);
      setLlmEnabled(config.llm_guard_enabled);
      setLlmModel(config.llm_guard_model);
      setInputPrompt(config.input_guard_prompt);
      setOutputPrompt(config.output_guard_prompt);
      setBlockedResponse(config.blocked_response);
    }
  }, [config]);

  const handleSave = () => {
    updateMutation.mutate({
      input_rules: inputRules,
      output_keywords: outputKeywords,
      llm_guard_enabled: llmEnabled,
      llm_guard_model: llmModel === "__none__" ? "" : llmModel,
      input_guard_prompt: inputPrompt,
      output_guard_prompt: outputPrompt,
      blocked_response: blockedResponse,
    });
  };

  const addInputRule = () => {
    setInputRules([...inputRules, { pattern: "", type: "keyword", enabled: true }]);
  };

  const addOutputKeyword = () => {
    setOutputKeywords([...outputKeywords, { keyword: "", enabled: true }]);
  };

  if (isLoading) {
    return <p className="text-muted-foreground">載入中...</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Input Rules */}
      <div className="rounded-lg border p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">輸入過濾規則</h3>
          <Button variant="outline" size="sm" onClick={addInputRule}>
            <Plus className="h-3.5 w-3.5 mr-1" /> 新增規則
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          用戶訊息命中規則時直接攔截，不送進 AI。
        </p>
        {inputRules.map((rule, i) => (
          <div key={i} className="flex items-center gap-2">
            <Switch
              checked={rule.enabled}
              onCheckedChange={(v) => {
                const next = [...inputRules];
                next[i] = { ...next[i], enabled: v };
                setInputRules(next);
              }}
            />
            <Select
              value={rule.type}
              onValueChange={(v) => {
                const next = [...inputRules];
                next[i] = { ...next[i], type: v as "regex" | "keyword" };
                setInputRules(next);
              }}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="regex">Regex</SelectItem>
                <SelectItem value="keyword">Keyword</SelectItem>
              </SelectContent>
            </Select>
            <Input
              className="flex-1"
              value={rule.pattern}
              onChange={(e) => {
                const next = [...inputRules];
                next[i] = { ...next[i], pattern: e.target.value };
                setInputRules(next);
              }}
              placeholder="規則 pattern"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setInputRules(inputRules.filter((_, j) => j !== i))}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        ))}
      </div>

      {/* Output Keywords */}
      <div className="rounded-lg border p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">輸出過濾關鍵詞</h3>
          <Button variant="outline" size="sm" onClick={addOutputKeyword}>
            <Plus className="h-3.5 w-3.5 mr-1" /> 新增關鍵詞
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          AI 回答命中 2 個以上關鍵詞時判定為洩露。
        </p>
        {outputKeywords.map((kw, i) => (
          <div key={i} className="flex items-center gap-2">
            <Switch
              checked={kw.enabled}
              onCheckedChange={(v) => {
                const next = [...outputKeywords];
                next[i] = { ...next[i], enabled: v };
                setOutputKeywords(next);
              }}
            />
            <Input
              className="flex-1"
              value={kw.keyword}
              onChange={(e) => {
                const next = [...outputKeywords];
                next[i] = { ...next[i], keyword: e.target.value };
                setOutputKeywords(next);
              }}
              placeholder="關鍵詞"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setOutputKeywords(outputKeywords.filter((_, j) => j !== i))}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        ))}
      </div>

      {/* LLM Guard */}
      <div className="rounded-lg border p-4 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">LLM Guard 二次確認</h3>
          <Switch checked={llmEnabled} onCheckedChange={setLlmEnabled} />
        </div>
        <p className="text-xs text-muted-foreground">
          啟用後，輸出可疑時用 LLM 二次判斷是否洩露。會消耗少量 token。
        </p>
        {llmEnabled && (
          <>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">Guard 模型</Label>
              <ModelSelect
                value={llmModel}
                onValueChange={setLlmModel}
                enabledModels={enabledModels}
                placeholder="系統預設（Haiku）"
                allowEmpty
                emptyLabel="系統預設（Haiku）"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">輸入檢查 Prompt</Label>
              <Textarea
                rows={6}
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="留空使用預設 prompt..."
              />
              <p className="text-xs text-muted-foreground">
                變數：<code className="rounded bg-muted px-1">{"{user_message}"}</code>
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-sm">輸出檢查 Prompt</Label>
              <Textarea
                rows={6}
                value={outputPrompt}
                onChange={(e) => setOutputPrompt(e.target.value)}
                placeholder="留空使用預設 prompt..."
              />
              <p className="text-xs text-muted-foreground">
                變數：<code className="rounded bg-muted px-1">{"{ai_response}"}</code>
              </p>
            </div>
          </>
        )}
      </div>

      {/* Blocked Response */}
      <div className="rounded-lg border p-4 flex flex-col gap-2">
        <Label className="text-sm font-semibold">被攔截時回覆</Label>
        <Textarea
          rows={2}
          value={blockedResponse}
          onChange={(e) => setBlockedResponse(e.target.value)}
          placeholder="我只能協助您處理客服相關問題。"
        />
      </div>

      {/* Actions */}
      <div className="flex gap-2 justify-end">
        <Button
          variant="outline"
          onClick={() => resetMutation.mutate()}
          disabled={resetMutation.isPending}
        >
          <RotateCcw className="h-4 w-4 mr-1" />
          重置為預設
        </Button>
        <Button onClick={handleSave} disabled={updateMutation.isPending}>
          {updateMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1" />
          ) : null}
          儲存規則
        </Button>
      </div>
    </div>
  );
}

function GuardLogsTable() {
  const [page, setPage] = useState(1);
  const [logType, setLogType] = useState<string>("");
  const { data, isLoading } = useGuardLogs(
    page,
    20,
    logType || undefined,
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Select value={logType} onValueChange={setLogType}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="全部類型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部類型</SelectItem>
            <SelectItem value="input_blocked">輸入攔截</SelectItem>
            <SelectItem value="output_blocked">輸出攔截</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading && <p className="text-muted-foreground">載入中...</p>}

      {data && data.items.length === 0 && (
        <div className="rounded-md border border-dashed p-8 text-center text-muted-foreground">
          <ShieldAlert className="h-8 w-8 mx-auto mb-2 opacity-50" />
          尚無攔截記錄
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left w-[40px]"></th>
                <th className="px-3 py-2 text-left">時間</th>
                <th className="px-3 py-2 text-left">類型</th>
                <th className="px-3 py-2 text-left">命中規則</th>
                <th className="px-3 py-2 text-left">用戶訊息</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((log) => {
                const isExpanded = expandedLogIds.has(log.id);
                return (
                  <Fragment key={log.id}>
                    <tr
                      className="border-b hover:bg-muted/30 cursor-pointer"
                      onClick={() => toggleLogExpanded(log.id)}
                    >
                      <td className="px-3 py-2 text-muted-foreground">
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">
                        {new Date(log.created_at).toLocaleString("zh-TW")}
                      </td>
                      <td className="px-3 py-2">
                        <Badge
                          variant={
                            log.log_type === "input_blocked"
                              ? "destructive"
                              : "secondary"
                          }
                          className="text-xs"
                        >
                          {log.log_type === "input_blocked" ? "輸入攔截" : "輸出攔截"}
                        </Badge>
                      </td>
                      <td
                        className="px-3 py-2 text-xs font-mono max-w-[200px] truncate"
                        title={log.rule_matched}
                      >
                        {log.rule_matched}
                      </td>
                      <td
                        className="px-3 py-2 text-xs max-w-[400px] truncate"
                        title={log.user_message ?? ""}
                      >
                        {log.user_message}
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="border-b bg-muted/10">
                        <td></td>
                        <td colSpan={4} className="px-3 py-3 space-y-2 text-xs">
                          <div>
                            <div className="font-medium text-muted-foreground mb-1">
                              命中規則
                            </div>
                            <div className="font-mono break-all rounded bg-background border px-2 py-1.5">
                              {log.rule_matched}
                            </div>
                          </div>
                          <div>
                            <div className="font-medium text-muted-foreground mb-1">
                              用戶訊息（完整）
                            </div>
                            <div className="whitespace-pre-wrap break-all rounded bg-background border px-2 py-1.5 max-h-[200px] overflow-y-auto">
                              {log.user_message || (
                                <span className="text-muted-foreground italic">（無）</span>
                              )}
                            </div>
                          </div>
                          {log.ai_response && (
                            <div>
                              <div className="font-medium text-muted-foreground mb-1">
                                AI 回應（完整）
                              </div>
                              <div className="whitespace-pre-wrap break-all rounded bg-background border px-2 py-1.5 max-h-[200px] overflow-y-auto">
                                {log.ai_response}
                              </div>
                            </div>
                          )}
                          {(log.tenant_id || log.bot_id || log.user_id) && (
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground pt-1">
                              {log.tenant_id && (
                                <span>tenant: <code className="font-mono">{log.tenant_id}</code></span>
                              )}
                              {log.bot_id && (
                                <span>bot: <code className="font-mono">{log.bot_id}</code></span>
                              )}
                              {log.user_id && (
                                <span>user: <code className="font-mono">{log.user_id}</code></span>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex gap-2 justify-center">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            上一頁
          </Button>
          <span className="text-sm text-muted-foreground self-center">
            {page} / {data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.total_pages}
            onClick={() => setPage(page + 1)}
          >
            下一頁
          </Button>
        </div>
      )}
    </div>
  );
}
