import { useEffect, useState } from "react";
import { Pencil, Plus, RotateCcw, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  useDiagnosticRules,
  useUpdateDiagnosticRules,
  useResetDiagnosticRules,
} from "@/hooks/queries/use-observability";
import type {
  DiagnosticSingleRule,
  DiagnosticComboRule,
} from "@/types/observability";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/30",
  warning: "bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/30",
  info: "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30",
};

const CATEGORY_LABELS: Record<string, string> = {
  data_source: "資料源",
  rag_strategy: "RAG 策略",
  prompt: "Prompt",
  agent: "Agent",
};

const OP_LABELS: Record<string, string> = {
  "<=": "<=",
  "<": "<",
  ">=": ">=",
  ">": ">",
  "==": "==",
};

function emptySingleRule(): DiagnosticSingleRule {
  return {
    dimension: "", threshold: 0.5, category: "rag_strategy",
    severity: "warning", message: "", suggestion: "",
  };
}

function emptyComboRule(): DiagnosticComboRule {
  return {
    dim_a: "", op_a: ">", threshold_a: 0.5,
    dim_b: "", op_b: "<=", threshold_b: 0.3,
    category: "rag_strategy", severity: "warning",
    dimension: "", message: "", suggestion: "",
  };
}

// -----------------------------------------------------------------------
// Single Rule Edit Dialog
// -----------------------------------------------------------------------

