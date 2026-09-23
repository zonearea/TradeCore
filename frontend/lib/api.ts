/**
 * TradeCore frontend API istemcisi.
 *
 * Mimari amaç:
 * - Tarayıcıdan doğrudan FastAPI'ye gitmek yerine Next.js `/api/backend/*` proxy'sini kullanır.
 * - Böylece HttpOnly çerezler (accessToken / refreshToken) güvenli şekilde taşınır.
 * - 401 gelirse bir kez refresh denenir; oturum yenilenirse asıl istek tekrarlanır.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5080";

/** API hatalarını UI'da okunabilir mesaja çevirmek için özel hata sınıfı. */
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
  detail?: string | { msg?: string }[];
};

export type CurrentUser = {
  id: string | null;
  email: string | null;
  firstName: string | null;
  lastName: string | null;
  role: string | null;
};

/** Portföydeki tek bir hisse satırı (backend camelCase döner). */
export type Holding = {
  id: string;
  symbol: string;
  companyName?: string;
  /** BIST | US */
  market?: string;
  /** TRY | USD — tutarlar bu para biriminde */
  currency: string;
  sharesCount: number;
  averageCost: number;
  currentPrice: number;
  totalCost: number;
  currentValue: number;
  profitLoss: number;
  profitLossPercentage: number;
  /** TRY karşılıkları (ABD hisselerinde gri alt satır) */
  averageCostTry?: number;
  currentPriceTry?: number;
  totalCostTry?: number;
  currentValueTry?: number;
  profitLossTry?: number;
  usdTryRate?: number | null;
  portfolioWeight?: number;
  /** Madde 3 — pandas-ta teknik özet */
  technical?: {
    rsi: number;
    signal: string;
    trend: string;
  };
};

/** BIST / ABD kırılımı (üst kart alt satırı). */
export type PortfolioBreakdown = {
  bistValueTry: number;
  bistCostTry: number;
  usValueUsd: number;
  usCostUsd: number;
  usValueTry: number;
  usCostTry: number;
  usdTryRate: number;
};

/** GET /api/portfolio özet yanıtı. total* alanları her zaman TRY. */
export type PortfolioSummary = {
  totalCost: number;
  totalValue: number;
  profitLoss: number;
  profitLossPercentage: number;
  usdTryRate?: number;
  breakdown?: PortfolioBreakdown;
  holdings: Holding[];
};

/** Gemini analiz raporu. */
export type AiReport = {
  id: string;
  title: string;
  executiveSummary: string;
  fullReportMarkdown: string;
  riskScore: number;
  recommendations: { symbol?: string; action?: string; note?: string }[];
  createdAtUtc: string;
};

/** Piyasa haber kartı (canlı RSS — BIST & KAP). */
export type MarketNewsItem = {
  id: string;
  /** Geriye dönük alan; canlı akışta genelde "BIST" */
  symbol?: string;
  title: string;
  summary: string;
  /** Kaynak adı: örn. "Bloomberg HT", "Google News BIST" */
  source?: string;
  /** Habere giden tıklanabilir URL */
  url?: string;
  sourceUrl?: string;
  sentiment: "Pozitif" | "Nötr" | "Negatif" | "Positive" | "Neutral" | "Negative" | string;
  publishedAt?: string;
  publishedAtUtc?: string;
};

/** Ekstre önizlemesinde yakalanan hisse satırı. */
export type StatementParsedLine = {
  symbol: string;
  sharesCount: number;
  averageCost: number;
  rawLine: string;
};

export type StatementPreview = {
  parsed: StatementParsedLine[];
  unparsed: string[];
  lineCount: number;
};

/**
 * FastAPI yolunu Next.js proxy yoluna çevirir.
 * Örn: `/api/portfolio` → `/api/backend/portfolio`
 */
function endpoint(path: string) {
  const suffix = path.replace(/^\/api/, "");
  return `/api/backend${suffix}`;
}

/** FastAPI `detail` alanını (string veya validation listesi) tek mesaja indirger. */
function readDetail(problem: ProblemBody | null): string {
  if (!problem?.detail) {
    return problem?.title || "İstek başarısız oldu.";
  }
  if (typeof problem.detail === "string") {
    return problem.detail;
  }
  return problem.detail.map((item) => item.msg || "Doğrulama hatası").join(" ");
}

/**
 * Ortak HTTP sarmalayıcı.
 * @param path Backend API yolu (`/api/...`)
 * @param init fetch seçenekleri; FormData gönderirken Content-Type elle set edilmez
 *             (tarayıcı boundary ekler).
 */
