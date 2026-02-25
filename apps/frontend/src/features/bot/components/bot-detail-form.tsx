"use client";

import { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useKnowledgeBases } from "@/hooks/queries/use-knowledge-bases";
import type { Bot, UpdateBotRequest } from "@/types/bot";

const AVAILABLE_TOOLS = [
  { value: "rag_query", label: "Knowledge Base Query" },
  { value: "order_lookup", label: "Order Lookup" },
  { value: "product_search", label: "Product Search" },
  { value: "ticket_creation", label: "Ticket Creation" },
] as const;

const botFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  is_active: z.boolean(),
  system_prompt: z.string().optional(),
  knowledge_base_ids: z.array(z.string()),
  enabled_tools: z.array(z.string()),
  temperature: z.coerce.number().min(0).max(1),
  max_tokens: z.coerce.number().int().min(128).max(4096),
  history_limit: z.coerce.number().int().min(0).max(35),
  frequency_penalty: z.coerce.number().min(0).max(1),
  reasoning_effort: z.enum(["low", "medium", "high"]),
  rag_top_k: z.coerce.number().int().min(1).max(20),
  rag_score_threshold: z.coerce.number().min(0).max(1),
  line_channel_secret: z.string().nullable().optional(),
  line_channel_access_token: z.string().nullable().optional(),
});

type BotFormValues = z.infer<typeof botFormSchema>;

interface BotDetailFormProps {
  bot: Bot;
  onSave: (data: UpdateBotRequest) => void;
  onDelete: () => void;
  isSaving: boolean;
  isDeleting: boolean;
}

