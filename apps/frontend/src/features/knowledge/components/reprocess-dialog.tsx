"use client";

import { useState } from "react";
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

interface ReprocessDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (params: {
    chunk_size?: number;
    chunk_overlap?: number;
    chunk_strategy?: string;
  }) => void;
  isPending?: boolean;
  filename: string;
}

export function ReprocessDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending,
  filename,
}: ReprocessDialogProps) {
  const [chunkSize, setChunkSize] = useState("");
  const [chunkOverlap, setChunkOverlap] = useState("");
  const [strategy, setStrategy] = useState("");

  const handleSubmit = () => {
    onConfirm({
      chunk_size: chunkSize ? Number(chunkSize) : undefined,
      chunk_overlap: chunkOverlap ? Number(chunkOverlap) : undefined,
      chunk_strategy: strategy || undefined,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>重新處理文件</DialogTitle>
          <DialogDescription>
            將重新分塊「{filename}」。可選填覆寫參數，留空則使用預設值。
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="chunk-size">Chunk Size</Label>
            <Input
              id="chunk-size"
              type="number"
              placeholder="例：500"
              value={chunkSize}
              onChange={(e) => setChunkSize(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="chunk-overlap">Chunk Overlap</Label>
            <Input
              id="chunk-overlap"
              type="number"
              placeholder="例：50"
              value={chunkOverlap}
              onChange={(e) => setChunkOverlap(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="strategy">Strategy</Label>
            <Input
              id="strategy"
              placeholder="例：recursive / csv_row / auto"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
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
