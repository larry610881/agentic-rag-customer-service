/** 稽核紀錄的實體 / 動作中文標籤（表格與篩選器共用） */
export const ENTITY_TYPE_LABEL: Record<string, string> = {
  guard_rules: "安全規則",
  system_prompt: "系統提示詞",
  bot: "機器人",
  worker: "Worker",
  tenant: "租戶",
};

export const ACTION_LABEL: Record<string, string> = {
  create: "建立",
  update: "更新",
  delete: "刪除",
  reset: "重設",
};
