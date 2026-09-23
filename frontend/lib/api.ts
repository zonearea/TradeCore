const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5080";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type ProblemBody = {
  title?: string;
  detail?: string;
};

export type CurrentUser = {
  id: string | null;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
  role: string | null;
};

function endpoint(path: string) {
  const suffix = path.replace(/^\/api/, "");
  return `/api/backend${suffix}`;
}

async function request<T>(path: string, init?: RequestInit, retry = true): Promise<T> {
  const response = await fetch(endpoint(path), {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (response.status === 401 && retry && path !== "/api/auth/login" && path !== "/api/auth/refresh") {
    const refreshed = await fetch(endpoint("/api/auth/refresh"), {
      method: "POST",
      credentials: "include",
    });

    if (refreshed.ok) {
      return request<T>(path, init, false);
    }
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as ProblemBody | null;
    throw new ApiError(response.status, problem?.detail || problem?.title || "İstek başarısız oldu.");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function login(email: string, password: string) {
  return request<{ accessToken: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function register(input: {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
}) {
  return request<{ id: string }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function logout() {
  return request<void>("/api/auth/logout", { method: "POST" });
}

export function currentUser() {
  return request<CurrentUser>("/api/auth/me");
}

export { API_URL };
