import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { GuardEffectiveBadges } from "@/features/guard-stages/components/guard-effective-badges";
import { GuardStageChecklist } from "@/features/guard-stages/components/guard-stage-checklist";
import {
  describeGuardApiError,
  guardProfileDescription,
  guardStageDefsFor,
  sortGuardStages,
} from "@/features/guard-stages/guard-stage-labels";
import {
  useGuardSettingsOverview,
  useTenantGuardSettings,
  useUpdateGuardPlatform,
  useUpdateGuardProfile,
  useUpdateGuardTenant,
} from "@/hooks/queries/use-guard-stages";
import { useTenants } from "@/hooks/queries/use-tenants";
import { Badge } from "@/components/ui/badge";
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
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { GuardSettingsOverview, TenantGuardSettings } from "@/types/guard-stages";

const SYSTEM_TENANT_ID = "00000000-0000-0000-0000-000000000000";
const DEFAULT_PROFILE = "standard";

function sameSet(a: Iterable<string>, b: Iterable<string>): boolean {
  const sa = new Set(a);
  const sb = new Set(b);
  if (sa.size !== sb.size) return false;
  for (const x of sa) if (!sb.has(x)) return false;
  return true;
}

/** 平台層目前的預設啟用清單（未覆寫時 = 生效預設，已含底線） */
function platformStagesOf(overview: GuardSettingsOverview): string[] {
  return sortGuardStages(overview.platform_overrides.stages ?? overview.effective_default.stages);
}

function requiredOf(overview: GuardSettingsOverview): string[] {
  return sortGuardStages(
    overview.platform_overrides.required_stages ?? overview.effective_default.required,
  );
}

/** 方案名稱清單：內建優先、其餘字母序 */
function profileNames(overview: GuardSettingsOverview): string[] {
  const builtin = new Set(overview.builtin_profiles);
  return Array.from(new Set([...overview.builtin_profiles, ...Object.keys(overview.profiles)])).sort(
    (a, b) => Number(builtin.has(b)) - Number(builtin.has(a)) || a.localeCompare(b),
  );
}

/**
 * 某方案下的基底 = 底線 ∪（方案自設 stages，沒有就是平台預設）。
 * 與後端 resolve_guard 一致：方案的 stages 是「取代」平台預設，不是聯集。
 */
function baseStagesFor(overview: GuardSettingsOverview, profile: string): string[] {
  const own = overview.profiles[profile]?.stages;
  return sortGuardStages([...requiredOf(overview), ...(own ?? platformStagesOf(overview))]);
}

/* ---------------------------------------------------------------- 系統底線 */

