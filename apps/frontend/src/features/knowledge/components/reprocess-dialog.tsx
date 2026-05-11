import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import type { KnowledgeBase } from "@/types/knowledge";

type ReprocessParams = {
  chunk_size?: number;
  chunk_overlap?: number;
  chunk_strategy?: string;
  ocr_mode?: string;
  ocr_model?: string;
  context_model?: string;
  ocr_slice_grid?: string;
};

type ReprocessDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (params: ReprocessParams) => void;
  isPending?: boolean;
  filename: string;
  /** 該文件所屬 KB；提供後 dialog 預設值帶入此 KB 設定。 */
  kbDefaults?: KnowledgeBase | null;
};

const OCR_MODE_OPTIONS = [
  { value: "general", label: "通用文字提取" },
  { value: "catalog", label: "商品目錄 DM" },
  { value: "auto", label: "自動分類（混合 DM 推薦）" },
] as const;

// chunk_strategy 後端「""」與「auto」行為相同 — UI 統一用 "auto"
const CHUNK_STRATEGY_OPTIONS = [
  { value: "auto", label: "auto - 依 content_type 自動選（預設）" },
  { value: "recursive", label: "recursive - 純文字字數切" },
  { value: "separator", label: "separator - DM 商品目錄（=== 分隔）" },
  { value: "json_record", label: "json_record - JSON 一筆一 chunk" },
  { value: "csv_row", label: "csv_row - CSV 一列一 chunk" },
] as const;

// 切片 OCR override（per-reprocess）— 後端「""」= 不切片，UI 用 "none"
const OCR_SLICE_GRID_OPTIONS = [
  { value: "none", label: "不切片（標準成本）" },
  { value: "2x3", label: "2x3 切片（rare char 突破，+3x token）" },
  { value: "3x2", label: "3x2 切片（橫向文件適用）" },
] as const;

const defaultOcrMode = (kb?: KnowledgeBase | null) => kb?.ocr_mode || "general";
const defaultChunkStrategy = (kb?: KnowledgeBase | null) =>
  kb?.chunk_strategy || "auto";
const defaultOcrSliceGrid = (kb?: KnowledgeBase | null) =>
  kb?.ocr_slice_grid || "none";

export function ReprocessDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
  filename,
  kbDefaults,
}: ReprocessDialogProps) {
  const [chunkSize, setChunkSize] = useState("");
  const [chunkOverlap, setChunkOverlap] = useState("");
  const [chunkStrategy, setChunkStrategy] = useState(
    defaultChunkStrategy(kbDefaults),
  );
  const [ocrMode, setOcrMode] = useState(defaultOcrMode(kbDefaults));
  const [ocrModel, setOcrModel] = useState(kbDefaults?.ocr_model ?? "");
  const [contextModel, setContextModel] = useState(
    kbDefaults?.context_model ?? "",
  );
  const [ocrSliceGrid, setOcrSliceGrid] = useState(
    defaultOcrSliceGrid(kbDefaults),
  );

  // dialog 打開時重設為 KB 預設值（每次開啟都同步最新 kbDefaults）
  useEffect(() => {
    if (!open) return;
    setChunkSize("");
    setChunkOverlap("");
    setChunkStrategy(defaultChunkStrategy(kbDefaults));
    setOcrMode(defaultOcrMode(kbDefaults));
    setOcrModel(kbDefaults?.ocr_model ?? "");
    setContextModel(kbDefaults?.context_model ?? "");
    setOcrSliceGrid(defaultOcrSliceGrid(kbDefaults));
  }, [open, kbDefaults]);

  const handleResetDefaults = () => {
    setChunkSize("");
    setChunkOverlap("");
    setChunkStrategy(defaultChunkStrategy(kbDefaults));
    setOcrMode(defaultOcrMode(kbDefaults));
    setOcrModel(kbDefaults?.ocr_model ?? "");
    setContextModel(kbDefaults?.context_model ?? "");
    setOcrSliceGrid(defaultOcrSliceGrid(kbDefaults));
  };

  const handleSubmit = () => {
    onConfirm({
      chunk_size: chunkSize ? Number(chunkSize) : undefined,
      chunk_overlap: chunkOverlap ? Number(chunkOverlap) : undefined,
      // "auto" 在後端視為 "" — 統一送 ""
      chunk_strategy: chunkStrategy === "auto" ? "" : chunkStrategy,
      ocr_mode: ocrMode,
      ocr_model: ocrModel || undefined,
      context_model: contextModel || undefined,
      // "none" 在後端視為 ""（不切片）
      ocr_slice_grid: ocrSliceGrid === "none" ? "" : ocrSliceGrid,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>重新處理文件</DialogTitle>
          <DialogDescription>
            將重新分塊「{filename}」。
            {kbDefaults
              ? "預設值已帶入 KB 當前設定，可暫時覆寫（只影響這次 reprocess，不改 KB）。"
              : "可選填覆寫參數，留空則使用預設值。"}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reprocess-ocr-mode">OCR 模式</Label>
            <Select value={ocrMode} onValueChange={setOcrMode}>
              <SelectTrigger id="reprocess-ocr-mode">
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
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reprocess-chunk-strategy">分塊策略</Label>
            <Select value={chunkStrategy} onValueChange={setChunkStrategy}>
              <SelectTrigger id="reprocess-chunk-strategy">
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
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reprocess-ocr-slice-grid">切片 OCR</Label>
            <Select value={ocrSliceGrid} onValueChange={setOcrSliceGrid}>
              <SelectTrigger id="reprocess-ocr-slice-grid">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OCR_SLICE_GRID_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              開啟切片可突破 rare brand char 字形混淆（如「薈」「樟腦」），
              但 token 成本 +3x。僅對 image/png (PDF 子頁) OCR 生效。
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reprocess-ocr-model">OCR 模型</Label>
            <Input
              id="reprocess-ocr-model"
              placeholder="例：anthropic:claude-sonnet-4-6（留空 = 系統預設）"
              value={ocrModel}
              onChange={(e) => setOcrModel(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              目前 reserved — 引擎需改造才能 per-call 覆寫，先記錄此次 reprocess 期望值。
            </p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reprocess-context-model">上下文模型 (Contextual Retrieval)</Label>
            <Input
              id="reprocess-context-model"
              placeholder="例：anthropic:claude-haiku-4-5（留空 = 不啟用）"
              value={contextModel}
              onChange={(e) => setContextModel(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              啟用後每個 chunk 會被 LLM 補上下文摘要，提升 RAG 召回率。
            </p>
          </div>

          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">
              進階：自訂 chunk 大小
            </summary>
            <div className="mt-3 flex flex-col gap-3 pl-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="reprocess-chunk-size">Chunk Size</Label>
                <Input
                  id="reprocess-chunk-size"
                  type="number"
                  placeholder="例：500（留空 = global default）"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="reprocess-chunk-overlap">Chunk Overlap</Label>
                <Input
                  id="reprocess-chunk-overlap"
                  type="number"
                  placeholder="例：50（留空 = global default）"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(e.target.value)}
                />
              </div>
            </div>
          </details>
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          {kbDefaults ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetDefaults}
              disabled={isPending}
            >
              重設為 KB 預設
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={isPending}>
            {isPending ? "處理中..." : "重新處理"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
