import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ModelSelect } from "@/components/shared/model-select";
import { useEnabledModels } from "@/hooks/queries/use-provider-settings";
import { useAuthStore } from "@/stores/use-auth-store";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import type { Tenant } from "@/types/auth";

const MODEL_FIELDS = [
  { key: "default_ocr_model", label: "OCR 解析" },
  { key: "default_context_model", label: "上下文生成（Contextual Retrieval）" },
  { key: "default_classification_model", label: "自動分類" },
  // S-KB-Followup.2
  { key: "default_intent_model", label: "意圖分類（Intent Classifier）" },
  { key: "default_summary_model", label: "對話摘要（Conversation Summary）" },
] as const;

type ModelKey = (typeof MODEL_FIELDS)[number]["key"];

export function DefaultModelSettings() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.tenantId);
  const { data: enabledModels } = useEnabledModels();

  const [values, setValues] = useState<Record<ModelKey, string>>({
    default_ocr_model: "",
    default_context_model: "",
    default_classification_model: "",
    default_intent_model: "",
    default_summary_model: "",
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Fetch current tenant config
  useEffect(() => {
    if (!token || !tenantId) return;
    setLoading(true);
    apiFetch<Tenant>(
      `/api/v1/tenants/${tenantId}`,
      {},
      token,
    )
      .then((tenant) => {
        setValues({
          default_ocr_model: tenant.default_ocr_model || "",
          default_context_model: tenant.default_context_model || "",
          default_classification_model: tenant.default_classification_model || "",
          default_intent_model: tenant.default_intent_model || "",
          default_summary_model: tenant.default_summary_model || "",
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, tenantId]);

  const handleSave = async () => {
    if (!token || !tenantId) return;
    setSaving(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(values).map(([k, v]) => [k, v === "__none__" ? "" : v]),
      );
      await apiFetch(
        API_ENDPOINTS.tenants.config(tenantId),
        { method: "PATCH", body: JSON.stringify(payload) },
        token,
      );
      toast.success("預設模型已儲存");
    } catch {
      toast.error("儲存失敗");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="text-sm text-muted-foreground">載入中...</div>
    );
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border p-4">
      <div>
        <h3 className="text-sm font-semibold">知識庫預設模型</h3>
        <p className="text-xs text-muted-foreground">
          個別知識庫未設定模型時，使用這裡的預設值。
        </p>
      </div>

      {MODEL_FIELDS.map((field) => (
        <div key={field.key} className="flex flex-col gap-1">
          <Label className="text-sm">{field.label}</Label>
          <ModelSelect
            value={values[field.key]}
            onValueChange={(v) =>
              setValues((prev) => ({ ...prev, [field.key]: v }))
            }
            enabledModels={enabledModels}
            placeholder="未設定"
            allowEmpty
            emptyLabel="未設定"
          />
        </div>
      ))}

      <Button onClick={handleSave} disabled={saving} className="self-start">
        {saving ? (
          <>
            <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            儲存中...
          </>
        ) : (
          "儲存預設"
        )}
      </Button>
    </div>
  );
}
