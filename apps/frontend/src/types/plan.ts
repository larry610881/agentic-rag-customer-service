export interface Plan {
  id: string;
  name: string;
  base_monthly_tokens: number;
  addon_pack_tokens: number;
  base_price: string; // Decimal serialized as string
  addon_price: string;
  currency: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreatePlanRequest {
  name: string;
  base_monthly_tokens: number;
  addon_pack_tokens: number;
  base_price: number;
  addon_price: number;
  currency?: string;
  description?: string | null;
  is_active?: boolean;
}

export interface UpdatePlanRequest {
  base_monthly_tokens?: number;
  addon_pack_tokens?: number;
  base_price?: number;
  addon_price?: number;
  currency?: string;
  description?: string | null;
  is_active?: boolean;
}
