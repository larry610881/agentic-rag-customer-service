import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type Mode = "month" | "year";

interface TokenPeriodSelectorProps {
  onChange: (startDate: string, endDate: string) => void;
}

function getMonthOptions() {
  const now = new Date();
  const options: { label: string; value: string }[] = [];
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    options.push({ label: `${yyyy}年${mm}月`, value: `${yyyy}-${mm}` });
  }
  return options;
}

function getYearOptions() {
  const year = new Date().getFullYear();
  return [
    { label: `${year}年`, value: String(year) },
    { label: `${year - 1}年`, value: String(year - 1) },
    { label: `${year - 2}年`, value: String(year - 2) },
  ];
}

function computeDateRange(mode: Mode, value: string) {
  if (mode === "month") {
    const [y, m] = value.split("-").map(Number);
    const start = `${y}-${String(m).padStart(2, "0")}-01`;
    const next = new Date(y, m, 1); // month is 0-indexed in Date, but m is already 1-indexed so this gives next month
    const end = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}-01`;
    return { startDate: start, endDate: end };
  }
  const y = Number(value);
  return { startDate: `${y}-01-01`, endDate: `${y + 1}-01-01` };
}

export function TokenPeriodSelector({ onChange }: TokenPeriodSelectorProps) {
  const now = new Date();
  const defaultMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  const [mode, setMode] = useState<Mode>("month");
  const [monthValue, setMonthValue] = useState(defaultMonth);
  const [yearValue, setYearValue] = useState(String(now.getFullYear()));

  const monthOptions = getMonthOptions();
  const yearOptions = getYearOptions();

  const handleModeChange = (newMode: string) => {
    const m = newMode as Mode;
    setMode(m);
    const value = m === "month" ? monthValue : yearValue;
    const range = computeDateRange(m, value);
    onChange(range.startDate, range.endDate);
  };

  const handleValueChange = (value: string) => {
    if (mode === "month") {
      setMonthValue(value);
    } else {
      setYearValue(value);
    }
    const range = computeDateRange(mode, value);
    onChange(range.startDate, range.endDate);
  };

  return (
    <div className="flex items-center gap-2">
      <Select value={mode} onValueChange={handleModeChange}>
        <SelectTrigger className="w-[100px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="month">月份</SelectItem>
          <SelectItem value="year">年度</SelectItem>
        </SelectContent>
      </Select>
      <Select
        value={mode === "month" ? monthValue : yearValue}
        onValueChange={handleValueChange}
      >
        <SelectTrigger className="w-[140px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(mode === "month" ? monthOptions : yearOptions).map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
