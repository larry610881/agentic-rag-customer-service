import { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Send } from "lucide-react";
import { formatDateTime } from "@/lib/format-date";
import {
  useNotificationChannels,
  useCreateChannel,
  useUpdateChannel,
  useDeleteChannel,
  useTestChannel,
} from "@/hooks/queries/use-notification-channels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  NotificationChannel,
  CreateChannelPayload,
} from "@/types/error-event";

interface ChannelFormData {
  channel_type: "email" | "slack" | "teams";
  name: string;
  enabled: boolean;
  throttle_minutes: number;
  min_severity: string;
  notify_diagnostics: boolean;
  diagnostic_severity: string;
  notify_abuse: boolean;
  // Email-specific
  smtp_host: string;
  smtp_port: number;
  smtp_use_tls: boolean;
  smtp_username: string;
  smtp_password: string;
  from_address: string;
  recipients: string;
  // Webhook-specific
  webhook_url: string;
}

function channelTypeBadgeVariant(
  type: string,
): "default" | "secondary" | "outline" {
  switch (type) {
    case "email":
      return "default";
    case "slack":
      return "secondary";
    case "teams":
      return "outline";
    default:
      return "outline";
  }
}

/** Email 渠道缺 recipients 或 smtp_host 時，後端送信會略過（不失敗）；UI 提示「未設定」 */
function isEmailConfigIncomplete(channel: NotificationChannel): boolean {
  if (channel.channel_type !== "email") return false;
  const cfg = channel.config ?? {};
  const recipients = cfg.recipients;
  const hasRecipients = Array.isArray(recipients) && recipients.length > 0;
  const hasHost =
    typeof cfg.smtp_host === "string" && cfg.smtp_host.trim().length > 0;
  return !hasRecipients || !hasHost;
}

