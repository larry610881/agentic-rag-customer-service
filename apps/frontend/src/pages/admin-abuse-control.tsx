import { useEffect, useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import { AbuseControlsTable } from "@/features/abuse-control/components/abuse-controls-table";
import { AbuseEffectiveTable } from "@/features/abuse-control/components/abuse-effective-table";
import { AbuseSettingsForm } from "@/features/abuse-control/components/abuse-settings-form";
import {
  BUILTIN_PROFILE_NAMES,
  describeAbuseApiError,
  fieldLabel,
  formatSettingValue,
  profileLabel,
} from "@/features/abuse-control/abuse-setting-labels";
import {
  useAbuseControls,
  useAbuseSettingsOverview,
  useReleaseAbuseControl,
  useTenantAbuseSettings,
  useUpdateAbuseProfile,
  useUpdatePlatformAbuseSettings,
  useUpdateTenantAbuseSettings,
} from "@/hooks/queries/use-abuse-control";
import { useTenants } from "@/hooks/queries/use-tenants";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AbuseOverrides, AbuseSettingsOverview } from "@/types/abuse-control";

const EMPTY_OVERRIDES: AbuseOverrides = {};

/* ---------------------------------------------------------------- 系統預設 */

function SystemDefaultsTab() {
  const { data, isLoading, isError } = useAbuseSettingsOverview();
  const mutation = useUpdatePlatformAbuseSettings();

  if (isLoading) return <p className="text-muted-foreground">載入中…</p>;
  if (isError || !data) return <p className="text-destructive">無法載入設定</p>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        留空的欄位沿用程式預設值；只有填寫的欄位會被儲存為平台覆寫，並套用到所有租戶。
      </p>
      <AbuseSettingsForm
        idPrefix="platform"
        initialOverrides={data.platform_overrides}
        baseValues={data.effective_default}
        bounds={data.bounds}
        allowedKeys={data.allowed_keys}
        isPending={mutation.isPending}
        submitLabel="儲存系統預設"
        onSubmit={(overrides) =>
          mutation.mutate(overrides, {
            onSuccess: () => toast.success("系統預設已更新"),
            onError: (err) => toast.error(describeAbuseApiError(err)),
          })
        }
      />
    </div>
  );
}

/* ------------------------------------------------------------------- 方案 */

const PROFILE_NAME_PATTERN = /^[a-z0-9][a-z0-9_-]{0,39}$/;

interface ProfileEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  overview: AbuseSettingsOverview;
  /** 有值 = 編輯既有方案；undefined = 新增 */
  editingName?: string;
}

function ProfileEditorDialog({ open, onOpenChange, overview, editingName }: ProfileEditorDialogProps) {
  const [name, setName] = useState("");
  const mutation = useUpdateAbuseProfile();

  useEffect(() => {
    if (open) setName(editingName ?? "");
  }, [open, editingName]);

  const isNew = editingName === undefined;
  const trimmed = name.trim();
  const nameError = !isNew
    ? null
    : trimmed === ""
      ? "請輸入方案名稱"
      : !PROFILE_NAME_PATTERN.test(trimmed)
        ? "名稱限小寫英數、- 與 _，最長 40 字"
        : overview.profiles[trimmed] !== undefined
          ? "已有同名方案"
          : null;

  const initial = isNew ? EMPTY_OVERRIDES : (overview.profiles[editingName] ?? EMPTY_OVERRIDES);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{isNew ? "新增方案" : `編輯方案：${profileLabel(editingName)}`}</DialogTitle>
          <DialogDescription>
            方案是一組覆寫，租戶可指定採用。內建方案儲存後以你的設定為準。
          </DialogDescription>
        </DialogHeader>
        <AbuseSettingsForm
          idPrefix={`profile-${editingName ?? "new"}`}
          initialOverrides={initial}
          baseValues={overview.effective_default}
          bounds={overview.bounds}
          allowedKeys={overview.allowed_keys}
          isPending={mutation.isPending}
          submitLabel={isNew ? "建立方案" : "儲存方案"}
          externallyDirty={isNew && !nameError}
          footerExtra={
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              取消
            </Button>
          }
          onSubmit={(overrides) => {
            if (nameError) {
              toast.error(nameError);
              return;
            }
            mutation.mutate(
              { name: isNew ? trimmed : editingName, overrides },
              {
                onSuccess: () => {
                  toast.success(isNew ? "方案已建立" : "方案已更新");
                  onOpenChange(false);
                },
                onError: (err) => toast.error(describeAbuseApiError(err)),
              },
            );
          }}
        >
          {isNew && (
            <div className="space-y-1.5">
              <Label htmlFor="profile-new-name">方案名稱</Label>
              <Input
                id="profile-new-name"
                value={name}
                placeholder="例：vip"
                autoComplete="off"
                onChange={(e) => setName(e.target.value)}
              />
              {nameError && trimmed !== "" && (
                <p className="text-xs text-destructive">{nameError}</p>
              )}
            </div>
          )}
        </AbuseSettingsForm>
      </DialogContent>
    </Dialog>
  );
}

