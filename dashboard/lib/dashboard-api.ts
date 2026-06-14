export class DashboardApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "DashboardApiError";
    this.status = status;
    this.code = code;
  }
}

function errorFromPayload(payload: unknown, status: number) {
  const error =
    typeof payload === "object" && payload !== null && "error" in payload
      ? (payload as { error?: { message?: unknown; code?: unknown } }).error
      : undefined;
  const message =
    typeof error?.message === "string" && error.message.trim()
      ? error.message
      : "ไม่สามารถเชื่อมต่อระบบได้ กรุณาลองอีกครั้ง";
  const code =
    typeof error?.code === "string" && error.code.trim()
      ? error.code
      : `HTTP_${status}`;
  return new DashboardApiError(message, status, code);
}

function dataFromPayload<T>(payload: unknown, status: number): T {
  if (typeof payload === "object" && payload !== null && "data" in payload) {
    return (payload as { data: T }).data;
  }
  throw new DashboardApiError(
    "ข้อมูลที่ได้รับไม่สมบูรณ์ กรุณาอัปเดตข้อมูลอีกครั้ง",
    status,
    "INVALID_API_RESPONSE",
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw errorFromPayload(payload, response.status);
  }
  return dataFromPayload<T>(payload, response.status);
}

export function apiGet<T>(path: string) {
  return request<T>(path);
}

export function apiSend<T>(
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  body?: unknown,
) {
  return request<T>(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiUpload<T>(path: string, file: File) {
  const formData = new FormData();
  formData.set("image", file);
  return request<T>(path, { method: "POST", body: formData });
}

export function validationError(message: string) {
  return new DashboardApiError(message, 422, "VALIDATION_ERROR");
}
