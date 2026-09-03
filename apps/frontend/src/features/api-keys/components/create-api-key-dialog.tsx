/** Issue #67 P2 — 建立 API 金鑰對話框（含一次性 client_secret 顯示） */
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { PUBLIC_API_URL } from "@/lib/api-config";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { ApiError } from "@/lib/api-client";
import {
  useApiKeyBotOptions,
  useApiKeyScopes,
  useCreateApiKey,
} from "@/hooks/queries/use-api-keys";
import { API_KEY_SCOPE_LABELS, type ApiKeyCreated } from "@/types/api-key";

interface CreateApiKeyDialogProps {
  /** system_admin 必填（後端要求）；tenant_admin 不傳 */
  tenantId?: string;
  /** system_admin 尚未選租戶時 disable 觸發按鈕 */
  disabled?: boolean;
}

export function CreateApiKeyDialog({ tenantId, disabled }: CreateApiKeyDialogProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [selectedBotIds, setSelectedBotIds] = useState<string[]>([]);
  const [expiresDate, setExpiresDate] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);

  const { data: scopes = [], isLoading: scopesLoading } = useApiKeyScopes();
  const { data: bots = [] } = useApiKeyBotOptions(tenantId);
  const createMutation = useCreateApiKey();

  const resetForm = () => {
    setName("");
    setDescription("");
    setSelectedScopes([]);
    setSelectedBotIds([]);
    setExpiresDate("");
    setFormError(null);
    setCreated(null);
  };

  const handleOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) resetForm();
  };

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!name.trim()) {
      setFormError("請輸入名稱");
      return;
    }
    if (selectedScopes.length === 0) {
      setFormError("請至少選擇一個權限範圍");
      return;
    }
    let expiresAt: string | null = null;
    if (expiresDate) {
      const d = new Date(`${expiresDate}T23:59:59`);
      if (d.getTime() <= Date.now()) {
        setFormError("到期日必須晚於現在");
        return;
      }
      expiresAt = d.toISOString();
    }

    createMutation.mutate(
      {
        name: name.trim(),
        description: description.trim() || undefined,
        scopes: selectedScopes,
        allowed_bot_ids: selectedBotIds,
        expires_at: expiresAt,
        ...(tenantId ? { tenant_id: tenantId } : {}),
      },
      {
        onSuccess: (data) => {
          setCreated(data);
          toast.success("API 金鑰已建立");
        },
        onError: (err) => {
          if (err instanceof ApiError && err.status === 422) {
            setFormError("欄位驗證失敗，請檢查權限範圍與到期日");
          } else if (err instanceof ApiError && err.status === 403) {
            setFormError("沒有權限為此租戶建立金鑰");
          } else {
            setFormError("建立失敗，請稍後再試");
          }
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>建立金鑰</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        {created ? (
          <CreatedSecretPanel created={created} onClose={() => handleOpenChange(false)} />
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>建立 API 金鑰</DialogTitle>
              <DialogDescription>
                金鑰以 OAuth client_credentials 方式換取 access token；client_secret 只會顯示一次。
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="api-key-name">名稱</Label>
                <Input
                  id="api-key-name"
                  value={name}
                  maxLength={100}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="例如：官網整合"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="api-key-description">描述（選填）</Label>
                <Textarea
                  id="api-key-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="用途說明..."
                />
              </div>

              <fieldset className="flex flex-col gap-2">
                <legend className="text-sm font-medium">權限範圍</legend>
                {scopesLoading ? (
                  <p className="text-xs text-muted-foreground">載入中...</p>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {scopes.map((scope) => {
                      const id = `scope-${scope}`;
                      return (
                        <div key={scope} className="flex items-start gap-2">
                          <Checkbox
                            id={id}
                            checked={selectedScopes.includes(scope)}
                            onCheckedChange={() =>
                              setSelectedScopes((prev) => toggle(prev, scope))
                            }
                          />
                          <Label htmlFor={id} className="flex flex-col items-start gap-0.5 font-normal">
                            <span className="font-mono text-xs">{scope}</span>
                            <span className="text-xs text-muted-foreground">
                              {API_KEY_SCOPE_LABELS[scope] ?? ""}
                            </span>
                          </Label>
                        </div>
                      );
                    })}
                  </div>
                )}
              </fieldset>

              <fieldset className="flex flex-col gap-2">
                <legend className="text-sm font-medium">允許的機器人</legend>
                <p className="text-xs text-muted-foreground">
                  未勾選 = 允許全部機器人。
                </p>
                {bots.length === 0 ? (
                  <p className="text-xs text-muted-foreground">目前沒有可選的機器人。</p>
                ) : (
                  <div className="grid max-h-40 gap-2 overflow-y-auto sm:grid-cols-2">
                    {bots.map((bot) => {
                      const id = `bot-${bot.id}`;
                      return (
                        <div key={bot.id} className="flex items-center gap-2">
                          <Checkbox
                            id={id}
                            checked={selectedBotIds.includes(bot.id)}
                            onCheckedChange={() =>
                              setSelectedBotIds((prev) => toggle(prev, bot.id))
                            }
                          />
                          <Label htmlFor={id} className="font-normal">
                            {bot.name}
                          </Label>
                        </div>
                      );
                    })}
                  </div>
                )}
              </fieldset>

              <div className="flex flex-col gap-2">
                <Label htmlFor="api-key-expires">到期日（選填）</Label>
                <Input
                  id="api-key-expires"
                  type="date"
                  value={expiresDate}
                  onChange={(e) => setExpiresDate(e.target.value)}
                  className="w-fit"
                />
                <p className="text-xs text-muted-foreground">留空表示永不過期。</p>
              </div>

              {formError && (
                <p className="text-sm text-destructive" role="alert">
                  {formError}
                </p>
              )}

              <DialogFooter>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending ? "建立中..." : "建立"}
                </Button>
              </DialogFooter>
            </form>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function CreatedSecretPanel({
  created,
  onClose,
}: {
  created: ApiKeyCreated;
  onClose: () => void;
}) {
  const firstScope = created.scopes[0] ?? "chat:send";
  const tokenUrl = `${PUBLIC_API_URL}${API_ENDPOINTS.auth.token}`;
  const chatUrl = `${PUBLIC_API_URL}${API_ENDPOINTS.agent.chat}`;
  const curlExample = [
    `# 1. 換取 access token`,
    `curl -X POST '${tokenUrl}' \\`,
    `  -H 'Content-Type: application/json' \\`,
    `  -d '{"grant_type":"client_credentials","client_id":"${created.client_id}","client_secret":"${created.client_secret}","scope":"${firstScope}"}'`,
    ``,
    `# 2. 用 access_token 呼叫聊天 API`,
    `curl -X POST '${chatUrl}' \\`,
    `  -H 'Authorization: Bearer <access_token>' \\`,
    `  -H 'Content-Type: application/json' \\`,
    `  -d '{"bot_id":"<bot_id>","message":"你好"}'`,
  ].join("\n");

  return (
    <>
      <DialogHeader>
        <DialogTitle>金鑰已建立</DialogTitle>
        <DialogDescription>
          請立即複製並妥善保存 client_secret。
        </DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-4">
        <div
          role="alert"
          className="rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300"
        >
          client_secret 只會顯示這一次，關閉後將無法再次取得；若遺失請撤銷後重新建立。
        </div>

        <CopyField label="client_id" value={created.client_id} />
        <CopyField label="client_secret" value={created.client_secret} />

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <Label>curl 範例</Label>
            <CopyButton value={curlExample} label="複製 curl 範例" />
          </div>
          <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
            {curlExample}
          </pre>
        </div>
      </div>
      <DialogFooter>
        <Button onClick={onClose}>我已保存，關閉</Button>
      </DialogFooter>
    </>
  );
}

function CopyField({ label, value }: { label: string; value: string }) {
  const id = `created-${label}`;
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex gap-2">
        <Input id={id} readOnly value={value} className="font-mono text-xs" />
        <CopyButton value={value} label={`複製 ${label}`} />
      </div>
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
    <Button
      type="button"
      variant="outline"
      size="icon"
      aria-label={label}
      onClick={handleCopy}
    >
      {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
    </Button>
  );
}