function buildConfig(data: ChannelFormData): Record<string, unknown> {
  if (data.channel_type === "email") {
    return {
      smtp_host: data.smtp_host,
      smtp_port: data.smtp_port,
      smtp_use_tls: data.smtp_use_tls,
      smtp_username: data.smtp_username,
      smtp_password: data.smtp_password,
      from_address: data.from_address,
      recipients: data.recipients
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
  }
  return { webhook_url: data.webhook_url };
}

function toFormData(channel?: NotificationChannel | null): ChannelFormData {
  if (!channel) {
    return {
      channel_type: "slack",
      name: "",
      enabled: true,
      throttle_minutes: 5,
      min_severity: "all",
      notify_diagnostics: false,
      diagnostic_severity: "critical",
      notify_abuse: true,
      smtp_host: "",
      smtp_port: 587,
      smtp_use_tls: true,
      smtp_username: "",
      smtp_password: "",
      from_address: "",
      recipients: "",
      webhook_url: "",
    };
  }
  const cfg = channel.config ?? {};
  return {
    channel_type: channel.channel_type,
    name: channel.name,
    enabled: channel.enabled,
    throttle_minutes: channel.throttle_minutes,
    min_severity: channel.min_severity,
    notify_diagnostics: channel.notify_diagnostics ?? false,
    diagnostic_severity: channel.diagnostic_severity ?? "critical",
    notify_abuse: channel.notify_abuse ?? true,
    smtp_host: (cfg.smtp_host as string) ?? "",
    smtp_port: (cfg.smtp_port as number) ?? 587,
    smtp_use_tls: (cfg.smtp_use_tls as boolean) ?? true,
    smtp_username: (cfg.smtp_username as string) ?? "",
    smtp_password: (cfg.smtp_password as string) ?? "",
    from_address: (cfg.from_address as string) ?? "",
    recipients: Array.isArray(cfg.recipients)
      ? (cfg.recipients as string[]).join(", ")
      : "",
    webhook_url: (cfg.webhook_url as string) ?? "",
  };
}

function ChannelFormDialog({
  open,
  onOpenChange,
  channel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channel?: NotificationChannel | null;
}) {
  const createMutation = useCreateChannel();
  const updateMutation = useUpdateChannel();

  const { register, handleSubmit, watch, control, reset } =
    useForm<ChannelFormData>({ defaultValues: toFormData(channel) });

  // useForm 的 defaultValues 只在首次 mount 生效；Dialog 常駐、channel 會切換，
  // 因此每次開啟都以當前 channel 重設表單（新增 → 預設值、編輯 → 回填）。
  useEffect(() => {
    if (open) reset(toFormData(channel));
  }, [open, channel, reset]);

  const channelType = watch("channel_type");

  const onSubmit = (data: ChannelFormData) => {
    const payload: CreateChannelPayload = {
      channel_type: data.channel_type,
      name: data.name,
      enabled: data.enabled,
      config: buildConfig(data),
      throttle_minutes: data.throttle_minutes,
      min_severity: data.min_severity,
      notify_diagnostics: data.notify_diagnostics,
      diagnostic_severity: data.diagnostic_severity,
      notify_abuse: data.notify_abuse,
    };

    if (channel) {
      updateMutation.mutate(
        { id: channel.id, data: payload },
        {
          onSuccess: () => {
            toast.success("通知渠道已更新");
            reset();
            onOpenChange(false);
          },
          onError: () => toast.error("更新失敗"),
        },
      );
    } else {
      createMutation.mutate(payload, {
        onSuccess: () => {
          toast.success("通知渠道已建立");
          reset();
          onOpenChange(false);
        },
        onError: () => toast.error("建立失敗"),
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {channel ? "編輯通知渠道" : "新增通知渠道"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label>名稱</Label>
            <Input {...register("name", { required: true })} placeholder="例：Slack #alerts" />
          </div>

          <div className="space-y-2">
            <Label>渠道類型</Label>
            <Controller
              name="channel_type"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value}
                  onValueChange={field.onChange}
                  disabled={!!channel}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="slack">Slack</SelectItem>
                    <SelectItem value="teams">Teams</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          <div className="flex items-center gap-2">
            <Controller
              name="enabled"
              control={control}
              render={({ field }) => (
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              )}
            />
            <Label>啟用</Label>
          </div>

          <div className="space-y-2">
            <Label>節流間隔（分鐘）</Label>
            <Input
              type="number"
              {...register("throttle_minutes", { valueAsNumber: true })}
            />
          </div>

          <div className="space-y-3 border-t pt-3">
            <h4 className="text-sm font-medium">錯誤通知</h4>
            <div className="space-y-2">
              <Label>嚴重度篩選</Label>
              <Controller
                name="min_severity"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部</SelectItem>
                      <SelectItem value="5xx_only">僅 5xx</SelectItem>
                      <SelectItem value="off">關閉</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>

          <div className="space-y-3 border-t pt-3">
            <h4 className="text-sm font-medium">RAG 品質告警</h4>
            <div className="flex items-center gap-2">
              <Controller
                name="notify_diagnostics"
                control={control}
                render={({ field }) => (
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
              <Label>啟用診斷告警</Label>
            </div>
            <div className="space-y-2">
              <Label>告警嚴重度</Label>
              <Controller
                name="diagnostic_severity"
                control={control}
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="critical">僅 Critical</SelectItem>
                      <SelectItem value="warning">Warning 以上</SelectItem>
                      <SelectItem value="all">全部</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
              <p className="text-xs text-muted-foreground">
                評估分數低於診斷規則門檻時通知
              </p>
            </div>
          </div>

          <div className="space-y-3 border-t pt-3">
            <h4 className="text-sm font-medium">異常控管</h4>
            <div className="flex items-center gap-2">
              <Controller
                name="notify_abuse"
                control={control}
                render={({ field }) => (
                  <Switch
                    id="notify_abuse"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                )}
              />
              <Label htmlFor="notify_abuse">異常控管告警</Label>
            </div>
            <p className="text-xs text-muted-foreground">
              L3/L4 冷卻與封鎖、控管失效（fail-open）、429 突增、每日摘要
            </p>
          </div>

          {channelType === "email" && (
            <div className="space-y-3 border-t pt-3">
              <h4 className="text-sm font-medium">SMTP 設定</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>SMTP Host</Label>
                  <Input {...register("smtp_host")} placeholder="smtp.gmail.com" />
                </div>
                <div className="space-y-2">
                  <Label>SMTP Port</Label>
                  <Input
                    type="number"
                    {...register("smtp_port", { valueAsNumber: true })}
                  />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Controller
                  name="smtp_use_tls"
                  control={control}
                  render={({ field }) => (
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  )}
                />
                <Label>使用 TLS</Label>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>帳號</Label>
                  <Input {...register("smtp_username")} />
                </div>
                <div className="space-y-2">
                  <Label>密碼</Label>
                  <Input type="password" {...register("smtp_password")} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>寄件人</Label>
                <Input {...register("from_address")} placeholder="alert@example.com" />
              </div>
              <div className="space-y-2">
                <Label>收件人（逗號分隔）</Label>
                <Input {...register("recipients")} placeholder="a@example.com, b@example.com" />
              </div>
            </div>
          )}

          {(channelType === "slack" || channelType === "teams") && (
            <div className="space-y-3 border-t pt-3">
              <h4 className="text-sm font-medium">Webhook 設定</h4>
              <div className="space-y-2">
                <Label>Webhook URL</Label>
                <Input
                  {...register("webhook_url")}
                  placeholder={
                    channelType === "slack"
                      ? "https://hooks.slack.com/services/..."
                      : "https://prod-xx.xxx.logic.azure.com/workflows/..."
                  }
                />
                {channelType === "teams" && (
                  <p className="text-xs text-muted-foreground">
                    請使用 Teams Workflows（Power Automate）「When a Teams webhook request is received」產生的 URL；舊版 Office 365 Connector Incoming Webhook 已退場。
                  </p>
                )}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {channel ? "更新" : "建立"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminNotificationChannelsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingChannel, setEditingChannel] =
    useState<NotificationChannel | null>(null);

  const { data: channels, isLoading } = useNotificationChannels();
  const deleteMutation = useDeleteChannel();
  const testMutation = useTestChannel();

  const handleDelete = (id: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success("通知渠道已刪除"),
      onError: () => toast.error("刪除失敗"),
    });
  };

  const handleTest = (id: string) => {
    testMutation.mutate(id, {
      onSuccess: (data) =>
        data.success
          ? toast.success("測試通知已送出")
          : toast.error(data.message || "測試失敗"),
      onError: () => toast.error("測試失敗"),
    });
  };

  const handleEdit = (channel: NotificationChannel) => {
    setEditingChannel(channel);
    setDialogOpen(true);
  };

  const handleAdd = () => {
    setEditingChannel(null);
    setDialogOpen(true);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">通知渠道</h1>
          <p className="text-muted-foreground">
            管理錯誤通知、RAG 品質告警與異常控管告警的發送渠道
          </p>
        </div>
        <Button onClick={handleAdd}>
          <Plus className="h-4 w-4 mr-2" />
          新增渠道
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>名稱</TableHead>
              <TableHead className="w-24">類型</TableHead>
              <TableHead className="w-24">狀態</TableHead>
              <TableHead className="w-44">訂閱</TableHead>
              <TableHead className="w-32">節流（分鐘）</TableHead>
              <TableHead className="w-40">建立時間</TableHead>
              <TableHead className="w-40">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  載入中...
                </TableCell>
              </TableRow>
            ) : !channels || channels.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  尚無通知渠道
                </TableCell>
              </TableRow>
            ) : (
              channels.map((ch) => (
                <TableRow key={ch.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <span>{ch.name}</span>
                      {isEmailConfigIncomplete(ch) && (
                        <Badge
                          variant="outline"
                          title="缺少收件人或 SMTP Host，送信時會略過此渠道"
                        >
                          未設定
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={channelTypeBadgeVariant(ch.channel_type)}>
                      {ch.channel_type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={ch.enabled ? "default" : "outline"}>
                      {ch.enabled ? "啟用" : "停用"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {ch.min_severity !== "off" && (
                        <Badge variant="secondary">錯誤</Badge>
                      )}
                      {ch.notify_diagnostics && (
                        <Badge variant="outline">診斷</Badge>
                      )}
                      {ch.notify_abuse && (
                        <Badge variant="outline">異常告警</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>{ch.throttle_minutes}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {formatDateTime(ch.created_at)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleEdit(ch)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleTest(ch.id)}
                        disabled={testMutation.isPending}
                      >
                        <Send className="h-4 w-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>確認刪除</AlertDialogTitle>
                            <AlertDialogDescription>
                              確定要刪除通知渠道「{ch.name}」嗎？此操作無法復原。
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>取消</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDelete(ch.id)}
                            >
                              刪除
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <ChannelFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        channel={editingChannel}
      />
    </div>
  );
}
