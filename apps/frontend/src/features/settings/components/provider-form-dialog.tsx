"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useCreateProviderSetting,
  useUpdateProviderSetting,
} from "@/hooks/queries/use-provider-settings";
import type { ProviderSetting } from "@/types/provider-setting";
import { PROVIDER_NAMES, PROVIDER_TYPES } from "@/types/provider-setting";

const formSchema = z.object({
  provider_type: z.string().min(1, "請選擇類型"),
  provider_name: z.string().min(1, "請選擇供應商"),
  display_name: z.string().min(1, "請輸入顯示名稱"),
  api_key: z.string(),
  base_url: z.string(),
});

type FormValues = z.infer<typeof formSchema>;

interface ProviderFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingSetting: ProviderSetting | null;
  defaultType?: string;
}

export function ProviderFormDialog({
  open,
  onOpenChange,
  editingSetting,
  defaultType,
}: ProviderFormDialogProps) {
  const createMutation = useCreateProviderSetting();
  const updateMutation = useUpdateProviderSetting();
  const isEditing = !!editingSetting;

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      provider_type: defaultType || "llm",
      provider_name: "",
      display_name: "",
      api_key: "",
      base_url: "",
    },
  });

  useEffect(() => {
    if (editingSetting) {
      reset({
        provider_type: editingSetting.provider_type,
        provider_name: editingSetting.provider_name,
        display_name: editingSetting.display_name,
        api_key: "",
        base_url: editingSetting.base_url,
      });
    } else {
      reset({
        provider_type: defaultType || "llm",
        provider_name: "",
        display_name: "",
        api_key: "",
        base_url: "",
      });
    }
  }, [editingSetting, defaultType, reset]);

  const onSubmit = (values: FormValues) => {
    if (isEditing) {
      updateMutation.mutate(
        {
          id: editingSetting.id,
          data: {
            display_name: values.display_name,
            api_key: values.api_key || undefined,
            base_url: values.base_url || undefined,
          },
        },
        {
          onSuccess: () => onOpenChange(false),
        },
      );
    } else {
      createMutation.mutate(
        {
          provider_type: values.provider_type,
          provider_name: values.provider_name,
          display_name: values.display_name,
          api_key: values.api_key,
          base_url: values.base_url || undefined,
        },
        {
          onSuccess: () => onOpenChange(false),
        },
      );
    }
  };

  const providerType = watch("provider_type");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "編輯供應商設定" : "新增供應商設定"}
          </DialogTitle>
        </DialogHeader>
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4"
          aria-label="供應商設定表單"
        >
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="provider_type">類型</Label>
              <Select
                value={providerType}
                onValueChange={(v) => setValue("provider_type", v)}
                disabled={isEditing}
              >
                <SelectTrigger id="provider_type">
                  <SelectValue placeholder="選擇類型" />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDER_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.provider_type && (
                <p className="text-sm text-destructive">
                  {errors.provider_type.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="provider_name">供應商</Label>
              <Select
                value={watch("provider_name")}
                onValueChange={(v) => setValue("provider_name", v)}
                disabled={isEditing}
              >
                <SelectTrigger id="provider_name">
                  <SelectValue placeholder="選擇供應商" />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDER_NAMES.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.provider_name && (
                <p className="text-sm text-destructive">
                  {errors.provider_name.message}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="display_name">顯示名稱</Label>
            <Input
              id="display_name"
              placeholder="例：OpenAI GPT-4o"
              {...register("display_name")}
            />
            {errors.display_name && (
              <p className="text-sm text-destructive">
                {errors.display_name.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="api_key">
              API Key {isEditing && "(留空則不更新)"}
            </Label>
            <Input
              id="api_key"
              type="password"
              placeholder={isEditing ? "••••••••" : "sk-..."}
              {...register("api_key")}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="base_url">Base URL (選填)</Label>
            <Input
              id="base_url"
              placeholder="https://api.openai.com/v1"
              {...register("base_url")}
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button
              type="submit"
              disabled={
                createMutation.isPending || updateMutation.isPending
              }
            >
              {createMutation.isPending || updateMutation.isPending
                ? "儲存中..."
                : "儲存"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
