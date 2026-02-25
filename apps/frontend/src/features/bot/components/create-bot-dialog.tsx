"use client";

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

const createBotSchema = z.object({
  name: z.string().min(1, "請輸入名稱"),
  description: z.string().optional(),
});

type CreateBotFormValues = z.infer<typeof createBotSchema>;

export function CreateBotDialog() {
  const [open, setOpen] = useState(false);
  const createMutation = useCreateBot();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateBotFormValues>({
    resolver: zodResolver(createBotSchema),
  });

  const onSubmit = (data: CreateBotFormValues) => {
    createMutation.mutate(
      { name: data.name, description: data.description },
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
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "建立中..." : "建立"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
