import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreatePricing } from "@/hooks/queries/use-pricing";

interface PricingCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DEFAULT_FORM = {
  provider: "anthropic",
  model_id: "",
  display_name: "",
  category: "llm" as "llm" | "embedding",
  input_price: 0,
  output_price: 0,
  cache_read_price: 0,
  cache_creation_price: 0,
  effective_from: "", // datetime-local string
  note: "",
};

function toIsoUtc(localDatetime: string): string {
  // datetime-local input gives e.g. "2026-04-22T12:34"
  // Convert to ISO UTC by treating as local then calling toISOString
  const d = new Date(localDatetime);
  return d.toISOString();
}

function defaultFutureInput(): string {
  const d = new Date(Date.now() + 60_000); // 1min future
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function PricingCreateDialog({
  open,
  onOpenChange,
}: PricingCreateDialogProps) {
  const [form, setForm] = useState({
    ...DEFAULT_FORM,
    effective_from: defaultFutureInput(),
  });
  const [error, setError] = useState<string | null>(null);
  const createMutation = useCreatePricing();

  const handleSubmit = async () => {
    setError(null);
    if (!form.model_id || !form.display_name) {
      setError("model_id 與 display_name 必填");
      return;
    }
    if (!form.note.trim()) {
      setError("請填寫改價理由（將寫入 audit log）");
      return;
    }
    if (!form.effective_from) {
      setError("請選擇生效時間");
      return;
    }

    try {
      await createMutation.mutateAsync({
        provider: form.provider,
        model_id: form.model_id,
        display_name: form.display_name,
        category: form.category,
        input_price: Number(form.input_price),
        output_price: Number(form.output_price),
        cache_read_price: Number(form.cache_read_price),
        cache_creation_price: Number(form.cache_creation_price),
        effective_from: toIsoUtc(form.effective_from),
        note: form.note,
      });
      onOpenChange(false);
      setForm({ ...DEFAULT_FORM, effective_from: defaultFutureInput() });
    } catch (e) {
      setError(e instanceof Error ? e.message : "建立失敗");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>新增 Pricing 版本</DialogTitle>
        </DialogHeader>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="provider">Provider</Label>
              <Input
                id="provider"
                value={form.provider}
                onChange={(e) =>
                  setForm({ ...form, provider: e.target.value })
                }
                placeholder="anthropic / openai / litellm / ..."
              />
            </div>
            <div>
              <Label htmlFor="category">類別</Label>
              <select
                id="category"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                value={form.category}
                onChange={(e) =>
                  setForm({
                    ...form,
                    category: e.target.value as "llm" | "embedding",
                  })
                }
              >
                <option value="llm">llm</option>
                <option value="embedding">embedding</option>
              </select>
            </div>
          </div>

          <div>
            <Label htmlFor="model_id">Model ID</Label>
            <Input
              id="model_id"
              value={form.model_id}
              onChange={(e) => setForm({ ...form, model_id: e.target.value })}
              placeholder="claude-haiku-4-5 / azure_ai/claude-sonnet-4-5"
            />
          </div>
          <div>
            <Label htmlFor="display_name">顯示名稱</Label>
            <Input
              id="display_name"
              value={form.display_name}
              onChange={(e) =>
                setForm({ ...form, display_name: e.target.value })
              }
              placeholder="Claude Haiku 4.5"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="input_price">Input (USD / 1M)</Label>
              <Input
                id="input_price"
                type="number"
                step="0.001"
                value={form.input_price}
                onChange={(e) =>
                  setForm({ ...form, input_price: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <Label htmlFor="output_price">Output (USD / 1M)</Label>
              <Input
                id="output_price"
                type="number"
                step="0.001"
                value={form.output_price}
                onChange={(e) =>
                  setForm({ ...form, output_price: Number(e.target.value) })
                }
              />
            </div>
            <div>
              <Label htmlFor="cache_read_price">Cache Read</Label>
              <Input
                id="cache_read_price"
                type="number"
                step="0.001"
                value={form.cache_read_price}
                onChange={(e) =>
                  setForm({
                    ...form,
                    cache_read_price: Number(e.target.value),
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="cache_creation_price">Cache Creation</Label>
              <Input
                id="cache_creation_price"
                type="number"
                step="0.001"
                value={form.cache_creation_price}
                onChange={(e) =>
                  setForm({
                    ...form,
                    cache_creation_price: Number(e.target.value),
                  })
                }
              />
            </div>
          </div>

          <div>
            <Label htmlFor="effective_from">
              生效時間（必須為現在或未來）
            </Label>
            <Input
              id="effective_from"
              type="datetime-local"
              value={form.effective_from}
              onChange={(e) =>
                setForm({ ...form, effective_from: e.target.value })
              }
            />
          </div>

          <div>
            <Label htmlFor="note">改價理由（必填，寫入 audit log）</Label>
            <Textarea
              id="note"
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              placeholder="OpenAI 6/15 官方調價 10%"
              rows={3}
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={createMutation.isPending}
          >
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending ? "建立中..." : "建立新版本"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
