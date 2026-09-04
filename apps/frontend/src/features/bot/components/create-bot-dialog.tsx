import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import { useCreateBot } from "@/hooks/queries/use-bots";
import type { CreateBotRequest } from "@/types/bot";
import {
  CREATE_BOT_PRESET_LABELS,
  KB_QA_BOT_PRESET,
  type CreateBotPreset,
} from "@/features/bot/bot-presets";

const PRESET_OPTIONS: CreateBotPreset[] = ["default", "kb_qa"];

const createBotSchema = z.object({
  name: z.string().min(1, "請輸入名稱"),
  description: z.string().optional(),
  // Issue #70 — 快速範本；default 維持原本建立路徑（不帶額外欄位）。
  // 不用 .default()：zod v4 會讓 input/output 型別分歧、zodResolver 型別報錯，改以 defaultValues 給值。
  preset: z.enum(["default", "kb_qa"]),
});

type CreateBotFormValues = z.infer<typeof createBotSchema>;

export function CreateBotDialog() {
  const [open, setOpen] = useState(false);
  const createMutation = useCreateBot();

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<CreateBotFormValues>({
    resolver: zodResolver(createBotSchema),
    defaultValues: { preset: "default" },
  });
  const preset = watch("preset");

  const onSubmit = (data: CreateBotFormValues) => {
    const payload: CreateBotRequest = {
      name: data.name,
      description: data.description,
      ...(data.preset === "kb_qa" ? KB_QA_BOT_PRESET : {}),
    };
    createMutation.mutate(
      payload,
      {
        onSuccess: () => {
          reset();
          setOpen(false);
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>建立機器人</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>建立機器人</DialogTitle>
          <DialogDescription>
            建立新的機器人來處理客戶對話。
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-name">名稱</Label>
            <Input
              id="bot-name"
              {...register("name")}
              placeholder="例如：客服機器人"
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-description">描述</Label>
            <Textarea
              id="bot-description"
              {...register("description")}
              placeholder="描述機器人的用途..."
            />
          </div>
          {/* Issue #70 — 快速範本 */}
          <div className="flex flex-col gap-2">
            <Label>快速範本</Label>
            <div
              role="radiogroup"
              aria-label="快速範本"
              className="grid gap-2 sm:grid-cols-2"
            >
              {PRESET_OPTIONS.map((opt) => {
                const meta = CREATE_BOT_PRESET_LABELS[opt];
                const checked = preset === opt;
                return (
                  <label
                    key={opt}
                    className={
                      "flex cursor-pointer items-start gap-2 rounded-md border px-3 py-2 transition-colors " +
                      (checked ? "border-primary bg-primary/5" : "hover:bg-muted/50")
                    }
                  >
                    <input
                      type="radio"
                      value={opt}
                      className="mt-1 accent-primary"
                      {...register("preset")}
                    />
                    <span className="flex flex-col gap-0.5">
                      <span className="text-sm font-medium">{meta.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {meta.hint}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "建立中..." : "建立"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
