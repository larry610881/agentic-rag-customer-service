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
import { useDeleteBot } from "@/hooks/queries/use-bots";
import type { Bot } from "@/types/bot";

interface BotCardProps {
  bot: Bot;
}

export function BotCard({ bot }: BotCardProps) {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const deleteMutation = useDeleteBot();

  return (
    <>
      <Link to={`/bots/${bot.id}`}>
        <Card className="transition-colors hover:bg-muted/50">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">{bot.name}</CardTitle>
              <div className="flex items-center gap-1">
                <Badge variant={bot.is_active ? "default" : "secondary"}>
                  {bot.is_active ? "啟用" : "停用"}
                </Badge>
                <Badge variant="outline">
                  {bot.knowledge_base_ids.length} KB
                </Badge>
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
            <CardDescription>{bot.description || "尚無描述"}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              更新於 {new Date(bot.updated_at).toLocaleDateString()}
            </p>
          </CardContent>
        </Card>
      </Link>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>刪除機器人</AlertDialogTitle>
            <AlertDialogDescription>
              確定要刪除「{bot.name}」嗎？此操作無法復原。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                deleteMutation.mutate(bot.id);
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
