/** 백엔드 API 공통 호출. 주소는 NEXT_PUBLIC_API_URL, 없으면 http://localhost:8000 */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

/** GET 요청 후 JSON을 돌려줌. 연결 실패나 2xx가 아닌 응답이면 ApiError를 던짐. */
export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, method: "GET", headers: { Accept: "application/json", ...init?.headers } });
  } catch (error) {
    throw new ApiError(`GET ${path} 연결 실패: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!response.ok) throw new ApiError(`GET ${path} 실패 (${response.status})`, response.status);
  return response.json() as Promise<T>;
}

/** POST 요청(JSON 본문) 후 JSON을 돌려줌. 2xx가 아니면 서버의 detail 문구를 담아 ApiError를 던짐. */
export async function apiPost<T>(path: string, body?: unknown, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers }, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (error) {
    throw new ApiError(`POST ${path} 연결 실패: ${error instanceof Error ? error.message : String(error)}`);
  }
  if (!response.ok) {
    let detail: unknown;
    try { detail = ((await response.json()) as { detail?: unknown })?.detail; } catch { detail = undefined; }
    throw new ApiError(typeof detail === "string" && detail ? detail : `POST ${path} 실패 (${response.status})`, response.status);
  }
  return response.json() as Promise<T>;
}
