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
