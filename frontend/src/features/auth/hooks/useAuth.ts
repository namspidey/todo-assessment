import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useLogout, fetchCurrentUser } from "../api/auth";
import { queryClient } from "@/lib/queryClient";

export function useAuth() {
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  const token = localStorage.getItem("access_token");
  const isAuthenticated = !!token;

  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
    enabled: isAuthenticated,
    retry: false,
  });

  const logout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        // Clear all cached data on logout to prevent data leaking to next user
        queryClient.clear();
        navigate("/login");
      },
      onError: () => {
        // Even on error, clear local tokens and redirect
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        // Clear cache even on error
        queryClient.clear();
        navigate("/login");
      },
    });
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    logout,
  };
}
