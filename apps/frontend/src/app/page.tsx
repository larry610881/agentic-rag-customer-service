"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/use-auth-store";

export default function Home() {
  const token = useAuthStore((s) => s.token);
  const router = useRouter();

  useEffect(() => {
    if (token) {
      router.replace("/chat");
    } else {
      router.replace("/login");
    }
  }, [token, router]);

  return null;
}