function ProfilesTab() {
  const { data, isLoading, isError } = useAbuseSettingsOverview();
  const [editor, setEditor] = useState<{ open: boolean; name?: string }>({ open: false });

  const profiles = useMemo(() => {
    if (!data) return [];
    return Object.entries(data.profiles).sort(([a], [b]) => {
      const ab = BUILTIN_PROFILE_NAMES.has(a) ? 0 : 1;
      const bb = BUILTIN_PROFILE_NAMES.has(b) ? 0 : 1;
      return ab - bb || a.localeCompare(b);
    });
  }, [data]);

  if (isLoading) return <p className="text-muted-foreground">載入中…</p>;
  if (isError || !data) return <p className="text-destructive">無法載入方案</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          租戶可指定採用其中一個方案；未指定時採用 standard。
        </p>
        <Button onClick={() => setEditor({ open: true })}>新增方案</Button>
      </div>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-48">方案</TableHead>
              <TableHead className="w-20">類型</TableHead>
              <TableHead>覆寫項目</TableHead>
              <TableHead className="w-24" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {profiles.map(([name, overrides]) => {
              const entries = Object.entries(overrides).filter(([k]) => k !== "profile");
              return (
                <TableRow key={name}>
                  <TableCell className="font-medium">{profileLabel(name)}</TableCell>
                  <TableCell>
                    {BUILTIN_PROFILE_NAMES.has(name) ? (
                      <Badge variant="secondary">內建</Badge>
                    ) : (
                      <Badge variant="outline">自訂</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {entries.length === 0 ? (
                      <span className="text-muted-foreground">（無覆寫，沿用系統預設）</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {entries.map(([k, v]) => (
                          <Badge key={k} variant="outline" className="font-normal">
                            {fieldLabel(k)}：{formatSettingValue(k, v)}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEditor({ open: true, name })}
                    >
                      編輯
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
      <ProfileEditorDialog
        open={editor.open}
        onOpenChange={(open) => setEditor((prev) => ({ ...prev, open }))}
        overview={data}
        editingName={editor.name}
      />
    </div>
  );
}

/* --------------------------------------------------------------- 租戶設定 */

function TenantSettingsTab() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const overview = useAbuseSettingsOverview();
  const tenant = useTenantAbuseSettings(tenantId);
  const mutation = useUpdateTenantAbuseSettings();
  const [profile, setProfile] = useState<string>("standard");

  useEffect(() => {
    if (tenant.data) setProfile(tenant.data.profile);
  }, [tenant.data]);

  const profiles = overview.data?.profiles ?? {};
  // 租戶覆寫的繼承基底 = 平台生效預設 + 所選方案（切換方案時即時反映在提示）
  const baseValues = useMemo(
    () => ({ ...(overview.data?.effective_default ?? {}), ...(profiles[profile] ?? {}) }),
    [overview.data, profiles, profile],
  );

  const profileDirty = !!tenant.data && profile !== tenant.data.profile;

  return (
    <div className="space-y-4">
      <AdminTenantFilter value={tenantId} onChange={setTenantId} />
      {!tenantId ? (
        <p className="text-muted-foreground">請選擇租戶以查看異常控管設定</p>
      ) : tenant.isLoading || overview.isLoading ? (
        <p className="text-muted-foreground">載入中…</p>
      ) : tenant.isError || !tenant.data || !overview.data ? (
        <p className="text-destructive">無法載入租戶設定</p>
      ) : (
        <div className="space-y-6">
          <AbuseSettingsForm
            key={tenantId}
            idPrefix="tenant"
            initialOverrides={tenant.data.overrides}
            baseValues={baseValues}
            bounds={overview.data.bounds}
            allowedKeys={overview.data.allowed_keys}
            isPending={mutation.isPending}
            submitLabel="儲存租戶設定"
            externallyDirty={profileDirty}
            onSubmit={(overrides) =>
              mutation.mutate(
                { tenantId, data: { profile, overrides } },
                {
                  onSuccess: () => toast.success("租戶設定已更新"),
                  onError: (err) => toast.error(describeAbuseApiError(err)),
                },
              )
            }
          >
            <div className="max-w-sm space-y-1.5">
              <Label htmlFor="tenant-profile">採用方案</Label>
              <Select value={profile} onValueChange={setProfile}>
                <SelectTrigger id="tenant-profile" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.keys(profiles).map((name) => (
                    <SelectItem key={name} value={name}>
                      {profileLabel(name)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                下方欄位為租戶專屬微調，優先於方案與系統預設。
              </p>
            </div>
          </AbuseSettingsForm>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">目前生效值</h2>
            <AbuseEffectiveTable
              values={tenant.data.effective}
              allowedKeys={overview.data.allowed_keys}
              layers={[
                { label: "租戶覆寫", overrides: tenant.data.overrides },
                { label: `方案 ${tenant.data.profile}`, overrides: profiles[tenant.data.profile] },
                { label: "平台覆寫", overrides: overview.data.platform_overrides },
              ]}
              fallbackSource="程式預設"
            />
          </section>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- 受控中 */

function ControlsTab() {
  const [tenantId, setTenantId] = useState<string | undefined>();
  const controls = useAbuseControls(tenantId);
  const tenants = useTenants(1, 100);
  const release = useReleaseAbuseControl();

  const tenantNameOf = (id: string) => tenants.data?.items.find((t) => t.id === id)?.name;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <AdminTenantFilter value={tenantId} onChange={setTenantId} />
        <Button
          variant="outline"
          size="sm"
          onClick={() => controls.refetch()}
          disabled={controls.isFetching}
        >
          <RefreshCw className={`mr-1 h-4 w-4 ${controls.isFetching ? "animate-spin" : ""}`} />
          重新整理
        </Button>
        <span className="text-xs text-muted-foreground">每 30 秒自動更新</span>
      </div>
      {controls.isError ? (
        <p className="text-destructive">無法載入受控清單</p>
      ) : (
        <AbuseControlsTable
          items={controls.data}
          isLoading={controls.isLoading}
          fetchedAt={controls.dataUpdatedAt || undefined}
          tenantNameOf={tenantNameOf}
          isReleasing={release.isPending}
          onRelease={(item) => {
            if (!item.subject_id) return;
            release.mutate(
              {
                tenant_id: item.tenant_id,
                subject_kind: item.subject_kind,
                subject_id: item.subject_id,
              },
              {
                onSuccess: () => toast.success(`已解除 ${item.subject_masked} 的控管`),
                onError: (err) => toast.error(describeAbuseApiError(err, "解除失敗")),
              },
            );
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- 頁面 */

export default function AdminAbuseControlPage() {
  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">異常控管</h1>
        <p className="text-muted-foreground">
          設定異常行為評分的門檻與處置（觀察 → 降速 → 冷卻 → 封鎖），並管理目前受控的主體
        </p>
      </div>

      <Tabs defaultValue="system">
        <TabsList>
          <TabsTrigger value="system">系統預設</TabsTrigger>
          <TabsTrigger value="profiles">方案</TabsTrigger>
          <TabsTrigger value="tenant">租戶設定</TabsTrigger>
          <TabsTrigger value="controls">受控中</TabsTrigger>
        </TabsList>
        <TabsContent value="system" className="mt-4">
          <SystemDefaultsTab />
        </TabsContent>
        <TabsContent value="profiles" className="mt-4">
          <ProfilesTab />
        </TabsContent>
        <TabsContent value="tenant" className="mt-4">
          <TenantSettingsTab />
        </TabsContent>
        <TabsContent value="controls" className="mt-4">
          <ControlsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
