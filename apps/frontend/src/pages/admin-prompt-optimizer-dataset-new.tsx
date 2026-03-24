import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Database, ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ROUTES } from "@/routes/paths";
import { useCreateEvalDataset } from "@/hooks/queries/use-prompt-optimizer";

export default function AdminPromptOptimizerDatasetNewPage() {
  const navigate = useNavigate();
  const createMutation = useCreateEvalDataset();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const canSubmit = name.trim().length > 0;

  const handleSubmit = () => {
    if (!canSubmit) return;
    createMutation.mutate(
      { name: name.trim(), description: description.trim() || undefined },
      {
        onSuccess: (dataset) => {
          toast.success("情境集已建立");
          navigate(
            ROUTES.ADMIN_PROMPT_OPTIMIZER_DATASET_EDIT.replace(
              ":id",
              dataset.id,
            ),
          );
        },
        onError: () => toast.error("建立情境集失敗"),
      },
    );
  };

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
          新增情境集
        </h1>
        <p className="mt-1 text-muted-foreground">
          建立新的評估情境集
        </p>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>基本資訊</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">名稱</Label>
            <Input
              id="name"
              placeholder="如：商品查詢情境集"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">描述（選填）</Label>
            <Textarea
              id="description"
              placeholder="描述這個情境集的用途與涵蓋範圍"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div className="flex justify-end">
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit || createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              建立並編輯測試案例
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
