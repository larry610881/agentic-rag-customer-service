/** Issue #68 P7b — Widget 宿主身分綁定：租戶 identity secret 與驗證政策 */
import { useState } from "react";
import { Check, ChevronDown, Copy, KeyRound, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { AdminTenantFilter } from "@/features/admin/components/admin-tenant-filter";
import {
  useRotateWidgetIdentitySecret,
  useUpdateWidgetIdentityPolicy,
  useWidgetIdentityStatus,
} from "@/hooks/queries/use-widget-identity";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format-date";
import { useAuthStore } from "@/stores/use-auth-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type {
  UpdateWidgetIdentityPolicyRequest,
  WidgetIdentityStatus,
} from "@/types/widget-identity";

/** 把後端 `{"detail": "..."}` 轉成可讀訊息；其餘落到 fallback */
export function describeWidgetIdentityError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail) return parsed.detail;
    } catch {
      /* body 不是 JSON，落到下方 */
    }
    if (err.status === 403) return "沒有權限執行此操作";
    if (err.status === 422) return "請求參數不正確";
  }
  return fallback;
}

export default function WidgetIdentityPage() {
  const role = useAuthStore((s) => s.role);
  const ownTenantId = useAuthStore((s) => s.tenantId);
  const isSystemAdmin = role === "system_admin";
  const [selectedTenantId, setSelectedTenantId] = useState<string | undefined>();

  // tenant_admin 一律不帶 tenant_id（後端取自 token）；system_admin 必帶
  const targetTenantId = isSystemAdmin ? selectedTenantId : undefined;
  const ready = !isSystemAdmin || !!selectedTenantId;

  const status = useWidgetIdentityStatus(targetTenantId, ready);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Widget 身分綁定</h1>
        <p className="text-muted-foreground">
          讓嵌入 widget 的宿主網站把自家會員綁進對話：宿主後端用 secret 簽章，widget 驗證後對話與回饋歸戶到該會員。
        </p>
      </div>

      {isSystemAdmin ? (
        <div className="flex flex-wrap items-center gap-3">
          <Label>租戶</Label>
          <AdminTenantFilter value={selectedTenantId} onChange={setSelectedTenantId} />
          {!selectedTenantId && (
            <span className="text-xs text-muted-foreground">請先選擇租戶</span>
          )}
        </div>
      ) : !ownTenantId ? (
        <p className="text-muted-foreground">無法辨識目前租戶</p>
      ) : null}

      {ready && (
        <>
          {status.isLoading ? (
            <p className="text-muted-foreground">載入中…</p>
          ) : status.isError || !status.data ? (
            <p className="text-destructive">無法載入身分綁定設定</p>
          ) : (
            <IdentitySettings status={status.data} tenantId={targetTenantId} />
          )}
        </>
      )}

      <IntegrationHelp />
    </div>
  );
}

