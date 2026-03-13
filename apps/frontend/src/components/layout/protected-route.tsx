import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/stores/use-auth-store";
import { ROUTES } from "@/routes/paths";

export function ProtectedRoute() {
  const token = useAuthStore((s) => s.token);

  if (!token) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  return <Outlet />;
}

export function AdminRoute() {
  const token = useAuthStore((s) => s.token);
  const role = useAuthStore((s) => s.role);

  if (!token) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  if (role !== "system_admin") {
    return <Navigate to={ROUTES.CHAT} replace />;
  }

  return <Outlet />;
}
