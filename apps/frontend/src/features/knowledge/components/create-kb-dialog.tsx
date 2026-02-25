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
import { useCreateKnowledgeBase } from "@/hooks/queries/use-knowledge-bases";

const createKbSchema = z.object({
  name: z.string().min(1, "請輸入名稱"),
  description: z.string().min(1, "請輸入描述"),
});

type CreateKbFormValues = z.infer<typeof createKbSchema>;

export function CreateKbDialog() {
  const [open, setOpen] = useState(false);
  const createMutation = useCreateKnowledgeBase();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CreateKbFormValues>({
    resolver: zodResolver(createKbSchema),
  });

  const onSubmit = (data: CreateKbFormValues) => {
    createMutation.mutate(data, {
      onSuccess: () => {
        reset();
        setOpen(false);
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>建立知識庫</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>建立知識庫</DialogTitle>
          <DialogDescription>
            新增知識庫來管理您的文件。
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="kb-name">名稱</Label>
            <Input id="kb-name" {...register("name")} placeholder="例如：產品文件" />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="kb-description">描述</Label>
            <Textarea
              id="kb-description"
              {...register("description")}
              placeholder="描述知識庫的用途..."
            />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "建立中..." : "建立"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
