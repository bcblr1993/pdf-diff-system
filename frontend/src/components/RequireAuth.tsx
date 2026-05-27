import { useEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { getMe } from "@/api/endpoints";

export default function RequireAuth() {
  const location = useLocation();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  useEffect(() => {
    if (token && !user) {
      getMe().then(setUser).catch(() => {});
    }
  }, [token, user, setUser]);

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <Outlet />;
}
