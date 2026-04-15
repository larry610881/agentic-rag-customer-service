import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useSystemPrompts,
  useUpdateSystemPrompts,
} from "@/hooks/queries/use-system-prompts";

export function SystemPromptEditor() {
  const { data: config, isLoading } = useSystemPrompts();
  const updateMutation = useUpdateSystemPrompts();

  const [basePrompt, setBasePrompt] = useState("");

  useEffect(() => {
    if (config) {
      setBasePrompt(config.base_prompt);
    }
  }, [config]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        base_prompt: basePrompt,
      });
      toast.success("System Prompt 已更新");
    } catch {
      toast.error("更新失敗，請稍後再試");
    }
  };

  if (isLoading) {
    return <p className="text-muted-foreground">載入中...</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-muted-foreground">
        管理系統層級的預設提示詞。Bot 留空的欄位將使用這裡的預設值。
      </p>

      <div className="flex flex-col gap-2">
        <Label htmlFor="sys-base-prompt">System Prompt</Label>
        <Textarea
          id="sys-base-prompt"
          rows={10}
          value={basePrompt}
          onChange={(e) => setBasePrompt(e.target.value)}
          placeholder="定義 AI 的角色、行為準則與安全規則"
        />
        <p className="text-xs text-muted-foreground">
          所有 Bot 共用的系統提示詞，定義 AI 的角色與行為準則。
        </p>
        <p className="text-xs text-muted-foreground/70">
          支援動態變數：
          <code className="rounded bg-muted px-1">{"{today}"}</code> 今日日期、
          <code className="rounded bg-muted px-1">{"{now}"}</code> 當前時間、
          <code className="rounded bg-muted px-1">{"{weekday_zh}"}</code> 中文星期。
          例：「今天是 {"{today}"}（{"{weekday_zh}"}）」
        </p>
      </div>

      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? "儲存中..." : "儲存變更"}
        </Button>
      </div>
    </div>
  );
}