function IdentitySettings({
  status,
  tenantId,
}: {
  status: WidgetIdentityStatus;
  tenantId?: string;
}) {
  const update = useUpdateWidgetIdentityPolicy();
  const rotate = useRotateWidgetIdentitySecret();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);

  const hasSecret = status.has_secret;
  const switchesDisabled = !hasSecret || update.isPending;

  const handleToggle = (data: UpdateWidgetIdentityPolicyRequest) => {
    update.mutate(
      { tenantId, data },
      {
        onSuccess: (saved) => {
          if (!saved.has_secret) {
            toast.error("尚未產生 secret，設定未變更");
            return;
          }
          toast.success("設定已更新");
        },
        onError: (err) => toast.error(describeWidgetIdentityError(err, "更新失敗")),
      },
    );
  };

  const handleRotate = () => {
    rotate.mutate(
      { tenantId },
      {
        onSuccess: (data) => {
          setRevealedSecret(data.secret);
          toast.success(hasSecret ? "secret 已輪替" : "secret 已產生");
        },
        onError: (err) => toast.error(describeWidgetIdentityError(err, "輪替失敗")),
      },
    );
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>目前狀態</CardTitle>
          <CardDescription>
            secret 只在產生／輪替當下顯示一次；此處只顯示是否已設定與最後輪替時間。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 sm:grid-cols-2">
            <StatusRow label="secret" testId="status-has-secret">
              {hasSecret ? (
                <Badge variant="secondary">已設定</Badge>
              ) : (
                <Badge variant="outline">尚未產生</Badge>
              )}
            </StatusRow>
            <StatusRow label="身分綁定" testId="status-is-enabled">
              {status.is_enabled ? (
                <Badge>已啟用</Badge>
              ) : (
                <Badge variant="outline">停用</Badge>
              )}
            </StatusRow>
            <StatusRow label="強制驗證" testId="status-enforce-verified">
              {status.enforce_verified ? (
                <Badge variant="destructive">開啟</Badge>
              ) : (
                <Badge variant="outline">關閉</Badge>
              )}
            </StatusRow>
            <StatusRow label="最後輪替時間" testId="status-rotated-at">
              {status.rotated_at ? formatDateTime(status.rotated_at) : "—"}
            </StatusRow>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>驗證政策</CardTitle>
          {!hasSecret && (
            <CardDescription data-testid="no-secret-hint">
              請先產生 secret，才能啟用身分綁定與強制驗證。
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <Label htmlFor="widget-identity-enabled">啟用身分綁定</Label>
              <p className="text-xs text-muted-foreground">
                關閉時 widget 的 identify 一律回 <code>disabled</code>，對話維持匿名訪客。
              </p>
            </div>
            <Switch
              id="widget-identity-enabled"
              checked={status.is_enabled}
              disabled={switchesDisabled}
              onCheckedChange={(v) => handleToggle({ is_enabled: v })}
            />
          </div>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <Label htmlFor="widget-identity-enforce">強制驗證</Label>
              <p className="text-xs text-muted-foreground">
                開啟後簽章錯誤的 identify 直接回 403；關閉時失敗只降級為匿名並計分。
              </p>
            </div>
            <Switch
              id="widget-identity-enforce"
              checked={status.enforce_verified}
              disabled={switchesDisabled}
              onCheckedChange={(v) => handleToggle({ enforce_verified: v })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>identity secret</CardTitle>
          <CardDescription>
            宿主後端用這把 secret 計算 HMAC 簽章；請放進宿主後端的密鑰管理，不得進前端。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => setConfirmOpen(true)} disabled={rotate.isPending}>
            {hasSecret ? (
              <RefreshCw className={`mr-1 h-4 w-4 ${rotate.isPending ? "animate-spin" : ""}`} />
            ) : (
              <KeyRound className="mr-1 h-4 w-4" />
            )}
            {hasSecret ? "輪替 secret" : "產生 secret"}
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{hasSecret ? "確定要輪替 secret？" : "產生 identity secret"}</AlertDialogTitle>
            <AlertDialogDescription>
              {hasSecret
                ? "舊的 secret 會立即失效，宿主後端在更新 secret 之前簽出的身分都會驗證失敗；請先準備好更新宿主後端。新 secret 只會顯示一次。"
                : "系統會產生一把新的 identity secret，只會顯示一次；請立即複製並放到宿主後端的密鑰管理。"}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleRotate}>
              {hasSecret ? "確認輪替" : "確認產生"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog
        open={revealedSecret !== null}
        onOpenChange={(open) => {
          if (!open) setRevealedSecret(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新的 identity secret</DialogTitle>
            <DialogDescription>請立即複製並妥善保存。</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div
              role="alert"
              className="rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300"
            >
              關閉後無法再次查看；若遺失請重新輪替。
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="widget-identity-secret">secret</Label>
              <div className="flex gap-2">
                <Input
                  id="widget-identity-secret"
                  readOnly
                  value={revealedSecret ?? ""}
                  className="font-mono text-xs"
                />
                <CopyButton value={revealedSecret ?? ""} label="複製 secret" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setRevealedSecret(null)}>我已保存，關閉</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function StatusRow({
  label,
  testId,
  children,
}: {
  label: string;
  testId: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border p-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm" data-testid={testId}>
        {children}
      </dd>
    </div>
  );
}

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success("已複製");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("複製失敗，請手動選取複製");
    }
  };
  return (
    <Button type="button" variant="outline" size="icon" aria-label={label} onClick={handleCopy}>
      {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}

const NODE_SAMPLE = `const crypto = require("crypto");
const exp = Math.floor(Date.now() / 1000) + 600;
const hash = crypto.createHmac("sha256", process.env.WIDGET_IDENTITY_SECRET)
  .update(\`\${userId}.\${exp}\`).digest("hex");
res.json({ userId, exp, hash });`;

const PYTHON_SAMPLE = `import hmac, hashlib, time, os
exp = int(time.time()) + 600
hash_ = hmac.new(os.environ["WIDGET_IDENTITY_SECRET"].encode(),
                 f"{user_id}.{exp}".encode(), hashlib.sha256).hexdigest()
return {"userId": user_id, "exp": exp, "hash": hash_}`;

const WIDGET_SAMPLE = `window.AgenticRagWidget.identify({ userId, exp, hash, name, email })
  .then((r) => console.log(r.identified, r.reason));`;

function IntegrationHelp() {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between p-6 text-left"
            aria-expanded={open}
          >
            <div>
              <CardTitle>宿主整合方式</CardTitle>
              <CardDescription className="mt-1">
                hash 只能在宿主後端計算；前端只轉交 userId / exp / hash。
              </CardDescription>
            </div>
            <ChevronDown
              className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="space-y-5 pt-0">
            <section className="space-y-2">
              <h3 className="text-sm font-semibold">協定</h3>
              <pre className="overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
{`exp  = 現在 + N 秒（建議 5–15 分鐘，最多 24 小時）
hash = HMAC-SHA256(secret, \`\${userId}.\${exp}\`)  → hex 小寫`}
              </pre>
              <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                <li>secret 只放宿主後端；前端只轉交 {"{userId, exp, hash}"}。</li>
                <li>exp 超過 24 小時一律無效。</li>
                <li>簽章失敗會計入異常分數；連續失敗會被降速。開啟「強制驗證」時直接回 403。</li>
              </ul>
            </section>

            <section className="space-y-2">
              <h3 className="text-sm font-semibold">宿主後端（Node.js）</h3>
              <pre className="overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{NODE_SAMPLE}</pre>
            </section>

            <section className="space-y-2">
              <h3 className="text-sm font-semibold">宿主後端（Python）</h3>
              <pre className="overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{PYTHON_SAMPLE}</pre>
            </section>

            <section className="space-y-2">
              <h3 className="text-sm font-semibold">前端（widget 載入後）</h3>
              <pre className="overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{WIDGET_SAMPLE}</pre>
              <p className="text-xs text-muted-foreground">
                回應 <code>identified: true</code> 表示通過並已換票；<code>false</code> 時{" "}
                <code>reason</code> 為 <code>invalid</code> / <code>disabled</code> /{" "}
                <code>not_configured</code>，對話維持匿名。
              </p>
            </section>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
