import { useState } from "react";
import { Link } from "react-router-dom";
import { Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const OCR_MODE_LABELS: Record<string, { label: string; tip: string }> = {
  general: { label: "一般 OCR", tip: "標準文字擷取，適用一般文件" },
  catalog: { label: "型錄 OCR", tip: "圖片型錄辨識，適用商品型錄/DM" },
};
import { useDeleteKnowledgeBase } from "@/hooks/queries/use-knowledge-bases";
import type { KnowledgeBase } from "@/types/knowledge";

interface KnowledgeBaseCardProps {
  knowledgeBase: KnowledgeBase;
}

export function KnowledgeBaseCard({ knowledgeBase }: KnowledgeBaseCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const deleteMutation = useDeleteKnowledgeBase();

  return (
    <>
      <Link to={`/knowledge/${knowledgeBase.id}`}>
        <Card className="transition-colors hover:bg-muted/50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">{knowledgeBase.name}</CardTitle>
              <div className="flex items-center gap-2">
                {knowledgeBase.ocr_mode && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Badge variant="outline" className="text-xs">
                        {OCR_MODE_LABELS[knowledgeBase.ocr_mode]?.label ?? knowledgeBase.ocr_mode}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent>
                      {OCR_MODE_LABELS[knowledgeBase.ocr_mode]?.tip ?? "PDF 處理策略"}
                    </TooltipContent>
                  </Tooltip>
                )}
                <Badge variant="secondary">{knowledgeBase.document_count} 份文件</Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setShowDeleteDialog(true);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <CardDescription>{knowledgeBase.description}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              更新於 {new Date(knowledgeBase.updated_at).toLocaleDateString()}
            </p>
          </CardContent>
        </Card>
      </Link>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>刪除知識庫</AlertDialogTitle>
            <AlertDialogDescription>
              確定要刪除「{knowledgeBase.name}」嗎？
              這將同時移除所有文件及向量資料，且無法復原。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                deleteMutation.mutate(knowledgeBase.id);
                setShowDeleteDialog(false);
              }}
            >
              刪除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
