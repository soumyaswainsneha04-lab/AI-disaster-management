import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  apiFetch,
  clearAccessToken,
  getAccessToken,
  storeAccessToken,
} from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    const token = getAccessToken();

    if (!token) {
      setUser(null);
      setLoading(false);
      return null;
    }

    try {
      const data = await apiFetch("/auth/me");
      setUser(data.user);
      return data.user;
    } catch {
      clearAccessToken();
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshUser();

    const expired = () => {
      clearAccessToken();
      setUser(null);
    };

    window.addEventListener("disaster-ai-auth-expired", expired);

    return () =>
      window.removeEventListener(
        "disaster-ai-auth-expired",
        expired
      );
  }, []);

  async function login(email, password, remember = false) {
    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email, password }),
      });

      storeAccessToken(data.access_token, remember);
      setUser(data.user);

      return { ok: true, user: data.user };
    } catch (error) {
      return {
        ok: false,
        message: error.message || "Unable to sign in.",
      };
    }
  }

  async function googleLogin(
    credential,
    {
      remember = false,
      requestedRole = null,
      phone = "",
      organization = "",
      state = "",
      district = "",
    } = {}
  ) {
    try {
      const data = await apiFetch("/auth/google", {
        method: "POST",
        auth: false,
        body: JSON.stringify({
          credential,
          remember,
          requested_role: requestedRole,
          phone,
          organization,
          state,
          district,
        }),
      });

      if (data.account_status === "PENDING") {
        return {
          ok: true,
          pending: true,
          message: data.message,
          user: data.user,
        };
      }

      storeAccessToken(data.access_token, remember);
      setUser(data.user);

      return {
        ok: true,
        pending: false,
        user: data.user,
      };
    } catch (error) {
      return {
        ok: false,
        message: error.message || "Google sign-in failed.",
      };
    }
  }

  function logout() {
    clearAccessToken();
    setUser(null);
  }

  async function changePassword(
    currentPassword,
    newPassword
  ) {
    try {
      await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        message: error.message,
      };
    }
  }

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      googleLogin,
      logout,
      refreshUser,
      changePassword,
    }),
    [user, loading]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
