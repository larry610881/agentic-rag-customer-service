export interface SystemPromptConfig {
  base_prompt: string;
  router_mode_prompt: string;
  react_mode_prompt: string;
  updated_at: string;
}

export interface UpdateSystemPromptConfigRequest {
  base_prompt: string;
  router_mode_prompt: string;
  react_mode_prompt: string;
}
