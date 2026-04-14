import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PROVIDER_LABELS } from "@/types/provider-setting";
import type { EnabledModel } from "@/types/provider-setting";

interface ModelSelectProps {
  value: string;
  onValueChange: (combined: string) => void;
  enabledModels: EnabledModel[] | undefined;
  placeholder?: string;
  allowEmpty?: boolean;
  id?: string;
}

export function ModelSelect({
  value,
  onValueChange,
  enabledModels,
  placeholder = "請選擇模型",
  allowEmpty = false,
  id,
}: ModelSelectProps) {
  return (
    <Select value={value || undefined} onValueChange={onValueChange}>
      <SelectTrigger id={id}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allowEmpty && (
          <SelectItem value="__none__">不使用（關閉）</SelectItem>
        )}
        {enabledModels && enabledModels.length > 0 ? (
          Object.entries(
            enabledModels.reduce<Record<string, typeof enabledModels>>(
              (groups, m) => {
                (groups[m.provider_name] ??= []).push(m);
                return groups;
              },
              {},
            ),
          ).map(([provider, models]) => (
            <SelectGroup key={provider}>
              <SelectLabel>
                {PROVIDER_LABELS[provider] ?? provider}
              </SelectLabel>
              {models.map((m) => (
                <SelectItem
                  key={`${m.provider_name}:${m.model_id}`}
                  value={`${m.provider_name}:${m.model_id}`}
                >
                  {m.display_name}
                </SelectItem>
              ))}
            </SelectGroup>
          ))
        ) : (
          !allowEmpty && (
            <SelectItem value="__none__" disabled>
              尚未啟用任何模型
            </SelectItem>
          )
        )}
      </SelectContent>
    </Select>
  );
}
