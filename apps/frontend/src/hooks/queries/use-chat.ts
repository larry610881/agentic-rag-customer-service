import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { API_ENDPOINTS } from "@/lib/api-endpoints";
import { useAuthStore } from "@/stores/use-auth-store";
import type { ChatRequest, ChatResponse } from "@/types/chat";

export function useSendMessage() {
  const token = useAuthStore((s) => s.token);

  return useMutation({
    mutationFn: (data: ChatRequest) =>
      apiFetch<ChatResponse>(
        API_ENDPOINTS.agent.chat,
        { method: "POST", body: JSON.stringify(data) },
        token ?? undefined,
      ),
  });
}