function SingleRuleDialog({
  open, onOpenChange, rule, onSave,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  rule: DiagnosticSingleRule;
  onSave: (r: DiagnosticSingleRule) => void;
}) {
  const [draft, setDraft] = useState(rule);
  useEffect(() => { setDraft(rule); }, [rule]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>編輯單維度規則</DialogTitle></DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>維度名稱</Label>
              <Input value={draft.dimension} onChange={(e) => setDraft({ ...draft, dimension: e.target.value })} />
            </div>
            <div>
              <Label>門檻值</Label>
              <Input type="number" step="0.05" min="0" max="1"
                value={draft.threshold} onChange={(e) => setDraft({ ...draft, threshold: Number(e.target.value) })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>類別</Label>
              <Select value={draft.category} onValueChange={(v) => setDraft({ ...draft, category: v as DiagnosticSingleRule["category"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(CATEGORY_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>嚴重度</Label>
              <Select value={draft.severity} onValueChange={(v) => setDraft({ ...draft, severity: v as DiagnosticSingleRule["severity"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>診斷訊息</Label>
            <Textarea rows={2} value={draft.message} onChange={(e) => setDraft({ ...draft, message: e.target.value })} />
          </div>
          <div>
            <Label>改善建議</Label>
            <Textarea rows={2} value={draft.suggestion} onChange={(e) => setDraft({ ...draft, suggestion: e.target.value })} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={() => { onSave(draft); onOpenChange(false); }}>確認</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// -----------------------------------------------------------------------
// Combo Rule Edit Dialog
// -----------------------------------------------------------------------

function ComboRuleDialog({
  open, onOpenChange, rule, onSave,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  rule: DiagnosticComboRule;
  onSave: (r: DiagnosticComboRule) => void;
}) {
  const [draft, setDraft] = useState(rule);
  useEffect(() => { setDraft(rule); }, [rule]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>編輯交叉維度規則</DialogTitle></DialogHeader>
        <div className="grid gap-4 py-2">
          <div className="text-sm font-medium text-muted-foreground">條件 A</div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>維度</Label>
              <Input value={draft.dim_a} onChange={(e) => setDraft({ ...draft, dim_a: e.target.value })} />
            </div>
            <div>
              <Label>運算子</Label>
              <Select value={draft.op_a} onValueChange={(v) => setDraft({ ...draft, op_a: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(OP_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>門檻</Label>
              <Input type="number" step="0.05" min="0" max="1"
                value={draft.threshold_a} onChange={(e) => setDraft({ ...draft, threshold_a: Number(e.target.value) })} />
            </div>
          </div>
          <div className="text-sm font-medium text-muted-foreground">條件 B</div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label>維度</Label>
              <Input value={draft.dim_b} onChange={(e) => setDraft({ ...draft, dim_b: e.target.value })} />
            </div>
            <div>
              <Label>運算子</Label>
              <Select value={draft.op_b} onValueChange={(v) => setDraft({ ...draft, op_b: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(OP_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>門檻</Label>
              <Input type="number" step="0.05" min="0" max="1"
                value={draft.threshold_b} onChange={(e) => setDraft({ ...draft, threshold_b: Number(e.target.value) })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>類別</Label>
              <Select value={draft.category} onValueChange={(v) => setDraft({ ...draft, category: v as DiagnosticComboRule["category"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(CATEGORY_LABELS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>嚴重度</Label>
              <Select value={draft.severity} onValueChange={(v) => setDraft({ ...draft, severity: v as DiagnosticComboRule["severity"] })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>維度標籤</Label>
            <Input value={draft.dimension} onChange={(e) => setDraft({ ...draft, dimension: e.target.value })} />
          </div>
          <div>
            <Label>診斷訊息</Label>
            <Textarea rows={2} value={draft.message} onChange={(e) => setDraft({ ...draft, message: e.target.value })} />
          </div>
          <div>
            <Label>改善建議</Label>
            <Textarea rows={2} value={draft.suggestion} onChange={(e) => setDraft({ ...draft, suggestion: e.target.value })} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={() => { onSave(draft); onOpenChange(false); }}>確認</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// -----------------------------------------------------------------------
// Main Editor
// -----------------------------------------------------------------------

export function DiagnosticRulesEditor() {
  const { data, isLoading } = useDiagnosticRules();
  const updateMutation = useUpdateDiagnosticRules();
  const resetMutation = useResetDiagnosticRules();

  const [singleRules, setSingleRules] = useState<DiagnosticSingleRule[]>([]);
  const [comboRules, setComboRules] = useState<DiagnosticComboRule[]>([]);
  const [dirty, setDirty] = useState(false);

  // Single rule dialog
  const [singleDialogOpen, setSingleDialogOpen] = useState(false);
  const [editingSingleIdx, setEditingSingleIdx] = useState<number>(-1);
  const [editingSingleRule, setEditingSingleRule] = useState<DiagnosticSingleRule>(emptySingleRule());

  // Combo rule dialog
  const [comboDialogOpen, setComboDialogOpen] = useState(false);
  const [editingComboIdx, setEditingComboIdx] = useState<number>(-1);
  const [editingComboRule, setEditingComboRule] = useState<DiagnosticComboRule>(emptyComboRule());

  useEffect(() => {
    if (data) {
      setSingleRules(data.single_rules);
      setComboRules(data.combo_rules);
      setDirty(false);
    }
  }, [data]);

  function openEditSingle(idx: number) {
    setEditingSingleIdx(idx);
    setEditingSingleRule(singleRules[idx]);
    setSingleDialogOpen(true);
  }

  function openAddSingle() {
    setEditingSingleIdx(-1);
    setEditingSingleRule(emptySingleRule());
    setSingleDialogOpen(true);
  }

  function handleSaveSingle(rule: DiagnosticSingleRule) {
    setSingleRules((prev) => {
      const next = [...prev];
      if (editingSingleIdx >= 0) {
        next[editingSingleIdx] = rule;
      } else {
        next.push(rule);
      }
      return next;
    });
    setDirty(true);
  }

  function removeSingle(idx: number) {
    setSingleRules((prev) => prev.filter((_, i) => i !== idx));
    setDirty(true);
  }

  function openEditCombo(idx: number) {
    setEditingComboIdx(idx);
    setEditingComboRule(comboRules[idx]);
    setComboDialogOpen(true);
  }

  function openAddCombo() {
    setEditingComboIdx(-1);
    setEditingComboRule(emptyComboRule());
    setComboDialogOpen(true);
  }

  function handleSaveCombo(rule: DiagnosticComboRule) {
    setComboRules((prev) => {
      const next = [...prev];
      if (editingComboIdx >= 0) {
        next[editingComboIdx] = rule;
      } else {
        next.push(rule);
      }
      return next;
    });
    setDirty(true);
  }

  function removeCombo(idx: number) {
    setComboRules((prev) => prev.filter((_, i) => i !== idx));
    setDirty(true);
  }

  async function handleSaveAll() {
    try {
      await updateMutation.mutateAsync({
        single_rules: singleRules,
        combo_rules: comboRules,
      });
      toast.success("診斷規則已儲存");
      setDirty(false);
    } catch {
      toast.error("儲存失敗");
    }
  }

  async function handleReset() {
    try {
      await resetMutation.mutateAsync();
      toast.success("已還原為預設規則");
      setDirty(false);
    } catch {
      toast.error("還原失敗");
    }
  }

  if (isLoading) {
    return <div className="py-8 text-center text-muted-foreground">載入中...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          管理 RAG 品質診斷規則的門檻與提示文字。修改後需儲存才會生效。
        </p>
        <div className="flex gap-2">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm">
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                還原預設
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>確認還原預設規則？</AlertDialogTitle>
                <AlertDialogDescription>
                  所有自訂的門檻與提示文字將被還原為系統預設值，此操作無法復原。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction onClick={handleReset}>確認還原</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button size="sm" disabled={!dirty || updateMutation.isPending} onClick={handleSaveAll}>
            <Save className="mr-1.5 h-3.5 w-3.5" />
            {updateMutation.isPending ? "儲存中..." : "儲存變更"}
          </Button>
        </div>
      </div>

      {/* Single Rules Table */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold">單維度規則（{singleRules.length} 條）</h3>
          <Button variant="outline" size="sm" onClick={openAddSingle}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            新增
          </Button>
        </div>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-36">維度</TableHead>
                <TableHead className="w-20">門檻</TableHead>
                <TableHead className="w-24">類別</TableHead>
                <TableHead className="w-20">嚴重度</TableHead>
                <TableHead>訊息</TableHead>
                <TableHead className="w-20 text-center">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {singleRules.map((rule, idx) => (
                <TableRow key={idx}>
                  <TableCell className="font-mono text-xs">{rule.dimension}</TableCell>
                  <TableCell className="font-mono text-xs">&le; {rule.threshold}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {CATEGORY_LABELS[rule.category] ?? rule.category}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={`text-[10px] ${SEVERITY_COLORS[rule.severity] ?? ""}`}>
                      {rule.severity}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs max-w-xs truncate" title={rule.message}>
                    {rule.message}
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex justify-center gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEditSingle(idx)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive"
                        onClick={() => removeSingle(idx)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {singleRules.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-6 text-muted-foreground">
                    尚無規則
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Combo Rules Table */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold">交叉維度規則（{comboRules.length} 條）</h3>
          <Button variant="outline" size="sm" onClick={openAddCombo}>
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            新增
          </Button>
        </div>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-48">條件</TableHead>
                <TableHead className="w-24">類別</TableHead>
                <TableHead className="w-20">嚴重度</TableHead>
                <TableHead>訊息</TableHead>
                <TableHead className="w-20 text-center">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {comboRules.map((rule, idx) => (
                <TableRow key={idx}>
                  <TableCell className="font-mono text-xs">
                    {rule.dim_a} {rule.op_a} {rule.threshold_a} &amp;&amp; {rule.dim_b} {rule.op_b} {rule.threshold_b}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {CATEGORY_LABELS[rule.category] ?? rule.category}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge className={`text-[10px] ${SEVERITY_COLORS[rule.severity] ?? ""}`}>
                      {rule.severity}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs max-w-xs truncate" title={rule.message}>
                    {rule.message}
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex justify-center gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEditCombo(idx)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive"
                        onClick={() => removeCombo(idx)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {comboRules.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-6 text-muted-foreground">
                    尚無規則
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      {/* Dialogs */}
      <SingleRuleDialog
        open={singleDialogOpen}
        onOpenChange={setSingleDialogOpen}
        rule={editingSingleRule}
        onSave={handleSaveSingle}
      />
      <ComboRuleDialog
        open={comboDialogOpen}
        onOpenChange={setComboDialogOpen}
        rule={editingComboRule}
        onSave={handleSaveCombo}
      />
    </div>
  );
}
