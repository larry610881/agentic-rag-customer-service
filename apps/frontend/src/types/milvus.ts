export interface IndexInfo {
  field: string;
  index_type: string;
}

export interface CollectionInfo {
  name: string;
  row_count: number;
  indexes: IndexInfo[];
}

export interface CollectionStats {
  row_count: number;
  loaded: boolean;
  indexes: IndexInfo[];
}
