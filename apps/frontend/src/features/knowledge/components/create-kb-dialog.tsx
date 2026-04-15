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
  embedding_model: z.string().default(""),
});

type CreateKbFormValues = z.infer<typeof createKbSchema>;

const OCR_MODE_OPTIONS = [
  { value: "general", label: "通用文字提取" },
  { value: "catalog", label: "商品目錄 DM" },
] as const;

const MODEL_FIELDS = [
  { key: "ocr_model" as const, label: "OCR 解析", emptyLabel: "系統預設" },
  { key: "context_model" as const, label: "上下文生成", emptyLabel: "系統預設" },
  { key: "classification_model" as const, label: "自動分類", emptyLabel: "系統預設" },
  { key: "embedding_model" as const, label: "Embedding", emptyLabel: "系統預設" },
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
      embedding_model: "",
    },
  });

  const ocrMode = watch("ocr_mode");

  const onSubmit = (data: CreateKbFormValues) => {
    const payload = {
      ...data,
      ocr_model: data.ocr_model === "__none__" ? "" : data.ocr_model,
      context_model: data.context_model === "__none__" ? "" : data.context_model,
      classification_model: data.classification_model === "__none__" ? "" : data.classification_model,
      embedding_model: data.embedding_model === "__none__" ? "" : data.embedding_model,
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
                ? "適用於賣場 DM、商品型錄，會結構化提取商品名稱與價格"
                : "適用於一般文件，提取純文字內容"}
            </p>
          </div>

          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" type="button" className="w-full justify-between">
                AI 模型設定
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
