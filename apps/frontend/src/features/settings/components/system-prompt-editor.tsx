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
  const [routerPrompt, setRouterPrompt] = useState("");
  const [reactPrompt, setReactPrompt] = useState("");

  useEffect(() => {
    if (config) {
      setBasePrompt(config.base_prompt);
      setRouterPrompt(config.router_mode_prompt);
      setReactPrompt(config.react_mode_prompt);
    }
  }, [config]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        base_prompt: basePrompt,
        router_mode_prompt: routerPrompt,
        react_mode_prompt: reactPrompt,
      });
      toast.success("系統提示詞已更新");
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
        <Label htmlFor="sys-base-prompt">基礎 Prompt</Label>
        <Textarea
          id="sys-base-prompt"
          rows={6}
          value={basePrompt}
          onChange={(e) => setBasePrompt(e.target.value)}
          placeholder="共用品牌聲音 + 行為準則"
        />
        <p className="text-xs text-muted-foreground">
          所有模式共用的基礎提示詞，定義 AI 的角色與行為準則。
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="sys-router-prompt">Router 模式 Prompt</Label>
        <Textarea
          id="sys-router-prompt"
          rows={4}
          value={routerPrompt}
          onChange={(e) => setRouterPrompt(e.target.value)}
          placeholder="Router 模式專用指令"
        />
        <p className="text-xs text-muted-foreground">
          使用 Router 模式時附加的提示詞。
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="sys-react-prompt">ReAct 模式 Prompt</Label>
        <Textarea
          id="sys-react-prompt"
          rows={6}
          value={reactPrompt}
          onChange={(e) => setReactPrompt(e.target.value)}
          placeholder="ReAct 模式推理策略"
        />
        <p className="text-xs text-muted-foreground">
          使用 ReAct 模式時附加的推理策略提示詞。
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
