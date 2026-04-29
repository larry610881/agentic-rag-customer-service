export interface IndexInfo {
  field: string;
  index_type: string;
}

export interface CollectionInfo {
  name: string;
  row_count: number;
  indexes: IndexInfo[];
  // 顯示用 — admin 不可能用 GUID 找 KB
  kb_id?: string | null;
  kb_name?: string | null;
  tenant_id?: string | null;
  tenant_name?: string | null;
}

export interface CollectionStats {
  row_count: number;
  loaded: boolean;
  indexes: IndexInfo[];
}