async function request<T>(path: string, init?: RequestInit, retry = true): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;

  const response = await fetch(endpoint(path), {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      // JSON gövdede Content-Type ekle; FormData'da ekleme ki multipart bozulmasın.
      ...(init?.body && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  // Access token süresi dolduysa refresh çerezi ile yenilemeyi dene.
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
    throw new ApiError(response.status, readDetail(problem));
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

/** Kullanıcının portföy özetini ve canlı fiyatlarla hisselerini getirir. */
export function getPortfolio() {
  return request<PortfolioSummary>("/api/portfolio");
}

/** Yeni hisse ekler veya aynı sembol varsa lotları ağırlıklı ortalama ile birleştirir. */
/** Hisse ekler; currency sekmeden gelir ('TRY' | 'USD'). */
export function addHolding(input: {
  symbol: string;
  sharesCount: number;
  averageCost: number;
  currency?: string;
}) {
  return request<Holding>("/api/portfolio/holdings", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Hisseyi portföyden çıkarır (backend POST .../remove kullanır; proxy DELETE taşımaz). */
export function removeHolding(id: string) {
  return request<void>(`/api/portfolio/holdings/${id}/remove`, { method: "POST" });
}

/** Gemini ile yeni portföy analizi üretir ve kaydeder. */
export function generateAnalysis() {
  return request<AiReport>("/api/analysis/generate", { method: "POST" });
}

/** Daha önce üretilmiş analiz raporlarını listeler (yeniden eskiye). */
export function getAnalysisReports() {
  return request<AiReport[]>("/api/analysis/reports");
}

/** Gemini haber açıklama yanıtı (akordeon kartı). */
export type NewsExplainResult = {
  summary: string;
  impact: string;
  verdict: string;
  /** Anahtar yok / hata — nazik uyarı metni */
  warning?: string;
};

/**
 * POST /api/market/news/explain — haber başlığı + özeti Gemini ile açıklar.
 * Yatırım tavsiyesi değildir; bilgilendirme amaçlıdır.
 */
export function explainMarketNews(input: { title: string; summary?: string; symbol?: string }) {
  return request<NewsExplainResult>("/api/market/news/explain", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * Canlı haberleri getirir.
 *
 * @param options.symbols Portföy sembolleri (örn. ["THYAO","NVDA"]) → Sadece Portföyüm
 * @param options.refresh true ise 5 dk sunucu önbelleğini aşar
 *
 * Örnek: GET /api/market/news?symbols=THYAO,NVDA&refresh=true
 */
export function getMarketNews(options?: { symbols?: string[]; refresh?: boolean } | string, refreshLegacy = false) {
  const params = new URLSearchParams();

  // Geriye dönük: getMarketNews("THYAO", true) çağrıları da çalışsın
  if (typeof options === "string") {
    if (options) params.set("symbol", options);
    if (refreshLegacy) params.set("refresh", "true");
  } else if (options) {
    const symbols = (options.symbols || []).map((s) => s.trim().toUpperCase()).filter(Boolean);
    if (symbols.length > 0) {
      params.set("symbols", symbols.join(","));
    }
    if (options.refresh) params.set("refresh", "true");
  }

  const query = params.toString() ? `?${params.toString()}` : "";
  return request<MarketNewsItem[]>(`/api/market/news${query}`);
}

/**
 * Banka/portföy PDF ekstresini sunucuya önizletir; veritabanına yazmaz.
 * @param file Kullanıcının seçtiği PDF dosyası
 */
export function previewStatement(file: File) {
  const form = new FormData();
  // Alan adı backend'deki `file: UploadFile = File(...)` ile aynı olmalı.
  form.append("file", file);
  return request<StatementPreview>("/api/portfolio/statements/preview", {
    method: "POST",
    body: form,
  });
}

/** Önizlemede kabul edilen satırları holding tablosuna işler. */
export function importStatement(holdings: { symbol: string; sharesCount: number; averageCost: number }[]) {
  return request<{ importedCount: number }>("/api/portfolio/statements/import", {
    method: "POST",
    body: JSON.stringify({ holdings }),
  });
}

/** Masaüstü üst çubuğu için SQLite / sistem durumu. */
export type SystemStatus = {
  status: string;
  mode: string;
  database: string;
  connected: boolean;
  databaseFile: string;
  owner: string;
};

/** Canlı piyasa şeridi kotasyonu. */
export type TickerQuote = {
  symbol: string;
  label: string;
  price: number;
  changePercent: number;
};

/** GET /api/system/status — Local-First bağlantı göstergesi. */
export function getSystemStatus() {
  return request<SystemStatus>("/api/system/status");
}

/** GET /api/market/ticker — BIST/FX/altın üst şerit. */
export function getMarketTicker() {
  return request<TickerQuote[]>("/api/market/ticker");
}

/** Tek sembol kotasyonu (çipler / hızlı ekleme). */
export type SymbolQuote = {
  symbol: string;
  companyName: string;
  market: string;
  currency: string;
  priceNative: number;
  /** Portföy/maliyet kutusu için TRY fiyat */
  priceTry: number;
  yahooSymbol: string;
  changePercent: number;
  usdTryRate?: number;
};

/** GET /api/market/quote?symbol=NVDA */
export function getSymbolQuote(symbol: string) {
  return request<SymbolQuote>(`/api/market/quote?symbol=${encodeURIComponent(symbol)}`);
}

export { API_URL };
