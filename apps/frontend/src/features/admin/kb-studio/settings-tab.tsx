import { useEffect, useState } from "react";
import {
  useKnowledgeBase,
  useUpdateKnowledgeBase,
} from "@/hooks/queries/use-knowledge-bases";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SettingsTabProps {
  kbId: string;
}

const OCR_MODE_OPTIONS = [
  { value: "general", label: "通用文字提取" },
  { value: "catalog", label: "商品目錄 DM" },
] as const;

const MODEL_FIELDS = [
  {
    key: "ocr_model" as const,
    label: "OCR 解析",
    hint: "PDF / 圖片 OCR 用的視覺模型（建議 Sonnet 4.6 / Haiku 4.5）",
  },
  {
    key: "context_model" as const,
    label: "上下文生成 (Contextual Retrieval)",
    hint: "為每個 chunk 生成上下文摘要，提升 RAG 召回率（PDF 子頁 rename 也用這個）",
  },
  {
    key: "classification_model" as const,
    label: "自動分類",
    hint: "KB 文件處理完成後自動聚類分類",
  },
] as const;

const NONE_VALUE = "__none__";

export function SettingsTab({ kbId }: SettingsTabProps) {
  const { data: kb, isLoading, error } = useKnowledgeBase(kbId);
  const { data: enabledModels } = useEnabledModels();
  const updateMutation = useUpdateKnowledgeBase();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [ocrMode, setOcrMode] = useState("general");
  const [ocrModel, setOcrModel] = useState("");
  const [contextModel, setContextModel] = useState("");
  const [classificationModel, setClassificationModel] = useState("");

  useEffect(() => {
    if (!kb) return;
    setName(kb.name);
    setDescription(kb.description ?? "");
    setOcrMode(kb.ocr_mode || "general");
    setOcrModel(kb.ocr_model || "");
    setContextModel(kb.context_model || "");
    setClassificationModel(kb.classification_model || "");
  }, [kb]);

  if (isLoading) {
    return <p className="text-muted-foreground">載入 KB 設定...</p>;
  }
  if (error || !kb) {
    return (
      <p className="text-destructive">
        載入失敗：{(error as Error)?.message ?? "找不到 KB"}
      </p>
    );
  }

  const handleSave = () => {
    updateMutation.mutate({
      kbId,
      data: {
        name,
        description,
        ocr_mode: ocrMode,
        ocr_model: ocrModel === NONE_VALUE ? "" : ocrModel,
        context_model:
          contextModel === NONE_VALUE ? "" : contextModel,
        classification_model:
          classificationModel === NONE_VALUE ? "" : classificationModel,
      },
    });
  };

  const modelValues: Record<(typeof MODEL_FIELDS)[number]["key"], string> = {
    ocr_model: ocrModel,
    context_model: contextModel,
    classification_model: classificationModel,
  };
  const setters: Record<
    (typeof MODEL_FIELDS)[number]["key"],
    (v: string) => void
  > = {
    ocr_model: setOcrModel,
    context_model: setContextModel,
    classification_model: setClassificationModel,
  };

  const dirty =
    name !== kb.name ||
    description !== (kb.description ?? "") ||
    ocrMode !== (kb.ocr_mode || "general") ||
    ocrModel !== (kb.ocr_model || "") ||
    contextModel !== (kb.context_model || "") ||
    classificationModel !== (kb.classification_model || "");

  return (
    <div className="max-w-2xl space-y-6">
      <header>
        <h2 className="text-lg font-semibold">知識庫設定</h2>
        <p className="text-sm text-muted-foreground">
          模型變更後新上傳 / re-process 文件會生效；既有 chunk 不會自動 re-embed。
        </p>
      </header>

      <section className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="kb-name">名稱</Label>
          <Input
            id="kb-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="知識庫名稱"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="kb-description">描述</Label>
          <Textarea
            id="kb-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="知識庫用途、內容來源..."
            rows={2}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="kb-ocr-mode">OCR 模式</Label>
          <Select value={ocrMode} onValueChange={setOcrMode}>
            <SelectTrigger id="kb-ocr-mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {OCR_MODE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {ocrMode === "catalog"
              ? "適用於賣場 DM / 商品型錄 — 結構化提取商品名稱與價格"
              : "適用於一般文件 — 提取純文字內容"}
          </p>
        </div>
      </section>

      <section className="space-y-4 border-t pt-4">
        <h3 className="text-sm font-semibold">AI 模型</h3>
        {MODEL_FIELDS.map((field) => (
          <div key={field.key} className="space-y-1.5">
            <Label htmlFor={`kb-${field.key}`}>{field.label}</Label>
            <Select
              value={modelValues[field.key] || NONE_VALUE}
              onValueChange={setters[field.key]}
            >
              <SelectTrigger id={`kb-${field.key}`}>
                <SelectValue placeholder="系統預設" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE_VALUE}>系統預設</SelectItem>
                {(enabledModels ?? []).map((m) => {
                  const spec = `${m.provider_name}:${m.model_id}`;
                  return (
                    <SelectItem key={spec} value={spec}>
                      {m.display_name || spec}
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{field.hint}</p>
          </div>
        ))}
      </section>

      <footer className="flex items-center gap-2 border-t pt-4">
        <Button
          onClick={handleSave}
          disabled={!dirty || updateMutation.isPending}
        >
          {updateMutation.isPending ? "儲存中..." : "儲存"}
        </Button>
        <p className="text-xs text-muted-foreground font-mono">
          KB ID: {kbId}
        </p>
      </footer>
    </div>
  );
}