export function BotDetailForm({
  bot,
  onSave,
  onDelete,
  isSaving,
  isDeleting,
}: BotDetailFormProps) {
  const { data: knowledgeBases } = useKnowledgeBases();

  const {
    register,
    handleSubmit,
    control,
    reset,
    watch,
    formState: { errors },
  } = useForm<BotFormValues>({
    resolver: zodResolver(botFormSchema),
    defaultValues: {
      name: bot.name,
      description: bot.description,
      is_active: bot.is_active,
      system_prompt: bot.system_prompt,
      knowledge_base_ids: bot.knowledge_base_ids,
      enabled_tools: bot.enabled_tools,
      temperature: bot.temperature,
      max_tokens: bot.max_tokens,
      history_limit: bot.history_limit,
      frequency_penalty: bot.frequency_penalty,
      reasoning_effort: bot.reasoning_effort,
      rag_top_k: bot.rag_top_k,
      rag_score_threshold: bot.rag_score_threshold,
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    },
  });

  const enabledTools = watch("enabled_tools") ?? [];

  useEffect(() => {
    reset({
      name: bot.name,
      description: bot.description,
      is_active: bot.is_active,
      system_prompt: bot.system_prompt,
      knowledge_base_ids: bot.knowledge_base_ids,
      enabled_tools: bot.enabled_tools,
      temperature: bot.temperature,
      max_tokens: bot.max_tokens,
      history_limit: bot.history_limit,
      frequency_penalty: bot.frequency_penalty,
      reasoning_effort: bot.reasoning_effort,
      rag_top_k: bot.rag_top_k,
      rag_score_threshold: bot.rag_score_threshold,
      line_channel_secret: bot.line_channel_secret,
      line_channel_access_token: bot.line_channel_access_token,
    });
  }, [bot, reset]);

  const onSubmit = (data: BotFormValues) => {
    onSave(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      {/* Basic Info */}
      <section className="flex flex-col gap-4">
        <h3 className="text-lg font-semibold">Basic Info</h3>
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-name">Name</Label>
          <Input id="bot-name" {...register("name")} />
          {errors.name && (
            <p className="text-sm text-destructive">{errors.name.message}</p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-description">Description</Label>
          <Textarea id="bot-description" {...register("description")} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-active">Status</Label>
          <Controller
            name="is_active"
            control={control}
            render={({ field }) => (
              <Select
                value={field.value ? "active" : "inactive"}
                onValueChange={(v) => field.onChange(v === "active")}
              >
                <SelectTrigger id="bot-active" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>
      </section>

      <Separator />

      {/* Knowledge Base Binding */}
      <section className="flex flex-col gap-4">
        <h3 className="text-lg font-semibold">Knowledge Bases</h3>
        <div className="flex flex-col gap-2">
          <Label>Linked Knowledge Bases</Label>
          <Controller
            name="knowledge_base_ids"
            control={control}
            render={({ field }) => (
              <div className="flex flex-col gap-2">
                {knowledgeBases?.map((kb) => (
                  <label
                    key={kb.id}
                    className="flex items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={field.value.includes(kb.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          field.onChange([...field.value, kb.id]);
                        } else {
                          field.onChange(
                            field.value.filter((id) => id !== kb.id),
                          );
                        }
                      }}
                      className="rounded border-input"
                    />
                    {kb.name}
                  </label>
                ))}
                {(!knowledgeBases || knowledgeBases.length === 0) && (
                  <p className="text-sm text-muted-foreground">
                    No knowledge bases available.
                  </p>
                )}
              </div>
            )}
          />
        </div>
      </section>

      <Separator />

      {/* Enabled Tools */}
      <section className="flex flex-col gap-4">
        <h3 className="text-lg font-semibold">Enabled Tools</h3>
        <p className="text-sm text-muted-foreground">
          Select which tools this bot can use. If none are selected, the bot will respond directly via LLM without any tools.
        </p>
        <Controller
          name="enabled_tools"
          control={control}
          render={({ field }) => (
            <div className="flex flex-col gap-2">
              {AVAILABLE_TOOLS.map((tool) => (
                <label
                  key={tool.value}
                  className="flex items-center gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={field.value.includes(tool.value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        field.onChange([...field.value, tool.value]);
                      } else {
                        field.onChange(
                          field.value.filter((v) => v !== tool.value),
                        );
                      }
                    }}
                    className="rounded border-input"
                  />
                  {tool.label}
                </label>
              ))}
            </div>
          )}
        />
      </section>

      {enabledTools.includes("rag_query") && (
        <>
          <Separator />

          {/* RAG Parameters */}
          <section className="flex flex-col gap-4">
            <h3 className="text-lg font-semibold">RAG Parameters</h3>
            <p className="text-sm text-muted-foreground">
              Configure retrieval parameters for the knowledge base query tool.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-rag-top-k">Top K (1-20)</Label>
                <Input
                  id="bot-rag-top-k"
                  type="number"
                  min="1"
                  max="20"
                  {...register("rag_top_k")}
                />
                {errors.rag_top_k && (
                  <p className="text-sm text-destructive">
                    {errors.rag_top_k.message}
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="bot-rag-score-threshold">
                  Score Threshold (0-1)
                </Label>
                <Input
                  id="bot-rag-score-threshold"
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  {...register("rag_score_threshold")}
                />
                {errors.rag_score_threshold && (
                  <p className="text-sm text-destructive">
                    {errors.rag_score_threshold.message}
                  </p>
                )}
              </div>
            </div>
          </section>
        </>
      )}

      <Separator />

      {/* System Prompt */}
      <section className="flex flex-col gap-4">
        <h3 className="text-lg font-semibold">System Prompt</h3>
        <div className="flex flex-col gap-2">
          <Label htmlFor="bot-system-prompt">Custom System Prompt</Label>
          <Textarea
            id="bot-system-prompt"
            {...register("system_prompt")}
            rows={5}
            placeholder="Enter a custom system prompt for this bot..."
          />
        </div>
      </section>

      <Separator />

      {/* LLM Parameters */}
      <section className="flex flex-col gap-4">
        <h3 className="text-lg font-semibold">LLM Parameters</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-temperature">Temperature (0-1)</Label>
            <Input
              id="bot-temperature"
              type="number"
              step="0.1"
              min="0"
              max="1"
              {...register("temperature")}
            />
            {errors.temperature && (
              <p className="text-sm text-destructive">
                {errors.temperature.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-max-tokens">Max Tokens (128-4096)</Label>
            <Input
              id="bot-max-tokens"
              type="number"
              min="128"
              max="4096"
              {...register("max_tokens")}
            />
            {errors.max_tokens && (
              <p className="text-sm text-destructive">
                {errors.max_tokens.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-history-limit">History Limit (0-35)</Label>
            <Input
              id="bot-history-limit"
              type="number"
              min="0"
              max="35"
              {...register("history_limit")}
            />
            {errors.history_limit && (
              <p className="text-sm text-destructive">
                {errors.history_limit.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-frequency-penalty">
              Frequency Penalty (0-1)
            </Label>
            <Input
              id="bot-frequency-penalty"
              type="number"
              step="0.1"
              min="0"
              max="1"
              {...register("frequency_penalty")}
            />
            {errors.frequency_penalty && (
              <p className="text-sm text-destructive">
                {errors.frequency_penalty.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-reasoning-effort">Reasoning Effort</Label>
            <Controller
              name="reasoning_effort"
              control={control}
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="bot-reasoning-effort">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>
        </div>
      </section>

      <Separator />

      {/* LINE Channel */}
      <section className="flex flex-col gap-4">
        <h3 className="text-lg font-semibold">LINE Channel</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-line-secret">Channel Secret</Label>
            <Input
              id="bot-line-secret"
              type="password"
              {...register("line_channel_secret")}
              placeholder="Enter LINE channel secret"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="bot-line-token">Access Token</Label>
            <Input
              id="bot-line-token"
              type="password"
              {...register("line_channel_access_token")}
              placeholder="Enter LINE access token"
            />
          </div>
        </div>
      </section>

      <Separator />

      {/* Actions */}
      <div className="flex items-center justify-between">
        <Button
          type="button"
          variant="destructive"
          onClick={onDelete}
          disabled={isDeleting}
        >
          {isDeleting ? "Deleting..." : "Delete Bot"}
        </Button>
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
