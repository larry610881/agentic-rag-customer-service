import { useEffect, useMemo, useState, type ReactNode } from "react";
import { RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { AbuseOverrides } from "@/types/abuse-control";
import {
  buildFieldGroups,
  formatSettingValue,
  LEVEL_LABELS,
  MODE_LABELS,
  type AbuseFieldDef,
} from "@/features/abuse-control/abuse-setting-labels";

const INHERIT = "__inherit__";
const THRESHOLD_KEYS = ["threshold_l1", "threshold_l2", "threshold_l3", "threshold_l4"];

/** 編輯中的草稿：數值 / 清單欄位在輸入期間以字串暫存，送出時再正規化 */
type Draft = Record<string, unknown>;

export interface AbuseSettingsFormProps {
  /** 目前已儲存的覆寫（只含有改的鍵）；`profile` 鍵會被忽略 */
  initialOverrides: AbuseOverrides;
  /** 未覆寫時的繼承值，作為 placeholder 與提示 */
  baseValues: Record<string, unknown>;
  /** 後端 bounds（數值鍵 [min,max]） */
  bounds?: Record<string, [number, number]>;
  /** 後端 allowed_keys；前端不認識的鍵會歸入「其他」 */
  allowedKeys?: string[];
  onSubmit: (overrides: AbuseOverrides) => void;
  isPending?: boolean;
  submitLabel?: string;
  /** 表單外的變更（例如租戶方案切換）也要允許儲存 */
  externallyDirty?: boolean;
  /** 控制項 id 前綴；同頁出現多份表單時需區分 */
  idPrefix?: string;
  /** 放在群組之前的額外控制項 */
  children?: ReactNode;
  /** 放在儲存按鈕旁的額外按鈕（例如取消） */
  footerExtra?: ReactNode;
}

function stripProfile(overrides: AbuseOverrides): AbuseOverrides {
  const { profile: _profile, ...rest } = overrides;
  return rest;
}

function sortedJson(value: AbuseOverrides): string {
  return JSON.stringify(
    Object.keys(value)
      .sort()
      .map((k) => [k, value[k]]),
  );
}

/** 把草稿轉成要送給後端的覆寫：空字串 / 空清單視為「移除覆寫」 */
export function normalizeDraft(draft: Draft, defs: Map<string, AbuseFieldDef>): AbuseOverrides {
  const out: AbuseOverrides = {};
  for (const [key, raw] of Object.entries(draft)) {
    if (raw === undefined || raw === null) continue;
    const kind = defs.get(key)?.kind ?? "number";
    if (kind === "number" || kind === "level") {
      const text = String(raw).trim();
      if (text === "") continue;
      const n = Number(text);
      if (Number.isNaN(n)) continue;
      out[key] = kind === "level" ? Math.trunc(n) : n;
    } else if (kind === "string-list") {
      const list = Array.isArray(raw)
        ? raw.map(String)
        : String(raw)
            .split(/\r?\n|,/)
            .map((s) => s.trim());
      const clean = list.filter(Boolean);
      if (clean.length === 0) continue;
      out[key] = clean;
    } else if (kind === "boolean") {
      out[key] = raw === true || raw === "true";
    } else {
      out[key] = raw;
    }
  }
  return out;
}

function thresholdError(merged: Record<string, unknown>): string | null {
  const values = THRESHOLD_KEYS.map((k) => merged[k]).filter(
    (v): v is number => typeof v === "number",
  );
  for (let i = 1; i < values.length; i += 1) {
    if (values[i] < values[i - 1]) return "門檻必須遞增：L1 < L2 < L3 < L4";
  }
  return null;
}

export function AbuseSettingsForm({
  initialOverrides,
  baseValues,
  bounds,
  allowedKeys,
  onSubmit,
  isPending = false,
  submitLabel = "儲存",
  externallyDirty = false,
  idPrefix = "abuse",
  children,
  footerExtra,
}: AbuseSettingsFormProps) {
  const initial = useMemo(() => stripProfile(initialOverrides), [initialOverrides]);
  const initialJson = sortedJson(initial);
  const [draft, setDraft] = useState<Draft>(initial);

  // 伺服器資料更新（切換租戶 / 方案 / 儲存後 refetch）時重置草稿
  useEffect(() => {
    setDraft(stripProfile(initialOverrides));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialJson]);

  const groups = useMemo(() => buildFieldGroups(allowedKeys), [allowedKeys]);
  const defs = useMemo(
    () => new Map(groups.flatMap((g) => g.fields.map((f) => [f.key, f] as const))),
    [groups],
  );

  const normalized = useMemo(() => normalizeDraft(draft, defs), [draft, defs]);
  const isDirty = sortedJson(normalized) !== initialJson;
  const error = thresholdError({ ...baseValues, ...normalized });
  const canSubmit = (isDirty || externallyDirty) && !error && !isPending;

  const setValue = (key: string, value: unknown) =>
    setDraft((prev) => ({ ...prev, [key]: value }));
  const clearValue = (key: string) =>
    setDraft((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });

  const renderField = (def: AbuseFieldDef) => {
    const id = `${idPrefix}-${def.key}`;
    const overridden = draft[def.key] !== undefined && draft[def.key] !== null;
    const baseValue = baseValues[def.key];
    const range = bounds?.[def.key] ?? def.fallbackBounds;
    const inheritLabel = `繼承：${formatSettingValue(def.key, baseValue)}`;

    let control: ReactNode;
    if (def.kind === "number") {
      const raw = draft[def.key];
      control = (
        <Input
          id={id}
          type="number"
          inputMode="decimal"
          value={raw === undefined || raw === null ? "" : String(raw)}
          placeholder={baseValue === undefined ? "—" : String(baseValue)}
          min={range?.[0]}
          max={range?.[1]}
          step="any"
          onChange={(e) =>
            e.target.value === "" ? clearValue(def.key) : setValue(def.key, e.target.value)
          }
        />
      );
    } else if (def.kind === "level") {
      const raw = draft[def.key];
      control = (
        <Select
          value={raw === undefined || raw === null ? INHERIT : String(raw)}
          onValueChange={(v) => (v === INHERIT ? clearValue(def.key) : setValue(def.key, Number(v)))}
        >
          <SelectTrigger id={id} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={INHERIT}>{inheritLabel}</SelectItem>
            {Object.entries(LEVEL_LABELS).map(([lv, label]) => (
              <SelectItem key={lv} value={lv}>
                {lv}（{label}）
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    } else if (def.kind === "mode") {
      const raw = draft[def.key];
      control = (
        <Select
          value={typeof raw === "string" ? raw : INHERIT}
          onValueChange={(v) => (v === INHERIT ? clearValue(def.key) : setValue(def.key, v))}
        >
          <SelectTrigger id={id} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={INHERIT}>{inheritLabel}</SelectItem>
            {Object.entries(MODE_LABELS).map(([mode, label]) => (
              <SelectItem key={mode} value={mode}>
                {label}（{mode}）
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    } else if (def.kind === "boolean") {
      const raw = draft[def.key];
      const value = raw === undefined || raw === null ? INHERIT : String(raw === true || raw === "true");
      control = (
        <Select
          value={value}
          onValueChange={(v) => (v === INHERIT ? clearValue(def.key) : setValue(def.key, v === "true"))}
        >
          <SelectTrigger id={id} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={INHERIT}>{inheritLabel}</SelectItem>
            <SelectItem value="true">是</SelectItem>
            <SelectItem value="false">否</SelectItem>
          </SelectContent>
        </Select>
      );
    } else {
      const raw = draft[def.key];
      const text = Array.isArray(raw) ? raw.join("\n") : raw === undefined || raw === null ? "" : String(raw);
      const basePlaceholder = Array.isArray(baseValue) && baseValue.length
        ? baseValue.join("\n")
        : "（未設定）";
      control = (
        <Textarea
          id={id}
          rows={3}
          value={text}
          placeholder={basePlaceholder}
          onChange={(e) =>
            e.target.value === "" ? clearValue(def.key) : setValue(def.key, e.target.value)
          }
        />
      );
    }

    return (
      <div key={def.key} className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={id}>{def.label}</Label>
          {overridden && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 text-xs text-muted-foreground"
              onClick={() => clearValue(def.key)}
              aria-label={`還原 ${def.label}`}
            >
              <RotateCcw className="mr-1 h-3 w-3" />
              還原
            </Button>
          )}
        </div>
        {control}
        <p className="text-xs text-muted-foreground">
          {overridden ? `已覆寫（${inheritLabel}）` : inheritLabel}
          {range && def.kind === "number" ? `　範圍 ${range[0]}–${range[1]}` : ""}
          {def.hint ? `　${def.hint}` : ""}
        </p>
      </div>
    );
  };

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit(normalized);
      }}
    >
      {children}
      {groups.map((group) => (
        <Card key={group.key}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{group.label}</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.fields.map(renderField)}
          </CardContent>
        </Card>
      ))}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!canSubmit}>
          {isPending ? "儲存中…" : submitLabel}
        </Button>
        {footerExtra}
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!error && !isDirty && !externallyDirty && (
          <p className="text-sm text-muted-foreground">尚無變更</p>
        )}
      </div>
    </form>
  );
}
