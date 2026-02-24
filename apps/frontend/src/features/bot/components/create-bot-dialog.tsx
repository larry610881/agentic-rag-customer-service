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
  name: z.string().min(1, "Name is required"),
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
        <Button>Create Bot</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Bot</DialogTitle>
          <DialogDescription>
            Create a new bot to handle customer conversations.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-name">Name</Label>
            <Input
              id="bot-name"
              {...register("name")}
              placeholder="e.g. Customer Service Bot"
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-description">Description</Label>
            <Textarea
              id="bot-description"
              {...register("description")}
              placeholder="Describe the bot's purpose..."
            />
          </div>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending ? "Creating..." : "Create"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
