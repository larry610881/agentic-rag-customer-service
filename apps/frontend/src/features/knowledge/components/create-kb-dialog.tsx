import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ModelSelect } from "@/components/shared/model-select";
import { useCreateKnowledgeBase } from "@/hooks/queries/use-knowledge-bases";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";

const createKbSchema = z.object({
  name: z.string().min(1, "請輸入名稱"),
  description: z.string().min(1, "請輸入描述"),
  ocr_mode: z.string().default("general"),
  ocr_model: z.string().default(""),
  context_model: z.string().default(""),
  classification_model: z.string().default(""),
  chunk_strategy: z.string().default(""),
  // Issue #47 L3：DM-style KB 啟用 KB-level metadata 抽取
  dm_metadata_model: z.string().default(""),
});

type CreateKbFormValues = z.infer<typeof createKbSchema>;

const OCR_MODE_OPTIONS = [
  { value: "general", label: "通用文字提取" },
  { value: "catalog", label: "商品目錄 DM" },
  // Issue #47：自動分類 — 每頁先 detect 類型再 dispatch 對應 prompt
  // catalog 是其 superset（純商品 DM 結果一樣，含信用卡頁的混合 DM 更佳）
  { value: "auto", label: "自動分類（混合 DM 推薦）" },
] as const;

// Issue #45: per-KB chunk_strategy 選項（白名單同後端 API validator）
// 註：後端「""」與「auto」行為相同 — UI 統一用 "auto" 作為預設展示值
const CHUNK_STRATEGY_OPTIONS = [
  { value: "auto", label: "auto - 依 content_type 自動選（預設）" },
  { value: "recursive", label: "recursive - 純文字字數切" },
  { value: "separator", label: "separator - DM 商品目錄（=== 分隔）" },
  { value: "json_record", label: "json_record - JSON 一筆一 chunk" },
  { value: "csv_row", label: "csv_row - CSV 一列一 chunk" },
] as const;

const MODEL_FIELDS = [
  { key: "ocr_model" as const, label: "OCR 解析", emptyLabel: "系統預設" },
  { key: "context_model" as const, label: "上下文生成", emptyLabel: "系統預設" },
  { key: "classification_model" as const, label: "自動分類", emptyLabel: "系統預設" },
  // Issue #47 L3: DM metadata 抽取（KB 全 docs done 後自動 trigger）
  { key: "dm_metadata_model" as const, label: "DM metadata 抽取", emptyLabel: "未啟用" },
] as const;

export function CreateKbDialog() {
  const [open, setOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const createMutation = useCreateKnowledgeBase();
  const { data: enabledModels } = useEnabledModels();

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<CreateKbFormValues>({
    resolver: zodResolver(createKbSchema),
    defaultValues: {
      ocr_mode: "general",
      ocr_model: "",
      context_model: "",
      classification_model: "",
      chunk_strategy: "auto",
      dm_metadata_model: "",
    },
  });

  const ocrMode = watch("ocr_mode");
  const chunkStrategy = watch("chunk_strategy");

  const onSubmit = (data: CreateKbFormValues) => {
    const payload = {
      ...data,
      ocr_model: data.ocr_model === "__none__" ? "" : data.ocr_model,
      context_model: data.context_model === "__none__" ? "" : data.context_model,
      classification_model: data.classification_model === "__none__" ? "" : data.classification_model,
      dm_metadata_model: data.dm_metadata_model === "__none__" ? "" : data.dm_metadata_model,
      // "auto" 在後端跟空字串行為相同（走 config.chunk_strategy default）
      // 為保留語意，傳「auto」時轉空字串給後端，避免在 DB 寫死字串
      chunk_strategy: data.chunk_strategy === "auto" ? "" : data.chunk_strategy,
    };
    createMutation.mutate(payload, {
      onSuccess: () => {
        reset();
        setShowAdvanced(false);
        setOpen(false);
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>建立知識庫</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>建立知識庫</DialogTitle>
          <DialogDescription>
            新增知識庫來管理您的文件。
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="kb-name">名稱</Label>
            <Input id="kb-name" {...register("name")} placeholder="例如：產品文件" />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="kb-description">描述</Label>
            <Textarea
              id="kb-description"
              {...register("description")}
              placeholder="描述知識庫的用途..."
            />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label>PDF 解析模式</Label>
            <Select
              value={ocrMode}
              onValueChange={(v) => setValue("ocr_mode", v)}
            >
              <SelectTrigger>
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
                ? "賣場 DM / 商品型錄，全頁結構化提取商品名稱與價格"
                : ocrMode === "auto"
                ? "混合 DM（含信用卡頁 / 服務介紹頁）— 每頁先分類再用對應 prompt"
                : "一般文件，提取純文字內容"}
            </p>
          </div>

          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" type="button" className="w-full justify-between">
                AI 模型 / 進階設定
                <ChevronDown
                  className={`h-4 w-4 transition-transform duration-200 ${showAdvanced ? "rotate-180" : ""}`}
                />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="flex flex-col gap-3 pt-2">
              <p className="text-xs text-muted-foreground">
                留空使用系統預設模型。
              </p>
              {MODEL_FIELDS.map((field) => (
                <div key={field.key} className="flex flex-col gap-1">
                  <Label className="text-sm">{field.label}</Label>
                  <ModelSelect
                    value={watch(field.key)}
                    onValueChange={(v) => setValue(field.key, v)}
                    enabledModels={enabledModels}
                    placeholder={field.emptyLabel}
                    allowEmpty
                    emptyLabel={field.emptyLabel}
                  />
                </div>
              ))}
              <div className="flex flex-col gap-1">
                <Label className="text-sm">分塊策略 (chunk_strategy)</Label>
                <Select
                  value={chunkStrategy || "auto"}
                  onValueChange={(v) => setValue("chunk_strategy", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CHUNK_STRATEGY_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  DM 商品目錄選 separator；FAQ JSON 選 json_record；其他用預設。
                </p>
              </div>
            </CollapsibleContent>
          </Collapsible>

          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "建立中..." : "建立"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
