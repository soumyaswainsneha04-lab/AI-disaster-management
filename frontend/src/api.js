export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "/api";

const TOKEN_LOCAL_KEY = "disaster_ai_access_token";
const TOKEN_SESSION_KEY = "disaster_ai_session_token";

export function getAccessToken() {
  return (
    localStorage.getItem(TOKEN_LOCAL_KEY) ||
    sessionStorage.getItem(TOKEN_SESSION_KEY)
  );
}

export function storeAccessToken(token, remember = false) {
  localStorage.removeItem(TOKEN_LOCAL_KEY);
  sessionStorage.removeItem(TOKEN_SESSION_KEY);

  if (remember) {
    localStorage.setItem(TOKEN_LOCAL_KEY, token);
  } else {
    sessionStorage.setItem(TOKEN_SESSION_KEY, token);
  }
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_LOCAL_KEY);
  sessionStorage.removeItem(TOKEN_SESSION_KEY);
}

export async function apiFetch(path, options = {}) {
  const {
    auth = true,
    headers = {},
    ...rest
  } = options;

  const token = getAccessToken();

  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}${path}`,
      {
        headers: {
          "Content-Type": "application/json",
          ...(auth && token
            ? {
                Authorization: `Bearer ${token}`,
              }
            : {}),
          ...headers,
        },
        ...rest,
      }
    );
  } catch {
    throw new Error(
      "Unable to reach the Disaster AI India server. " +
      "Make sure FastAPI and Vite are both running."
    );
  }

  let data;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    if (
      response.status === 401 &&
      auth
    ) {
      clearAccessToken();

      window.dispatchEvent(
        new Event(
          "disaster-ai-auth-expired"
        )
      );
    }

    const error = new Error(
      data?.detail ||
        data?.message ||
        `Request failed (${response.status})`
    );

    error.status = response.status;
    throw error;
  }

  return data;
}
