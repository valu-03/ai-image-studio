export type SubjectKind = "animal" | "human" | "object" | "place";

export interface CardOption {
  key: string;
  label: string;
  plain: string;
  example: string;
  look: Record<string, unknown>;
  kinds?: SubjectKind[];
}

export interface LookCard {
  id: string;
  title: string;
  plain: string;
  example: string;
  kinds?: SubjectKind[];
  options: CardOption[];
  advanced_part: string | null;
}

export interface LookSnapshot {
  kind: SubjectKind;
  cards: Record<string, string>;
  touched: string[];
}

export interface PriceEstimate {
  image: {
    credits: number | null;
    usd: number | null;
    confidence: string;
  };
  check: {
    usd: number;
    confidence: string;
  };
  label: string;
}

export interface GiveawayItem {
  key: string;
  label: string;
  plain: string;
  where: string;
  fixable: boolean;
}

export interface PhotoJob {
  state: "running" | "done" | "error";
  stage: string;
  error: string;
  file_url: string | null;
  history_id: string | null;
  giveaways: GiveawayItem[] | null;
  check_error: string;
}

export interface RecentPhoto {
  history_id: string;
  file_url: string;
  note: string;
  rating: number | null;
  source: "page" | "api";
}

export type KeyName =
  | "KIE_API_KEY"
  | "HIGGSFIELD_API_KEY_ID"
  | "HIGGSFIELD_API_KEY_SECRET"
  | "OPENROUTER_API_KEY";

export interface SettingsPayload {
  keys: Record<KeyName, boolean>;
  provider: "kie" | "higgsfield";
  local_api: {
    enabled: boolean;
    running: boolean;
    error: string;
  };
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.body ? { "Content-Type": "application/json" } : {}),
  };
  const res = await fetch(path, { ...init, headers });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const obj = (data && typeof data === "object" ? data : {}) as Record<string, unknown>;
    const msg =
      typeof obj.detail === "string"
        ? obj.detail
        : typeof obj.error === "string"
          ? obj.error
          : res.statusText || `HTTP ${res.status}`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export function getCards(kind: SubjectKind): Promise<LookCard[]> {
  return request<LookCard[]>(`/api/cards?kind=${encodeURIComponent(kind)}`);
}

export function describe(text: string): Promise<{ kind: SubjectKind }> {
  return request<{ kind: SubjectKind }>("/api/describe", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function getLook(): Promise<LookSnapshot> {
  return request<LookSnapshot>("/api/look");
}

export function setCard(card: string, option: string): Promise<LookSnapshot> {
  return request<LookSnapshot>("/api/look", {
    method: "PUT",
    body: JSON.stringify({ card, option }),
  });
}

export function getPrice(provider: string): Promise<PriceEstimate> {
  return request<PriceEstimate>(`/api/price?provider=${encodeURIComponent(provider)}`);
}

export function makePhoto(body: {
  text: string;
  provider?: string;
  reference_b64?: string;
  reference_name?: string;
}): Promise<{ id: string }> {
  return request<{ id: string }>("/api/photos", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getPhoto(id: string): Promise<PhotoJob> {
  return request<PhotoJob>(`/api/photos/${encodeURIComponent(id)}`);
}

export function fixPhoto(id: string, giveaway: string): Promise<{ id: string }> {
  return request<{ id: string }>(`/api/photos/${encodeURIComponent(id)}/fix`, {
    method: "POST",
    body: JSON.stringify({ giveaway }),
  });
}

export function ratePhoto(
  id: string,
  thumb: "up" | "down"
): Promise<{ history_id: string; rating: number }> {
  return request<{ history_id: string; rating: number }>(
    `/api/photos/${encodeURIComponent(id)}/rate`,
    {
      method: "POST",
      body: JSON.stringify({ thumb }),
    }
  );
}

export function getRecent(): Promise<RecentPhoto[]> {
  return request<RecentPhoto[]>("/api/recent");
}

export function checkRecent(
  historyId: string
): Promise<{ giveaways: GiveawayItem[] | null; check_error: string }> {
  return request<{ giveaways: GiveawayItem[] | null; check_error: string }>(
    `/api/recent/${encodeURIComponent(historyId)}/check`,
    { method: "POST" }
  );
}

export function getSettings(): Promise<SettingsPayload> {
  return request<SettingsPayload>("/api/settings");
}

export function setKey(
  name: KeyName,
  value: string
): Promise<{ name: KeyName; set: boolean }> {
  return request<{ name: KeyName; set: boolean }>("/api/settings/key", {
    method: "PUT",
    body: JSON.stringify({ name, value }),
  });
}

export function setSettings(patch: {
  provider?: "kie" | "higgsfield";
  local_api_enabled?: boolean;
}): Promise<SettingsPayload> {
  return request<SettingsPayload>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}
