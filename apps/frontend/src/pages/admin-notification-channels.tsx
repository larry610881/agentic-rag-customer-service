import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Send } from "lucide-react";
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
    useForm<ChannelFormData>({
      defaultValues: channel
        ? {
            channel_type: channel.channel_type,
            name: channel.name,
            enabled: channel.enabled,
            throttle_minutes: channel.throttle_minutes,
            min_severity: channel.min_severity,
            smtp_host: (channel.config.smtp_host as string) ?? "",
            smtp_port: (channel.config.smtp_port as number) ?? 587,
            smtp_use_tls: (channel.config.smtp_use_tls as boolean) ?? true,
            smtp_username: (channel.config.smtp_username as string) ?? "",
            smtp_password: (channel.config.smtp_password as string) ?? "",
            from_address: (channel.config.from_address as string) ?? "",
            recipients: Array.isArray(channel.config.recipients)
              ? (channel.config.recipients as string[]).join(", ")
              : "",
            webhook_url: (channel.config.webhook_url as string) ?? "",
          }
        : {
            channel_type: "slack",
            name: "",
            enabled: true,
            throttle_minutes: 5,
            min_severity: "all",
            smtp_host: "",
            smtp_port: 587,
            smtp_use_tls: true,
            smtp_username: "",
            smtp_password: "",
            from_address: "",
            recipients: "",
            webhook_url: "",
          },
    });

  const channelType = watch("channel_type");

  const onSubmit = (data: ChannelFormData) => {
    const payload: CreateChannelPayload = {
      channel_type: data.channel_type,
      name: data.name,
      enabled: data.enabled,
      config: buildConfig(data),
      throttle_minutes: data.throttle_minutes,
      min_severity: data.min_severity,
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

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>節流間隔（分鐘）</Label>
              <Input
                type="number"
                {...register("throttle_minutes", { valueAsNumber: true })}
              />
            </div>
            <div className="space-y-2">
              <Label>最低嚴重度</Label>
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
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
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
                      : "https://outlook.office.com/webhook/..."
                  }
                />
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
            管理錯誤通知的發送渠道（Email / Slack / Teams）
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
              <TableHead className="w-32">節流（分鐘）</TableHead>
              <TableHead className="w-40">建立時間</TableHead>
              <TableHead className="w-40">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  載入中...
                </TableCell>
              </TableRow>
            ) : !channels || channels.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  尚無通知渠道
                </TableCell>
              </TableRow>
            ) : (
              channels.map((ch) => (
                <TableRow key={ch.id}>
                  <TableCell className="font-medium">{ch.name}</TableCell>
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
                  <TableCell>{ch.throttle_minutes}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(ch.created_at).toLocaleString("zh-TW")}
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