function PlatformTab({ overview }: { overview: GuardSettingsOverview }) {
  const mutation = useUpdateGuardPlatform();
  const initialStages = useMemo(() => platformStagesOf(overview), [overview]);
  const initialRequired = useMemo(() => requiredOf(overview), [overview]);
  const [stages, setStages] = useState<string[]>(initialStages);
  const [required, setRequired] = useState<string[]>(initialRequired);

  useEffect(() => {
    setStages(initialStages);
    setRequired(initialRequired);
  }, [initialStages, initialRequired]);

  const dirty = !sameSet(stages, initialStages) || !sameSet(required, initialRequired);
  const defs = guardStageDefsFor(overview.stages);

  const toggleEnabled = (stage: string, checked: boolean) => {
    setStages((prev) =>
      sortGuardStages(checked ? [...prev, stage] : prev.filter((s) => s !== stage)),
    );
  };
  // 必開隱含啟用：勾必開同時勾啟用；取消必開不動啟用
  const toggleRequired = (stage: string, checked: boolean) => {
    setRequired((prev) =>
      sortGuardStages(checked ? [...prev, stage] : prev.filter((s) => s !== stage)),
    );
    if (checked) setStages((prev) => sortGuardStages([...prev, stage]));
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        「啟用」是所有租戶的預設；「必開」是底線，租戶與 bot 都不能關閉。必開一定同時啟用。
        程式預設底線：{overview.required_floor_default.map((s) => defs.find((d) => d.key === s)?.label ?? s).join("、")}
      </p>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>階段</TableHead>
              <TableHead className="w-20 text-center">啟用</TableHead>
              <TableHead className="w-20 text-center">必開</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {defs.map((def) => {
              const isRequired = required.includes(def.key);
              const disabled = def.comingSoon === true;
              return (
                <TableRow key={def.key}>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{def.label}</span>
                      {def.comingSoon && <Badge variant="outline">即將推出</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground">{def.description}</p>
                    {def.costHint && (
                      <p className="text-xs text-amber-600 dark:text-amber-400">
                        成本：{def.costHint}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    <input
                      type="checkbox"
                      className="rounded border-input"
                      aria-label={`啟用 ${def.label}`}
                      checked={stages.includes(def.key)}
                      disabled={disabled || isRequired}
                      onChange={(e) => toggleEnabled(def.key, e.target.checked)}
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <input
                      type="checkbox"
                      className="rounded border-input"
                      aria-label={`必開 ${def.label}`}
                      checked={isRequired}
                      disabled={disabled}
                      onChange={(e) => toggleRequired(def.key, e.target.checked)}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center gap-3">
        <Button
          type="button"
          disabled={!dirty || mutation.isPending}
          onClick={() =>
            mutation.mutate(
              { stages: sortGuardStages(stages), required_stages: sortGuardStages(required) },
              {
                onSuccess: () => toast.success("系統底線已更新"),
                onError: (err) => toast.error(describeGuardApiError(err)),
              },
            )
          }
        >
          {mutation.isPending ? "儲存中…" : "儲存系統底線"}
        </Button>
        {!dirty && <span className="text-xs text-muted-foreground">尚無變更</span>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- 方案 */

const PROFILE_NAME_PATTERN = /^[a-z0-9][a-z0-9_-]{0,39}$/;

function ProfileEditor({
  name,
  overview,
  isNew = false,
  onSaved,
}: {
  name: string;
  overview: GuardSettingsOverview;
  isNew?: boolean;
  onSaved?: () => void;
}) {
  const mutation = useUpdateGuardProfile();
  const overrides = overview.profiles[name] ?? {};
  const hasOwnStages = !isNew && overrides.stages !== undefined;
  const required = useMemo(() => requiredOf(overview), [overview]);
  const initial = useMemo(() => baseStagesFor(overview, name), [overview, name]);
  const normalize = (list: Iterable<string>) => sortGuardStages([...required, ...list]);
  const [stages, setStages] = useState<string[]>(initial);

  useEffect(() => {
    setStages(initial);
  }, [initial]);

  const dirty = isNew || !sameSet(stages, initial);
  const isBuiltin = overview.builtin_profiles.includes(name);

  const save = (next: { stages?: string[] }, successMsg: string) =>
    mutation.mutate(
      { name, overrides: next },
      {
        onSuccess: () => {
          toast.success(successMsg);
          onSaved?.();
        },
        onError: (err) => toast.error(describeGuardApiError(err)),
      },
    );

  return (
    <div className="space-y-3 rounded-lg border p-4" data-testid={`guard-profile-${name}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-medium">{isNew ? "新方案" : name}</h3>
          {!isNew &&
            (isBuiltin ? (
              <Badge variant="secondary">內建</Badge>
            ) : (
              <Badge variant="outline">自訂</Badge>
            ))}
          {!isNew && (
            <span className="text-xs text-muted-foreground">
              {guardProfileDescription(name, overrides)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {hasOwnStages && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={mutation.isPending}
              onClick={() => save({}, `方案 ${name} 已還原為沿用系統預設`)}
            >
              還原為沿用系統預設
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            disabled={!dirty || mutation.isPending}
            onClick={() =>
              save({ stages: normalize(stages) }, isNew ? "方案已建立" : `方案 ${name} 已更新`)
            }
          >
            {isNew ? "建立方案" : "儲存方案"}
          </Button>
        </div>
      </div>
      <GuardStageChecklist
        idPrefix={`profile-${name || "new"}`}
        stages={overview.stages}
        selected={stages}
        isDisabled={(s) => required.includes(s)}
        badgeOf={(s) => (required.includes(s) ? "底線" : undefined)}
        onToggle={(stage, checked) =>
          setStages((prev) =>
            normalize(checked ? [...prev, stage] : prev.filter((s) => s !== stage)),
          )
        }
      />
    </div>
  );
}

function ProfilesTab({ overview }: { overview: GuardSettingsOverview }) {
  const [newName, setNewName] = useState("");
  const trimmed = newName.trim();
  const names = useMemo(() => profileNames(overview), [overview]);
  const nameError =
    trimmed === ""
      ? null
      : !PROFILE_NAME_PATTERN.test(trimmed)
        ? "名稱限小寫英數、- 與 _，最長 40 字"
        : names.includes(trimmed)
          ? "已有同名方案"
          : null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        方案是一組「預設啟用」的階段（取代系統預設清單），租戶可指定採用；底線階段一律包含、不可取消。
        未自設清單的方案沿用系統預設。
      </p>
      <div className="grid gap-4 lg:grid-cols-2">
        {names.map((name) => (
          <ProfileEditor key={name} name={name} overview={overview} />
        ))}
      </div>
      <div className="space-y-3 rounded-lg border border-dashed p-4">
        <div className="max-w-sm space-y-1.5">
          <Label htmlFor="guard-profile-new-name">新增方案</Label>
          <Input
            id="guard-profile-new-name"
            value={newName}
            placeholder="例：strict"
            autoComplete="off"
            onChange={(e) => setNewName(e.target.value)}
          />
          {nameError && <p className="text-xs text-destructive">{nameError}</p>}
        </div>
        {trimmed !== "" && !nameError && (
          <ProfileEditor
            key={trimmed}
            name={trimmed}
            overview={overview}
            isNew
            onSaved={() => setNewName("")}
          />
        )}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- 租戶設定 */

function TenantEditor({
  tenant,
  overview,
}: {
  tenant: TenantGuardSettings;
  overview: GuardSettingsOverview;
}) {
  const mutation = useUpdateGuardTenant();
  const initialProfile = tenant.profile ?? tenant.effective.profile ?? DEFAULT_PROFILE;
  const [profile, setProfile] = useState<string>(initialProfile);
  const [locked, setLocked] = useState<boolean>(tenant.locked);
  const required = useMemo(() => requiredOf(overview), [overview]);
  const base = useMemo(() => baseStagesFor(overview, profile), [overview, profile]);
  // 租戶覆寫只存「加開」的階段；後端聯集時 setdefault，不會搶走底線 / 方案的來源
  const initialAdditions = useMemo(
    () => sortGuardStages((tenant.overrides.stages ?? []).filter((s) => !base.includes(s))),
    [tenant.overrides.stages, base],
  );
  const [additions, setAdditions] = useState<string[]>(initialAdditions);

  useEffect(() => {
    setProfile(initialProfile);
    setLocked(tenant.locked);
  }, [tenant, initialProfile]);
  useEffect(() => {
    setAdditions(initialAdditions);
  }, [initialAdditions]);

  const selected = sortGuardStages([...base, ...additions]);
  const dirty =
    profile !== initialProfile || locked !== tenant.locked || !sameSet(additions, initialAdditions);
  const profileHasOwn = overview.profiles[profile]?.stages !== undefined;

  const sourceOf = (stage: string): string | undefined => {
    if (required.includes(stage)) return "底線";
    if (base.includes(stage)) return profileHasOwn ? "方案" : "系統預設";
    if (additions.includes(stage)) return "租戶啟用";
    return undefined;
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="guard-tenant-profile">採用方案</Label>
          <Select value={profile} onValueChange={setProfile}>
            <SelectTrigger id="guard-tenant-profile" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {profileNames(overview).map((name) => (
                <SelectItem key={name} value={name}>
                  {name} — {guardProfileDescription(name, overview.profiles[name])}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="guard-tenant-locked">鎖定</Label>
          <div className="flex items-center gap-3 pt-1.5">
            <Switch
              id="guard-tenant-locked"
              checked={locked}
              onCheckedChange={setLocked}
              aria-label="鎖定"
            />
            <span className="text-xs text-muted-foreground">
              鎖定後忽略租戶加開與 bot 加嚴、租戶端唯讀，以此處設定為準。
            </span>
          </div>
        </div>
      </div>

      <GuardStageChecklist
        idPrefix={`tenant-${tenant.tenant_id}`}
        stages={overview.stages}
        selected={selected}
        isDisabled={(s) => base.includes(s)}
        badgeOf={sourceOf}
        onToggle={(stage, checked) =>
          setAdditions((prev) =>
            sortGuardStages(checked ? [...prev, stage] : prev.filter((s) => s !== stage)),
          )
        }
        header={
          <p className="text-xs text-muted-foreground">
            底線與系統／方案預設不可取消；此處只能替租戶加開階段。
          </p>
        }
      />

      <div className="flex items-center gap-3">
        <Button
          type="button"
          disabled={!dirty || mutation.isPending}
          onClick={() =>
            mutation.mutate(
              {
                tenantId: tenant.tenant_id,
                data: { profile, overrides: { stages: sortGuardStages(additions) }, locked },
              },
              {
                onSuccess: () => toast.success("租戶設定已更新"),
                onError: (err) => toast.error(describeGuardApiError(err)),
              },
            )
          }
        >
          {mutation.isPending ? "儲存中…" : "儲存租戶設定"}
        </Button>
        {!dirty && <span className="text-xs text-muted-foreground">尚無變更</span>}
      </div>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">目前生效</h2>
        <GuardEffectiveBadges effective={tenant.effective} />
      </section>
    </div>
  );
}

function TenantTab({ overview }: { overview: GuardSettingsOverview }) {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const tenant = useTenantGuardSettings(tenantId);

  return (
    <div className="space-y-4">
      <AdminTenantFilter value={tenantId} onChange={setTenantId} />
      {!tenantId ? (
        <p className="text-muted-foreground">請選擇租戶以查看防護階段設定</p>
      ) : tenant.isLoading ? (
        <p className="text-muted-foreground">載入中…</p>
      ) : tenant.isError || !tenant.data ? (
        <p className="text-destructive">無法載入租戶設定</p>
      ) : (
        <TenantEditor key={tenantId} tenant={tenant.data} overview={overview} />
      )}
    </div>
  );
}

/* --------------------------------------------------------------- 有效預覽 */

/** 每列各自讀取（只在此分頁掛載時發出；與租戶分頁共用快取） */
function TenantEffectiveRow({ tenantId, name }: { tenantId: string; name: string }) {
  const tenant = useTenantGuardSettings(tenantId);
  return (
    <TableRow>
      <TableCell className="font-medium">{name}</TableCell>
      {tenant.isLoading ? (
        <TableCell colSpan={3} className="text-muted-foreground">
          載入中…
        </TableCell>
      ) : tenant.isError || !tenant.data ? (
        <TableCell colSpan={3} className="text-destructive">
          無法載入
        </TableCell>
      ) : (
        <>
          <TableCell>{tenant.data.effective.profile}</TableCell>
          <TableCell>
            {tenant.data.locked ? (
              <Badge variant="destructive">已鎖定</Badge>
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </TableCell>
          <TableCell>
            <GuardEffectiveBadges effective={tenant.data.effective} />
          </TableCell>
        </>
      )}
    </TableRow>
  );
}

function EffectivePreviewTab() {
  const tenants = useTenants(1, 100);
  const items = (tenants.data?.items ?? []).filter((t) => t.id !== SYSTEM_TENANT_ID);

  if (tenants.isLoading) return <p className="text-muted-foreground">載入中…</p>;
  if (tenants.isError) return <p className="text-destructive">無法載入租戶清單</p>;
  if (items.length === 0) return <p className="text-muted-foreground">尚無租戶</p>;

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-48">租戶</TableHead>
            <TableHead className="w-28">方案</TableHead>
            <TableHead className="w-20">鎖定</TableHead>
            <TableHead>有效階段 · 來源</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((t) => (
            <TenantEffectiveRow key={t.id} tenantId={t.id} name={t.name} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/* ------------------------------------------------------------------- 頁面 */

export default function AdminGuardControlPage() {
  const { data, isLoading, isError } = useGuardSettingsOverview();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">防護階段</h1>
        <p className="text-muted-foreground">
          設定對話管線各段防護的系統底線與預設、方案預設，以及租戶的加嚴與鎖定；三通路（web / widget / LINE）共用同一份設定
        </p>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">載入中…</p>
      ) : isError || !data ? (
        <p className="text-destructive">無法載入設定</p>
      ) : (
        <Tabs defaultValue="platform">
          <TabsList>
            <TabsTrigger value="platform">系統底線</TabsTrigger>
            <TabsTrigger value="profiles">方案</TabsTrigger>
            <TabsTrigger value="tenant">租戶</TabsTrigger>
            <TabsTrigger value="preview">有效預覽</TabsTrigger>
          </TabsList>
          <TabsContent value="platform" className="mt-4">
            <PlatformTab overview={data} />
          </TabsContent>
          <TabsContent value="profiles" className="mt-4">
            <ProfilesTab overview={data} />
          </TabsContent>
          <TabsContent value="tenant" className="mt-4">
            <TenantTab overview={data} />
          </TabsContent>
          <TabsContent value="preview" className="mt-4">
            <EffectivePreviewTab />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
