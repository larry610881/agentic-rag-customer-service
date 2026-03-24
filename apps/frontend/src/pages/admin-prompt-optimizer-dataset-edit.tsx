import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Database,
  ArrowLeft,
  Plus,
  Trash2,
  Loader2,
  Save,
  ChevronDown,
  ChevronRight,
  MessageSquare,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { ROUTES } from "@/routes/paths";
import {
  useEvalDataset,
  useUpdateEvalDataset,
  useCreateTestCase,
  useDeleteTestCase,
} from "@/hooks/queries/use-prompt-optimizer";
import {
  AssertionEditor,
  type AssertionConfig,
} from "@/features/admin/components/prompt-optimizer/assertion-editor";

// 分類中文對照
const CATEGORY_LABELS: Record<string, string> = {
  "security/direct_override": "直接指令覆蓋",
  "security/role_play": "角色扮演攻擊",
  "security/indirect_injection": "間接注入",
  "security/data_exfil": "資料洩露攻擊",
  "security/encoding_bypass": "編碼混淆繞過",
  "security/functional_abuse": "功能濫用",
  "security/payload_splitting": "分段注入",
  "security/virtualization": "虛擬化沙箱",
  "security/crescendo": "漸進式多輪攻擊",
  "security/language_switch": "語言切換繞過",
  "security/few_shot": "Few-Shot 誘導",
  "security/delimiter_confusion": "分隔符混淆",
  "security/memory_poisoning": "記憶污染",
  "security/tool_manipulation": "工具操控",
  "course/browse": "課程瀏覽",
  "course/price": "課程價格",
  "course/vacancy": "課程名額",
  "course/lector": "講師資訊",
  "course/category": "課程分類",
  "course/detail": "課程詳情",
  "product/browse": "商品瀏覽",
  "product/price": "商品價格",
  "product/recommend": "商品推薦",
  "rag/policy": "政策查詢",
  "rag/faq": "常見問題",
  "rag/about": "品牌介紹",
  cross_tool: "跨工具場景",
  greeting: "問候寒暄",
  out_of_scope: "超出範圍",
  multiturn: "多輪對話",
  return_policy: "退貨政策",
  product_recommendation: "商品推薦",
};

// Assertion type 中文對照
const ASSERTION_LABELS: Record<string, string> = {
  no_system_prompt_leak: "不洩露系統提示詞",
  refused_gracefully: "優雅拒絕",
  not_contains: "不包含敏感詞",
  no_role_switch: "不接受角色切換",
  no_instruction_override: "不執行偽指令",
  no_pii_leak: "不洩露個資",
  contains_any: "包含任一關鍵字",
  contains_all: "包含所有關鍵字",
  tool_not_called: "不呼叫特定工具",
  tool_was_called: "呼叫特定工具",
  tool_call_count: "工具呼叫次數",
  response_not_empty: "回應非空",
  max_length: "最大長度限制",
  min_length: "最小長度限制",
  language_match: "語言匹配",
  regex_match: "正則匹配",
  has_citations: "包含引用來源",
  sentiment_positive: "正面語氣",
  no_hallucination_markers: "無幻覺標記",
  token_count_under: "Token 數量限制",
  cost_under: "成本限制",
  output_tokens_under: "輸出 Token 限制",
  source_relevance_above: "來源相關度",
  starts_with_any: "開頭匹配",
  latency_under: "延遲限制",
  references_history: "引用歷史對話",
};

interface TestCaseData {
  id: string;
  case_id: string;
  question: string;
  priority: string;
  category: string;
  assertions: { type: string; params?: Record<string, unknown> }[];
  conversation_history?: { role: string; content: string }[];
}

export default function AdminPromptOptimizerDatasetEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: dataset, isLoading } = useEvalDataset(id ?? "");
  const updateMutation = useUpdateEvalDataset();
  const createCaseMutation = useCreateTestCase();
  const deleteCaseMutation = useDeleteTestCase();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameInitialized, setNameInitialized] = useState(false);

  // Expanded rows
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  // Selected rows for batch delete
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  if (dataset && !nameInitialized) {
    setName(dataset.name);
    setDescription(dataset.description ?? "");
    setNameInitialized(true);
  }

  // New test case form
  const [newUserInput, setNewUserInput] = useState("");
  const [newCaseId, setNewCaseId] = useState("");
  const [newPriority, setNewPriority] = useState("P1");
  const [newCategory, setNewCategory] = useState("");
  const [newAssertions, setNewAssertions] = useState<AssertionConfig[]>([]);
  const [newHistory, setNewHistory] = useState<
    { role: string; content: string }[]
  >([]);

  const handleUpdateDataset = () => {
    if (!id || !name.trim()) return;
    updateMutation.mutate(
      { id, name: name.trim(), description: description.trim() || undefined },
      {
        onSuccess: () => toast.success("情境集已更新"),
        onError: () => toast.error("更新失敗"),
      },
    );
  };

  const handleAddCase = () => {
    if (!id || !newUserInput.trim() || !newCaseId.trim()) return;
    const filteredHistory = newHistory.filter((h) => h.content.trim());
    createCaseMutation.mutate(
      {
        datasetId: id,
        case_id: newCaseId.trim(),
        question: newUserInput.trim(),
        priority: newPriority,
        category: newCategory.trim() || undefined,
        assertions: newAssertions.length > 0 ? newAssertions : undefined,
        conversation_history:
          filteredHistory.length > 0 ? filteredHistory : undefined,
      } as never,
      {
        onSuccess: () => {
          toast.success("測試案例已新增");
          setNewUserInput("");
          setNewCaseId("");
          setNewCategory("");
          setNewAssertions([]);
          setNewHistory([]);
        },
        onError: () => toast.error("新增測試案例失敗"),
      },
    );
  };

  const addHistoryMessage = () => {
    setNewHistory([...newHistory, { role: "user", content: "" }]);
  };

  const updateHistoryMessage = (
    index: number,
    field: "role" | "content",
    value: string,
  ) => {
    const updated = [...newHistory];
    updated[index] = { ...updated[index], [field]: value };
    setNewHistory(updated);
  };

  const removeHistoryMessage = (index: number) => {
    setNewHistory(newHistory.filter((_, i) => i !== index));
  };

  const handleDeleteCase = (caseId: string) => {
    if (!id) return;
    deleteCaseMutation.mutate(
      { datasetId: id, caseId },
      {
        onSuccess: () => {
          toast.success("測試案例已刪除");
          setSelectedIds((prev) => {
            const next = new Set(prev);
            next.delete(caseId);
            return next;
          });
        },
        onError: () => toast.error("刪除失敗"),
      },
    );
  };

  const handleBatchDelete = () => {
    if (!id || selectedIds.size === 0) return;
    const ids = Array.from(selectedIds);
    let completed = 0;
    for (const caseId of ids) {
      deleteCaseMutation.mutate(
        { datasetId: id, caseId },
        {
          onSuccess: () => {
            completed++;
            if (completed === ids.length) {
              toast.success(`已刪除 ${ids.length} 個測試案例`);
              setSelectedIds(new Set());
            }
          },
          onError: () => toast.error("部分刪除失敗"),
        },
      );
    }
  };

  const toggleExpand = (tcId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(tcId)) next.delete(tcId);
      else next.add(tcId);
      return next;
    });
  };

  const toggleSelect = (tcId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(tcId)) next.delete(tcId);
      else next.add(tcId);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!dataset?.test_cases) return;
    if (selectedIds.size === dataset.test_cases.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(dataset.test_cases.map((tc: TestCaseData) => tc.id)));
    }
  };

  const allSelected =
    dataset?.test_cases?.length && selectedIds.size === dataset.test_cases.length;

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[200px] w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <Button
          variant="ghost"
          size="sm"
          className="mb-2"
          onClick={() => navigate(ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASETS)}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          返回情境集列表
        </Button>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Database className="h-6 w-6" />
          編輯情境集
        </h1>
        <p className="mt-1 text-muted-foreground">
          編輯情境集內容與測試案例
        </p>
      </div>

      {/* Dataset metadata */}
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>基本資訊</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="edit-name">名稱</Label>
            <Input
              id="edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-desc">描述</Label>
            <Textarea
              id="edit-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          <div className="flex justify-end">
            <Button
              onClick={handleUpdateDataset}
              disabled={!name.trim() || updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              儲存
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Add test case */}
      <Card>
        <CardHeader>
          <CardTitle>新增測試案例</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Row 1: ID, Priority, Category */}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="case-id">案例 ID</Label>
              <Input
                id="case-id"
                placeholder="如 sec-custom-01"
                value={newCaseId}
                onChange={(e) => setNewCaseId(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="priority">優先級</Label>
              <select
                id="priority"
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value)}
              >
                <option value="P0">P0 - 必過（失敗則整體歸零）</option>
                <option value="P1">P1 - 應過</option>
                <option value="P2">P2 - 加分</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="category">分類</Label>
              <Input
                id="category"
                placeholder="如 security/role_play"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
              />
            </div>
          </div>

          {/* Row 2: Question */}
          <div className="space-y-2">
            <Label htmlFor="user-input">攻擊提示詞 / 測試問題</Label>
            <Textarea
              id="user-input"
              placeholder="模擬攻擊者的問題或指令"
              value={newUserInput}
              onChange={(e) => setNewUserInput(e.target.value)}
              rows={3}
            />
          </div>

          {/* Row 3: Conversation History */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="flex items-center gap-1.5">
                <MessageSquare className="h-3.5 w-3.5" />
                對話歷史
                <span className="font-normal text-muted-foreground">
                  （選填，用於模擬多輪/間接注入攻擊）
                </span>
              </Label>
              <Button
                variant="outline"
                size="sm"
                onClick={addHistoryMessage}
              >
                <Plus className="mr-1 h-3.5 w-3.5" />
                新增對話
              </Button>
            </div>
            {newHistory.length === 0 && (
              <p className="text-xs text-muted-foreground">
                無對話歷史。適用於 Payload Splitting、Crescendo、間接注入等多輪攻擊場景。
              </p>
            )}
            {newHistory.map((msg, i) => (
              <div key={i} className="flex items-start gap-2">
                <select
                  className="h-9 w-[100px] rounded-md border bg-background px-2 text-sm"
                  value={msg.role}
                  onChange={(e) =>
                    updateHistoryMessage(i, "role", e.target.value)
                  }
                >
                  <option value="user">User</option>
                  <option value="assistant">AI</option>
                </select>
                <Textarea
                  className="min-h-[36px] flex-1 text-sm"
                  rows={2}
                  placeholder={
                    msg.role === "user"
                      ? "使用者訊息（可包含偽造的 [SYSTEM] 標記等）"
                      : "AI 回覆（可模擬已被攻破的回覆）"
                  }
                  value={msg.content}
                  onChange={(e) =>
                    updateHistoryMessage(i, "content", e.target.value)
                  }
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="mt-0.5 h-8 w-8 text-destructive/70 hover:text-destructive"
                  onClick={() => removeHistoryMessage(i)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>

          <Separator />

          {/* Row 4: Assertions */}
          <AssertionEditor
            assertions={newAssertions}
            onChange={setNewAssertions}
          />

          {/* Submit */}
          <div className="flex justify-end">
            <Button
              onClick={handleAddCase}
              disabled={
                !newUserInput.trim() ||
                !newCaseId.trim() ||
                createCaseMutation.isPending
              }
            >
              {createCaseMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              新增案例
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Test cases list */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              測試案例 ({dataset?.test_cases?.length ?? 0})
            </CardTitle>
            {selectedIds.size > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleBatchDelete}
                disabled={deleteCaseMutation.isPending}
              >
                {deleteCaseMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-4 w-4" />
                )}
                刪除已選 ({selectedIds.size})
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!dataset?.test_cases?.length ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              尚無測試案例，請使用上方表單新增
            </p>
          ) : (
            <div className="space-y-0">
              {/* Header row */}
              <div className="flex items-center gap-3 border-b px-2 py-2 text-xs font-medium text-muted-foreground">
                <div className="w-6">
                  <Checkbox
                    checked={!!allSelected}
                    onCheckedChange={toggleSelectAll}
                  />
                </div>
                <div className="w-5" />
                <div className="w-[130px]">案例 ID</div>
                <div className="w-[50px]">優先級</div>
                <div className="w-[130px]">分類</div>
                <div className="min-w-0 flex-1">問題</div>
                <div className="w-[70px] text-center">檢查規則</div>
                <div className="w-[50px]" />
              </div>

              {/* Case rows */}
              {dataset.test_cases.map((tc: TestCaseData) => {
                const isExpanded = expandedIds.has(tc.id);
                const isSelected = selectedIds.has(tc.id);
                const categoryLabel =
                  CATEGORY_LABELS[tc.category] || tc.category;

                return (
                  <div
                    key={tc.id}
                    className={`border-b last:border-b-0 ${isSelected ? "bg-primary/5" : ""}`}
                  >
                    {/* Summary row */}
                    <div
                      className="flex cursor-pointer items-center gap-3 px-2 py-2.5 transition-colors hover:bg-muted/50"
                      onClick={() => toggleExpand(tc.id)}
                    >
                      <div
                        className="w-6"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelect(tc.id);
                        }}
                      >
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => toggleSelect(tc.id)}
                        />
                      </div>
                      <div className="w-5 text-muted-foreground">
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </div>
                      <div className="w-[130px] font-mono text-xs">
                        {tc.case_id}
                      </div>
                      <div className="w-[50px]">
                        <span
                          className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${
                            tc.priority === "P0"
                              ? "bg-destructive/10 text-destructive"
                              : tc.priority === "P1"
                                ? "bg-yellow-500/10 text-yellow-600"
                                : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {tc.priority}
                        </span>
                      </div>
                      <div className="w-[130px]">
                        <span className="text-xs text-muted-foreground">
                          {categoryLabel}
                        </span>
                      </div>
                      <div className="min-w-0 flex-1 truncate text-sm">
                        {tc.question}
                      </div>
                      <div className="w-[70px] text-center text-xs text-muted-foreground">
                        {tc.assertions?.length ?? 0}
                      </div>
                      <div className="w-[50px]">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive/70 hover:text-destructive"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteCase(tc.id);
                          }}
                          disabled={deleteCaseMutation.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="border-t bg-muted/30 px-6 py-4">
                        <div className="space-y-4">
                          {/* Full question */}
                          <div>
                            <Label className="text-xs text-muted-foreground">
                              完整問題
                            </Label>
                            <p className="mt-1 whitespace-pre-wrap rounded bg-background p-3 text-sm">
                              {tc.question}
                            </p>
                          </div>

                          {/* Conversation history */}
                          {tc.conversation_history &&
                            tc.conversation_history.length > 0 && (
                              <div>
                                <Label className="text-xs text-muted-foreground">
                                  對話歷史（模擬多輪/間接注入）
                                </Label>
                                <div className="mt-1 space-y-2">
                                  {tc.conversation_history.map(
                                    (
                                      msg: { role: string; content: string },
                                      i: number,
                                    ) => (
                                      <div
                                        key={i}
                                        className={`rounded p-2 text-sm ${
                                          msg.role === "assistant"
                                            ? "ml-4 border-l-2 border-primary/30 bg-primary/5"
                                            : "border-l-2 border-yellow-500/30 bg-yellow-500/5"
                                        }`}
                                      >
                                        <span className="text-xs font-medium text-muted-foreground">
                                          {msg.role === "assistant"
                                            ? "AI"
                                            : "User"}
                                          :
                                        </span>
                                        <p className="mt-0.5 whitespace-pre-wrap">
                                          {msg.content}
                                        </p>
                                      </div>
                                    ),
                                  )}
                                </div>
                              </div>
                            )}

                          {/* Assertions */}
                          <div>
                            <Label className="text-xs text-muted-foreground">
                              檢查規則 ({tc.assertions?.length ?? 0})
                            </Label>
                            <div className="mt-1 flex flex-wrap gap-2">
                              {tc.assertions?.map(
                                (
                                  a: {
                                    type: string;
                                    params?: Record<string, unknown>;
                                  },
                                  i: number,
                                ) => (
                                  <Badge
                                    key={i}
                                    variant="outline"
                                    className="text-xs"
                                  >
                                    {ASSERTION_LABELS[a.type] || a.type}
                                    {a.params &&
                                      Object.keys(a.params).length > 0 && (
                                        <span className="ml-1 text-muted-foreground">
                                          (
                                          {Object.entries(a.params)
                                            .map(([k, v]) => {
                                              if (Array.isArray(v))
                                                return `${v.length} 項`;
                                              return String(v);
                                            })
                                            .join(", ")}
                                          )
                                        </span>
                                      )}
                                  </Badge>
                                ),
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
