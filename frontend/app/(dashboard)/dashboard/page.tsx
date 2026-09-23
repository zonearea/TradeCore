"use client";

/**
 * TradeCore Terminal — OLED / Bloomberg estetiğinde sekmeli masaüstü kokpit.
 *
 * Renk sözleşmesi:
 * - Arka plan: #09090b
 * - Kart / panel: #121215
 * - Kenarlık: zinc-800
 * - Pozitif: emerald-400 · Negatif: rose-400 · Mono rakamlar: font-mono
 */

import { useCallback, useEffect, useState, type Dispatch, type FormEvent, type ReactNode, type SetStateAction } from "react";
import { MarkdownView } from "@/components/markdown-view";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ApiError,
  addHolding,
  generateAnalysis,
  getAnalysisReports,
  getMarketNews,
  getMarketTicker,
  getPortfolio,
  getSymbolQuote,
  getSystemStatus,
  explainMarketNews,
  importStatement,
  previewStatement,
  removeHolding,
  type AiReport,
  type MarketNewsItem,
  type NewsExplainResult,
  type PortfolioSummary,
  type StatementPreview,
  type SystemStatus,
  type TickerQuote,
} from "@/lib/api";
import { formatApproxTry, formatMoney, formatNumber, formatPercent, formatSignedMoney, formatTry, formatUsd, pnlTone } from "@/lib/format";

type DesktopTab = "portfolio" | "ai" | "statements" | "news";

/** Hızlı ekle / tahta: Borsa İstanbul mı, ABD mi? */
type MarketBoard = "BIST" | "US";

type HoldingForm = {
  symbol: string;
  sharesCount: string;
  averageCost: string;
};

const emptyForm: HoldingForm = { symbol: "", sharesCount: "", averageCost: "" };

const TABS: { id: DesktopTab; label: string }[] = [
  { id: "portfolio", label: "Portföy & Tahta" },
  { id: "ai", label: "AI Analisti" },
  { id: "statements", label: "Ekstre & Harcamalar" },
  { id: "news", label: "BIST & KAP Akışı" },
];

export default function DashboardPage() {
  const [tab, setTab] = useState<DesktopTab>("portfolio");
  const [pageError, setPageError] = useState<string | null>(null);

  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [ticker, setTicker] = useState<TickerQuote[]>([]);

  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [portfolioLoading, setPortfolioLoading] = useState(true);
  const [holdingForm, setHoldingForm] = useState<HoldingForm>(emptyForm);
  const [holdingPending, setHoldingPending] = useState(false);
  const [chipPending, setChipPending] = useState(false);
  /** Portföy sekmesi borsa ayrımı: BIST (₺) | US ($) */
  const [marketBoard, setMarketBoard] = useState<MarketBoard>("BIST");

  /**
   * Otomatik fiyat tazeleme (Auto-Refresh).
   * Açıkken her 45 sn portföy + üst şerit sessizce yenilenir.
   * localStorage ile tercih hatırlanır.
   */
  const [autoRefresh, setAutoRefresh] = useState(true);
  /** Son başarılı otomatik nabız zamanı (Canlı göstergesi için) */
  const [livePulseAt, setLivePulseAt] = useState<number | null>(null);

  const [report, setReport] = useState<AiReport | null>(null);
  const [analysisPending, setAnalysisPending] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  const [dragOver, setDragOver] = useState(false);
  const [statementPending, setStatementPending] = useState(false);
  const [statementPreview, setStatementPreview] = useState<StatementPreview | null>(null);
  const [statementMessage, setStatementMessage] = useState<string | null>(null);

  const [news, setNews] = useState<MarketNewsItem[]>([]);
  const [newsLoading, setNewsLoading] = useState(true);
  /** Haber sekmesi: genel piyasa mı, yoksa yalnızca portföy hisseleri mi? */
  const [newsScope, setNewsScope] = useState<"market" | "portfolio">("market");

  const loadPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    try {
      setPortfolio(await getPortfolio());
    } catch (caught) {
      setPageError(caught instanceof ApiError ? caught.message : "Portföy alınamadı.");
    } finally {
      setPortfolioLoading(false);
    }
  }, []);

  /**
   * Arka plan tazeleme — loading spinner / hata bandı yok.
   * Otomatik döngü UI'yi titretmesin diye ayrı tutulur.
   */
  const refreshPortfolioSilent = useCallback(async () => {
    try {
      setPortfolio(await getPortfolio());
    } catch {
      // Sessiz: otomatik döngüde kırmızı banner basma
    }
  }, []);

  const loadLatestReport = useCallback(async () => {
    try {
      const reports = await getAnalysisReports();
      setReport(reports[0] ?? null);
    } catch {
      setReport(null);
    }
  }, []);

  /**
   * Haberleri yükler.
   * - market → genel BIST/KAP
   * - portfolio → GET /news?symbols=GARAN,NVDA… (tahtadaki hisseler)
   *
   * scope parametresi verilmezse o anki newsScope kullanılır.
   */
  const loadNews = useCallback(
    async (forceRefresh = false, scopeOverride?: "market" | "portfolio") => {
      const scope = scopeOverride ?? newsScope;
      setNewsLoading(true);
      try {
        if (scope === "portfolio") {
          // Portföy state boşsa API'den bir kez çek (sekme geçişinde)
          let holdings = portfolio?.holdings;
          if (!holdings) {
            holdings = (await getPortfolio()).holdings;
          }
          const symbols = holdings.map((h) => h.symbol).filter(Boolean);
          if (symbols.length === 0) {
            setNews([]);
            setPageError(null);
            return;
          }
          setNews(await getMarketNews({ symbols, refresh: forceRefresh }));
        } else {
          setNews(await getMarketNews({ refresh: forceRefresh }));
        }
        setPageError(null);
      } catch (caught) {
        setPageError(caught instanceof ApiError ? caught.message : "Haberler alınamadı.");
      } finally {
        setNewsLoading(false);
      }
    },
    [newsScope, portfolio],
  );

  const loadSystem = useCallback(async () => {
    try {
      setSystem(await getSystemStatus());
    } catch {
      setSystem(null);
    }
  }, []);

  /** Üst ticker şeridini yeniler (yfinance gecikmeli olabilir). */
  const loadTicker = useCallback(async () => {
    try {
      setTicker(await getMarketTicker());
    } catch {
      setTicker([]);
    }
  }, []);

  useEffect(() => {
    // İlk açılış: genel piyasa haberleri (Tüm Piyasa)
    void Promise.all([loadSystem(), loadTicker(), loadPortfolio(), loadLatestReport(), loadNews(false, "market")]);
    // loadNews kasıtlı olarak bağımlılığa alınmadı — her portfolio değişiminde yeniden çekmesin
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadLatestReport, loadPortfolio, loadSystem, loadTicker]);

  /**
   * Auto-Refresh döngüsü (45 sn).
   * - Yalnızca anahtar açıksa ve tarayıcı sekmesi görünürken çalışır
   *   (arka plan sekmesinde gereksiz yfinance / API yükü yok).
   * - Portföy + üst piyasa şeridi sessizce tazelenir.
   */
  useEffect(() => {
    if (!autoRefresh) return;

    const AUTO_MS = 45_000;

    async function beat() {
      // Sekme gizliyse nabız atlama — kullanıcı geri gelince sonraki tick alır
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        return;
      }
      await Promise.all([refreshPortfolioSilent(), loadTicker()]);
      setLivePulseAt(Date.now());
    }

    // İlk nabız: açılıştan kısa sonra (ilk yükleme ile çakışmasın diye 2 sn)
    const warm = window.setTimeout(() => void beat(), 2_000);
    const timer = window.setInterval(() => void beat(), AUTO_MS);
    return () => {
      window.clearTimeout(warm);
      window.clearInterval(timer);
    };
  }, [autoRefresh, loadTicker, refreshPortfolioSilent]);

  /** Filtre butonu: Tüm Piyasa ↔ Sadece Portföyüm */
  function onNewsScopeChange(next: "market" | "portfolio") {
    setNewsScope(next);
    void loadNews(true, next);
  }

  /** Manuel yenile: portföy + şerit + nabız */
  function onManualRefresh() {
    void Promise.all([loadPortfolio(), loadTicker()]).then(() => setLivePulseAt(Date.now()));
  }

  async function onAddHolding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setHoldingPending(true);
    setPageError(null);
    try {
      const sharesCount = Number(holdingForm.sharesCount);
      const averageCost = Number(holdingForm.averageCost.replace(",", "."));
      if (!holdingForm.symbol.trim() || !Number.isFinite(sharesCount) || sharesCount <= 0) {
        throw new Error("Geçerli sembol ve pozitif lot girin.");
      }
      if (!Number.isFinite(averageCost) || averageCost <= 0) {
        throw new Error("Geçerli alış fiyatı girin.");
      }
      // Maliyet native: BIST→₺, ABD→$ (currency alanı backend'e ipucu)
      await addHolding({
        symbol: holdingForm.symbol.trim().toUpperCase(),
        sharesCount: Math.trunc(sharesCount),
        averageCost,
        currency: marketBoard === "US" ? "USD" : "TRY",
      });
      setHoldingForm(emptyForm);
      await loadPortfolio();
    } catch (caught) {
      setPageError(caught instanceof Error ? caught.message : "Hisse eklenemedi.");
    } finally {
      setHoldingPending(false);
    }
  }

  /**
   * Hızlı seçim çipi: sembolü forma yazar.
   * BIST → priceTry (₺) · ABD → priceNative ($) maliyet kutusuna önerilir.
   */
  async function onPickSymbolChip(symbol: string) {
    setChipPending(true);
    setPageError(null);
    setHoldingForm((prev) => ({ ...prev, symbol, sharesCount: prev.sharesCount || "1" }));
    try {
      const quote = await getSymbolQuote(symbol);
      // Kotasyona göre sekmeyi hizala (NVDA → ABD, THYAO → BIST)
      const board: MarketBoard = quote.currency === "USD" || quote.market === "GLOBAL" ? "US" : "BIST";
      setMarketBoard(board);
      const suggested =
        board === "US" ? quote.priceNative : quote.priceTry;
      setHoldingForm((prev) => ({
        ...prev,
        symbol: quote.symbol,
        averageCost: String(suggested).replace(".", ","),
        sharesCount: prev.sharesCount || "1",
      }));
    } catch (caught) {
      setPageError(caught instanceof ApiError ? caught.message : "Fiyat alınamadı.");
    } finally {
      setChipPending(false);
    }
  }

  async function onRemoveHolding(id: string) {
    try {
      await removeHolding(id);
      await loadPortfolio();
    } catch (caught) {
      setPageError(caught instanceof ApiError ? caught.message : "Hisse silinemedi.");
    }
  }

  async function onGenerateAnalysis() {
    setAnalysisPending(true);
    setAnalysisError(null);
    try {
      setReport(await generateAnalysis());
    } catch (caught) {
      setAnalysisError(caught instanceof ApiError ? caught.message : "Analiz üretilemedi.");
    } finally {
      setAnalysisPending(false);
    }
  }

  async function onStatementFile(file: File | null | undefined) {
    if (!file) return;
    setStatementPending(true);
    setStatementMessage(null);
    setStatementPreview(null);
    try {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        throw new Error("Şimdilik yalnızca PDF destekleniyor.");
      }
      const preview = await previewStatement(file);
      setStatementPreview(preview);
      if (preview.parsed.length === 0) {
        setStatementMessage("Okunabilir hisse satırı bulunamadı.");
      }
    } catch (caught) {
      setStatementMessage(caught instanceof Error ? caught.message : "Ekstre okunamadı.");
    } finally {
      setStatementPending(false);
    }
  }

  async function onImportParsed() {
    if (!statementPreview?.parsed.length) return;
    setStatementPending(true);
    try {
      const result = await importStatement(
        statementPreview.parsed.map((line) => ({
          symbol: line.symbol,
          sharesCount: line.sharesCount,
          averageCost: line.averageCost,
        })),
      );
      setStatementMessage(`${result.importedCount} satır portföye işlendi.`);
      setStatementPreview(null);
      await loadPortfolio();
    } catch (caught) {
      setStatementMessage(caught instanceof ApiError ? caught.message : "İçe aktarım başarısız.");
    } finally {
      setStatementPending(false);
    }
  }

  const pnl = portfolio?.profitLoss ?? 0;

  return (
    <main className="min-h-screen bg-[#09090b] text-zinc-100">
      {/* Üst bar: marka + SQLite durumu */}
      <header className="border-b border-zinc-800 bg-[#0c0c0f]">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded border border-zinc-700 bg-[#121215] font-mono text-[10px] tracking-widest text-emerald-400">
              TC
            </div>
            <div>
              <p className="font-mono text-sm tracking-wide text-zinc-100">TRADECORE TERMINAL</p>
              <p className="font-mono text-[10px] text-zinc-500">LOCAL-FIRST · {system?.owner ?? "Berkay"}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Canlı nabız + Oto: 45s anahtarı + manuel Yenile */}
            <LivePulse active={autoRefresh} lastBeatAt={livePulseAt} />
            <AutoRefreshSwitch
              enabled={autoRefresh}
              onToggle={() => setAutoRefresh((v) => !v)}
            />
            <Button
              type="button"
              variant="outline"
              className="h-7 border-zinc-700 bg-[#121215] text-xs text-zinc-300 hover:bg-zinc-900"
              onClick={onManualRefresh}
            >
              Yenile
            </Button>
            <div className="flex items-center gap-2 rounded border border-zinc-800 bg-[#121215] px-3 py-1 font-mono text-[11px] text-zinc-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {system?.connected ? `Bağlı — SQLite · ${system.databaseFile}` : "Bağlantı…"}
            </div>
          </div>
        </div>

        {/* Canlı piyasa şeridi */}
        <TickerTape quotes={ticker} />

        {/* Sekmeler */}
        <nav className="flex gap-0 overflow-x-auto border-t border-zinc-800 px-2" aria-label="Terminal sekmeleri">
          {TABS.map((item) => {
            const active = tab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setTab(item.id)}
                className={`border-b-2 px-4 py-2.5 font-mono text-xs tracking-wide transition-colors ${
                  active
                    ? "border-emerald-400 text-emerald-400"
                    : "border-transparent text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </nav>
      </header>

      <div className="px-4 py-4">
        {pageError ? (
          <p className="mb-3 rounded border border-rose-900/60 bg-rose-950/40 px-3 py-2 font-mono text-xs text-rose-300">
            {pageError}
          </p>
        ) : null}

        {tab === "portfolio" ? (
          <PortfolioTab
            portfolio={portfolio}
            loading={portfolioLoading}
            pnl={pnl}
            marketBoard={marketBoard}
            onMarketBoardChange={setMarketBoard}
            holdingForm={holdingForm}
            setHoldingForm={setHoldingForm}
            holdingPending={holdingPending}
            chipPending={chipPending}
            onAddHolding={onAddHolding}
            onPickSymbolChip={onPickSymbolChip}
            onRemoveHolding={onRemoveHolding}
            onRefresh={onManualRefresh}
          />
        ) : null}

        {tab === "ai" ? (
          <AiTab
            report={report}
            pending={analysisPending}
            error={analysisError}
            onGenerate={() => void onGenerateAnalysis()}
          />
        ) : null}

        {tab === "statements" ? (
          <StatementsTab
            dragOver={dragOver}
            setDragOver={setDragOver}
            pending={statementPending}
            preview={statementPreview}
            message={statementMessage}
            onFile={(file) => void onStatementFile(file)}
            onImport={() => void onImportParsed()}
          />
        ) : null}

        {tab === "news" ? (
          <NewsTab
            news={news}
            loading={newsLoading}
            scope={newsScope}
            portfolioEmpty={(portfolio?.holdings.length ?? 0) === 0}
            onScopeChange={onNewsScopeChange}
            onRefresh={() => void loadNews(true)}
          />
        ) : null}
      </div>
    </main>
  );
}

/* -------------------------------------------------------------------------- */
/* Alt bileşenler                                                              */
/* -------------------------------------------------------------------------- */

/** Yatay kompakt ticker — TradingView / Bloomberg şerit hissi. */
function TickerTape({ quotes }: { quotes: TickerQuote[] }) {
  if (quotes.length === 0) {
    return (
      <div className="border-t border-zinc-800 bg-[#09090b] px-4 py-1.5 font-mono text-[10px] text-zinc-600">
        Piyasa şeridi yükleniyor…
      </div>
    );
  }

  return (
    <div className="flex gap-0 overflow-x-auto border-t border-zinc-800 bg-[#09090b]">
      {quotes.map((q) => (
        <div
          key={q.symbol}
          className="flex min-w-fit items-center gap-2 border-r border-zinc-800 px-3 py-1.5 font-mono text-[11px]"
        >
          <span className="text-zinc-400">{q.symbol}</span>
          <span className="text-zinc-100">{formatNumber(q.price)}</span>
          <span className={pnlTone(q.changePercent)}>{formatPercent(q.changePercent)}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Yeşil yanıp sönen 'Canlı' nabız noktası.
 * Auto-Refresh açıkken pulse animasyonu; kapalıyken soluk gri.
 */
function LivePulse({ active, lastBeatAt }: { active: boolean; lastBeatAt: number | null }) {
  return (
    <div
      className="flex items-center gap-1.5 rounded border border-zinc-800 bg-[#121215] px-2.5 py-1 font-mono text-[10px]"
      title={lastBeatAt ? `Son nabız: ${new Date(lastBeatAt).toLocaleTimeString("tr-TR")}` : "Henüz nabız yok"}
    >
      <span className="relative flex h-2 w-2">
        {active ? (
          <>
            {/* Dış halka: yayılan nabız */}
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
          </>
        ) : (
          <span className="relative inline-flex h-2 w-2 rounded-full bg-zinc-600" />
        )}
      </span>
      <span className={active ? "text-emerald-400" : "text-zinc-600"}>{active ? "Canlı" : "Durdu"}</span>
    </div>
  );
}

/**
 * Otomatik yenileme anahtarı: Oto: 45s [Açık/Kapalı]
 * Tıklanınca autoRefresh state tersine döner.
 */
function AutoRefreshSwitch({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`flex items-center gap-2 rounded border px-2.5 py-1 font-mono text-[10px] transition-colors ${
        enabled
          ? "border-emerald-800/80 bg-emerald-950/30 text-emerald-300"
          : "border-zinc-700 bg-[#121215] text-zinc-500 hover:text-zinc-300"
      }`}
      aria-pressed={enabled}
      title="Her 45 saniyede portföy ve piyasa şeridini otomatik yenile"
    >
      <span>Oto: 45s</span>
      <span
        className={`rounded px-1.5 py-0.5 text-[9px] tracking-wide ${
          enabled ? "bg-emerald-500/20 text-emerald-300" : "bg-zinc-800 text-zinc-500"
        }`}
      >
        {enabled ? "Açık" : "Kapalı"}
      </span>
    </button>
  );
}

/** Tek tıkla seçilebilen popüler BIST / ABD semboller (sekmeye göre filtrelenir). */
const BIST_CHIPS = ["THYAO", "ASELS", "GARAN", "EREGL", "TUPRS", "SISE"] as const;
const US_CHIPS = ["NVDA", "AAPL", "MSFT", "TSLA"] as const;

function PortfolioTab({
  portfolio,
  loading,
  pnl,
  marketBoard,
  onMarketBoardChange,
  holdingForm,
  setHoldingForm,
  holdingPending,
  chipPending,
  onAddHolding,
  onPickSymbolChip,
  onRemoveHolding,
  onRefresh,
}: {
  portfolio: PortfolioSummary | null;
  loading: boolean;
  pnl: number;
  marketBoard: MarketBoard;
  onMarketBoardChange: (board: MarketBoard) => void;
  holdingForm: HoldingForm;
  setHoldingForm: Dispatch<SetStateAction<HoldingForm>>;
  holdingPending: boolean;
  chipPending: boolean;
  onAddHolding: (event: FormEvent<HTMLFormElement>) => void;
  onPickSymbolChip: (symbol: string) => void;
  onRemoveHolding: (id: string) => void;
  onRefresh: () => void;
}) {
  const isUs = marketBoard === "US";
  const chips = isUs ? US_CHIPS : BIST_CHIPS;
  const costLabel = isUs ? "Maliyet ($ USD)" : "Maliyet (₺ TRY)";
  const costPlaceholder = isUs ? "225.50" : "280,50";

  // Tahtayı seçili borsaya göre filtrele
  const visibleHoldings = (portfolio?.holdings ?? []).filter((h) =>
    isUs ? h.currency === "USD" || h.market === "US" : h.currency !== "USD" && h.market !== "US",
  );

  const breakdown = portfolio?.breakdown;

  return (
    <div className="space-y-4">
      {/* Özet kartlar — toplam TRY + borsa kırılımı */}
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded border border-zinc-800 bg-[#121215] px-3 py-3">
          <p className="font-mono text-[10px] tracking-widest text-zinc-500 uppercase">Toplam Varlık</p>
          <p className="mt-1 font-mono text-xl tabular-nums text-zinc-50">
            {loading ? "—" : formatTry(portfolio?.totalValue)}
          </p>
          {!loading && breakdown ? (
            <p className="mt-1 font-mono text-[10px] text-zinc-500">
              ₺ BIST: {formatTry(breakdown.bistValueTry)}
              {" · "}
              $ ABD: {formatUsd(breakdown.usValueUsd)}
              <span className="text-zinc-600"> ({formatApproxTry(breakdown.usValueTry)})</span>
            </p>
          ) : null}
        </div>
        <Metric
          label="Günlük K/Z"
          value={loading ? "—" : formatTry(pnl)}
          valueClassName={pnlTone(pnl)}
          hint="Toplam gerçekleşmemiş K/Z (TRY)"
        />
        <Metric
          label="Toplam Getiri"
          value={loading ? "—" : formatPercent(portfolio?.profitLossPercentage)}
          valueClassName={pnlTone(portfolio?.profitLossPercentage ?? 0)}
        />
      </div>

      {/* Borsa ayrımı: BIST ⇄ ABD — hem ekleme hem tahta için ortak */}
      <MarketBoardToggle board={marketBoard} onChange={onMarketBoardChange} />

      {/* Hızlı hisse ekleme */}
      <Panel
        title={isUs ? "Hızlı Hisse Ekle · ABD ($)" : "Hızlı Hisse Ekle · BIST (₺)"}
        action={
          <Button type="button" variant="outline" className="h-7 border-zinc-700 bg-transparent text-xs text-zinc-300" onClick={onRefresh}>
            Yenile
          </Button>
        }
      >
        <div className="mb-3 space-y-2">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 font-mono text-[10px] tracking-wide text-zinc-500">
              {isUs ? "ABD" : "BIST"}
            </span>
            {chips.map((sym) => (
              <SymbolChip
                key={sym}
                symbol={sym}
                active={holdingForm.symbol.toUpperCase() === sym}
                disabled={chipPending}
                tone={isUs ? "global" : "bist"}
                onClick={() => onPickSymbolChip(sym)}
              />
            ))}
          </div>
          {chipPending ? (
            <p className="font-mono text-[10px] text-zinc-500">Canlı fiyat alınıyor…</p>
          ) : (
            <p className="font-mono text-[10px] text-zinc-600">
              {isUs
                ? "Çipe tıkla → sembol + $ maliyet önerilir. Kâr/zarar dolar üzerinden hesaplanır."
                : "Çipe tıkla → sembol + ₺ maliyet önerilir. Kâr/zarar TL üzerinden hesaplanır."}
            </p>
          )}
        </div>

        <form onSubmit={onAddHolding} className="grid gap-2 sm:grid-cols-4">
          <DarkField label="Sembol">
            <Input
              className="h-8 border-zinc-800 bg-[#09090b] font-mono text-xs text-zinc-100"
              placeholder={isUs ? "NVDA" : "THYAO"}
              value={holdingForm.symbol}
              onChange={(e) => setHoldingForm((p) => ({ ...p, symbol: e.target.value }))}
              required
            />
          </DarkField>
          <DarkField label="Lot">
            <Input
              className="h-8 border-zinc-800 bg-[#09090b] font-mono text-xs text-zinc-100"
              type="number"
              min={1}
              value={holdingForm.sharesCount}
              onChange={(e) => setHoldingForm((p) => ({ ...p, sharesCount: e.target.value }))}
              required
            />
          </DarkField>
          <DarkField label={costLabel}>
            <Input
              className="h-8 border-zinc-800 bg-[#09090b] font-mono text-xs text-zinc-100"
              placeholder={costPlaceholder}
              value={holdingForm.averageCost}
              onChange={(e) => setHoldingForm((p) => ({ ...p, averageCost: e.target.value }))}
              required
            />
          </DarkField>
          <div className="flex items-end">
            <Button type="submit" className="h-8 w-full bg-emerald-600 text-xs hover:bg-emerald-500" disabled={holdingPending}>
              {holdingPending ? "…" : "Ekle"}
            </Button>
          </div>
        </form>
      </Panel>

      {/* Veri yoğun portföy tablosu — native para birimi + TRY alt satır */}
      <Panel title={isUs ? "Portföy Tahtası · ABD ($)" : "Portföy Tahtası · BIST (₺)"}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left font-mono text-[11px]">
            <thead className="border-b border-zinc-800 text-zinc-500">
              <tr>
                <th className="px-2 py-2 font-medium">Sembol</th>
                <th className="px-2 py-2 font-medium">Şirket</th>
                <th className="px-2 py-2 font-medium">Lot</th>
                <th className="px-2 py-2 font-medium">{isUs ? "Ort. Maliyet ($)" : "Ort. Maliyet (₺)"}</th>
                <th className="px-2 py-2 font-medium">{isUs ? "Canlı Fiyat ($)" : "Canlı Fiyat (₺)"}</th>
                <th className="px-2 py-2 font-medium">Teknik Durum</th>
                <th className="px-2 py-2 font-medium">Portföy %</th>
                <th className="px-2 py-2 font-medium">Kâr/Zarar</th>
                <th className="px-2 py-2" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-2 py-6 text-zinc-600">
                    Yükleniyor…
                  </td>
                </tr>
              ) : null}
              {!loading && visibleHoldings.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-2 py-6 text-zinc-600">
                    {isUs ? "ABD portföyü boş. Yukarıdan NVDA vb. ekle." : "BIST portföyü boş."}
                  </td>
                </tr>
              ) : null}
              {visibleHoldings.map((h) => {
                const cur = h.currency === "USD" ? "USD" : "TRY";
                const tech = h.technical;
                const trendUp = (tech?.trend || "").startsWith("Yüks");
                return (
                  <tr key={h.id} className="border-t border-zinc-800/80 hover:bg-zinc-900/40">
                    <td className="px-2 py-2 font-semibold text-zinc-100">
                      {h.symbol}
                      <span className="ml-1 text-[9px] font-normal text-zinc-600">{cur}</span>
                    </td>
                    <td className="px-2 py-2 text-zinc-400">{h.companyName ?? "—"}</td>
                    <td className="px-2 py-2 text-zinc-200">{h.sharesCount}</td>
                    <td className="px-2 py-2 text-zinc-200">
                      <div>{formatMoney(h.averageCost, cur)}</div>
                      {cur === "USD" ? (
                        <div className="text-[10px] text-zinc-600">{formatApproxTry(h.averageCostTry)}</div>
                      ) : null}
                    </td>
                    <td className="px-2 py-2 text-zinc-100">
                      <div>{formatMoney(h.currentPrice, cur)}</div>
                      {cur === "USD" ? (
                        <div className="text-[10px] text-zinc-600">{formatApproxTry(h.currentPriceTry)}</div>
                      ) : null}
                    </td>
                    {/* Madde 3: RSI rozeti + trend oku */}
                    <td className="px-2 py-2">
                      {tech ? (
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="rounded border border-zinc-700 bg-[#09090b] px-1.5 py-0.5 text-[10px] text-zinc-300">
                            RSI: {formatNumber(tech.rsi, 1)} ({tech.signal})
                          </span>
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] ${
                              trendUp
                                ? "border-emerald-800/80 text-emerald-400"
                                : "border-rose-900/60 text-rose-400"
                            }`}
                          >
                            {trendUp ? "↗" : "↘"} {tech.trend}
                          </span>
                        </div>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2 text-zinc-300">{formatNumber(h.portfolioWeight ?? 0)}%</td>
                    <td className={`px-2 py-2 ${pnlTone(h.profitLoss)}`}>
                      <div>
                        {formatSignedMoney(h.profitLoss, cur)}{" "}
                        <span className="opacity-80">({formatPercent(h.profitLossPercentage)})</span>
                      </div>
                      {cur === "USD" ? (
                        <div className="text-[10px] text-zinc-600">{formatApproxTry(h.profitLossTry)}</div>
                      ) : null}
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button
                        type="button"
                        className="text-rose-400 hover:text-rose-300"
                        onClick={() => onRemoveHolding(h.id)}
                      >
                        Sil
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {portfolio?.usdTryRate ? (
          <p className="mt-2 font-mono text-[10px] text-zinc-600">
            Güncel USD/TRY: {formatNumber(portfolio.usdTryRate, 4)} — ABD satırlarının ~₺ karşılığı bu kurla hesaplanır.
          </p>
        ) : null}
      </Panel>
    </div>
  );
}

/** BIST / ABD geçiş sekmeleri (bayrak + para birimi etiketi). */
function MarketBoardToggle({
  board,
  onChange,
}: {
  board: MarketBoard;
  onChange: (board: MarketBoard) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="tablist" aria-label="Borsa seçimi">
      <button
        type="button"
        role="tab"
        aria-selected={board === "BIST"}
        onClick={() => onChange("BIST")}
        className={`rounded border px-3 py-1.5 font-mono text-xs transition-colors ${
          board === "BIST"
            ? "border-emerald-500 bg-emerald-950/40 text-emerald-300"
            : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
        }`}
      >
        🇹🇷 Borsa İstanbul (TRY · ₺)
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={board === "US"}
        onClick={() => onChange("US")}
        className={`rounded border px-3 py-1.5 font-mono text-xs transition-colors ${
          board === "US"
            ? "border-sky-500 bg-sky-950/40 text-sky-300"
            : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
        }`}
      >
        🇺🇸 Amerikan Borsası (USD · $)
      </button>
    </div>
  );
}

/** Kompakt sembol seçim rozeti (chip). */
function SymbolChip({
  symbol,
  active,
  disabled,
  tone = "bist",
  onClick,
}: {
  symbol: string;
  active?: boolean;
  disabled?: boolean;
  tone?: "bist" | "global";
  onClick: () => void;
}) {
  const base =
    tone === "global"
      ? "border-sky-800/80 text-sky-300 hover:border-sky-500 hover:text-sky-200"
      : "border-zinc-700 text-zinc-300 hover:border-emerald-600 hover:text-emerald-300";
  const activeCls =
    tone === "global"
      ? "border-sky-500 bg-sky-950/40 text-sky-200"
      : "border-emerald-500 bg-emerald-950/30 text-emerald-300";

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded border px-2 py-0.5 font-mono text-[11px] transition-colors disabled:opacity-40 ${
        active ? activeCls : base
      }`}
    >
      {symbol}
    </button>
  );
}

/** Haber sekmesi filtre rozeti: Tüm Piyasa / Sadece Portföyüm. */
function FilterChip({
  label,
  active,
  disabled,
  onClick,
}: {
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded border px-2.5 py-1 font-mono text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        active
          ? "border-emerald-500 bg-emerald-950/40 text-emerald-300"
          : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
      }`}
    >
      {label}
    </button>
  );
}

function AiTab({
  report,
  pending,
  error,
  onGenerate,
}: {
  report: AiReport | null;
  pending: boolean;
  error: string | null;
  onGenerate: () => void;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
      <Panel title="Risk">
        <div className="space-y-4">
          <div className="rounded border border-zinc-800 bg-[#09090b] p-4 text-center">
            <p className="font-mono text-[10px] tracking-widest text-zinc-500">SCORE</p>
            <p className={`mt-2 font-mono text-4xl ${pnlTone((report?.riskScore ?? 5) - 5)}`}>
              {report?.riskScore ?? "—"}
            </p>
            <p className="font-mono text-[10px] text-zinc-600">/ 10</p>
          </div>
          <Button
            type="button"
            className="w-full bg-emerald-600 text-xs hover:bg-emerald-500"
            onClick={onGenerate}
            disabled={pending}
          >
            {pending ? "Analiz…" : "Portföyümü Analiz Et"}
          </Button>
          {error ? <p className="font-mono text-[11px] text-amber-400">{error}</p> : null}
        </div>
      </Panel>
      <Panel title={report?.title ?? "Gemini Raporu"}>
        {report ? (
          <div className="min-h-[420px] rounded border border-zinc-800 bg-[#09090b] p-4">
            <p className="mb-3 font-mono text-xs text-zinc-400">{report.executiveSummary}</p>
            <MarkdownView content={report.fullReportMarkdown} />
          </div>
        ) : (
          <p className="rounded border border-dashed border-zinc-800 px-4 py-16 text-center font-mono text-xs text-zinc-600">
            Rapor yok. Analizi başlatın.
          </p>
        )}
      </Panel>
    </div>
  );
}

function StatementsTab({
  dragOver,
  setDragOver,
  pending,
  preview,
  message,
  onFile,
  onImport,
}: {
  dragOver: boolean;
  setDragOver: (v: boolean) => void;
  pending: boolean;
  preview: StatementPreview | null;
  message: string | null;
  onFile: (file: File | null | undefined) => void;
  onImport: () => void;
}) {
  return (
    <Panel title="PDF Ekstre">
      <div
        className={`mb-4 rounded border-2 border-dashed px-4 py-12 text-center transition-colors ${
          dragOver ? "border-emerald-500 bg-emerald-950/20" : "border-zinc-800 bg-[#09090b]"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          onFile(e.dataTransfer.files?.[0]);
        }}
      >
        <p className="mb-3 font-mono text-xs text-zinc-500">PDF sürükle-bırak veya seç</p>
        <Input
          type="file"
          accept=".pdf,application/pdf"
          className="mx-auto max-w-xs cursor-pointer border-zinc-800 bg-[#121215] text-xs text-zinc-300"
          disabled={pending}
          onChange={(e) => onFile(e.target.files?.[0])}
        />
      </div>
      {pending ? <p className="mb-2 font-mono text-xs text-zinc-500">İşleniyor…</p> : null}
      {message ? <p className="mb-2 font-mono text-xs text-zinc-300">{message}</p> : null}
      {preview ? (
        <div className="space-y-3">
          <div className="overflow-x-auto rounded border border-zinc-800">
            <table className="w-full text-left font-mono text-[11px]">
              <thead className="border-b border-zinc-800 text-zinc-500">
                <tr>
                  <th className="px-2 py-2">Sembol</th>
                  <th className="px-2 py-2">Lot</th>
                  <th className="px-2 py-2">Maliyet</th>
                  <th className="px-2 py-2">Ham</th>
                </tr>
              </thead>
              <tbody>
                {preview.parsed.map((line) => (
                  <tr key={`${line.symbol}-${line.rawLine}`} className="border-t border-zinc-800/80">
                    <td className="px-2 py-2 text-zinc-100">{line.symbol}</td>
                    <td className="px-2 py-2">{line.sharesCount}</td>
                    <td className="px-2 py-2">{formatTry(line.averageCost)}</td>
                    <td className="px-2 py-2 text-zinc-500">{line.rawLine}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button
            type="button"
            className="bg-emerald-600 text-xs hover:bg-emerald-500"
            onClick={onImport}
            disabled={pending || preview.parsed.length === 0}
          >
            Portföye Aktar
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}

function NewsTab({
  news,
  loading,
  scope,
  portfolioEmpty,
  onScopeChange,
  onRefresh,
}: {
  news: MarketNewsItem[];
  loading: boolean;
  /** market = Tüm Piyasa · portfolio = Sadece Portföyüm */
  scope: "market" | "portfolio";
  portfolioEmpty: boolean;
  onScopeChange: (next: "market" | "portfolio") => void;
  onRefresh: () => void;
}) {
  return (
    <Panel
      title="BIST & KAP Akışı"
      action={
        <Button type="button" variant="outline" className="h-7 border-zinc-700 bg-transparent text-xs text-zinc-300" onClick={onRefresh}>
          Yenile
        </Button>
      }
    >
      {/* Filtre: genel piyasa vs portföy hisselerine özel Google/Yahoo haberleri */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <FilterChip label="Tüm Piyasa" active={scope === "market"} onClick={() => onScopeChange("market")} />
        <FilterChip
          label="Sadece Portföyüm"
          active={scope === "portfolio"}
          onClick={() => onScopeChange("portfolio")}
          disabled={portfolioEmpty}
        />
        <span className="font-mono text-[10px] text-zinc-600">
          {scope === "portfolio"
            ? "Tahtadaki hisseler için Google News + Yahoo Finance"
            : "Bloomberg HT + Google News BIST"}
        </span>
      </div>

      {loading ? <p className="font-mono text-xs text-zinc-600">Yükleniyor…</p> : null}
      {!loading && scope === "portfolio" && portfolioEmpty ? (
        <p className="font-mono text-xs text-zinc-600">
          Portföyünde hisse yok. Önce Portföy sekmesinden hisse ekle, sonra buraya dön.
        </p>
      ) : null}
      {!loading && news.length === 0 && !(scope === "portfolio" && portfolioEmpty) ? (
        <p className="font-mono text-xs text-zinc-600">Canlı haber alınamadı. Yenile’yi deneyin.</p>
      ) : null}
      <ul className="divide-y divide-zinc-800">
        {news.map((item) => (
          <NewsCard key={item.id} item={item} />
        ))}
      </ul>
    </Panel>
  );
}

/**
 * Tek haber satırı + 'AI ile Açıkla' akordeonu.
 * Her kart kendi explain state'ini tutar (komşu kartlar birbirini etkilemez).
 */
function NewsCard({ item }: { item: MarketNewsItem }) {
  const href = item.url || item.sourceUrl || "";
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<NewsExplainResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onExplain() {
    // Zaten açık ve sonuç varsa sadece kapat/aç (tekrar API çağırma)
    if (open && result) {
      setOpen(false);
      return;
    }
    setOpen(true);
    if (result) return;

    setPending(true);
    setError(null);
    try {
      const explained = await explainMarketNews({
        title: item.title,
        summary: item.summary || item.title,
        symbol: item.symbol,
      });
      setResult(explained);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "AI açıklama alınamadı.");
    } finally {
      setPending(false);
    }
  }

  return (
    <li className="py-3">
      <div className="flex flex-wrap items-start gap-3">
        {/* Portföy modunda sembol rozeti (NVDA / THYAO); genel akışta kaynak adı */}
        <span className="rounded border border-zinc-800 bg-[#09090b] px-1.5 py-0.5 font-mono text-[10px] text-zinc-300">
          {item.symbol && item.symbol !== "BIST" ? item.symbol : item.source || "BIST"}
        </span>
        <SentimentBadge sentiment={item.sentiment} />
        <div className="min-w-0 flex-1">
          {href ? (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-zinc-100 underline-offset-2 hover:text-emerald-400 hover:underline"
            >
              {item.title}
            </a>
          ) : (
            <p className="text-sm text-zinc-100">{item.title}</p>
          )}
          {item.summary ? <p className="mt-0.5 text-xs text-zinc-500">{item.summary}</p> : null}
          {item.publishedAtUtc || item.publishedAt ? (
            <p className="mt-1 font-mono text-[10px] text-zinc-600">{item.publishedAtUtc || item.publishedAt}</p>
          ) : null}

          {/* AI ile Açıkla — Gemini haber özeti / etki / çıkarım */}
          <button
            type="button"
            onClick={() => void onExplain()}
            disabled={pending}
            className="mt-2 rounded border border-amber-800/50 bg-amber-950/20 px-2 py-0.5 font-mono text-[10px] text-amber-300 transition-colors hover:border-amber-600 hover:text-amber-200 disabled:opacity-50"
          >
            ⚡ AI ile Açıkla
          </button>

          {open ? (
            <div className="mt-2 overflow-hidden rounded border border-zinc-800 bg-[#0a0a0c]">
              {pending ? (
                // Skeleton / yükleme durumu
                <div className="space-y-2 p-3" aria-busy="true" aria-label="Analiz ediliyor">
                  <p className="font-mono text-[10px] text-zinc-500">Analiz ediliyor…</p>
                  <div className="h-2 w-[75%] animate-pulse rounded bg-zinc-800" />
                  <div className="h-2 w-full animate-pulse rounded bg-zinc-800" />
                  <div className="h-2 w-[66%] animate-pulse rounded bg-zinc-800" />
                </div>
              ) : null}

              {!pending && error ? (
                <p className="p-3 font-mono text-xs text-rose-400">{error}</p>
              ) : null}

              {!pending && result ? (
                <div className="space-y-2.5 p-3 text-xs leading-relaxed text-zinc-300">
                  {result.warning ? (
                    <p className="font-mono text-[10px] text-amber-500/90">⚠ {result.warning}</p>
                  ) : null}
                  <div>
                    <p className="mb-0.5 font-mono text-[10px] tracking-wide text-zinc-500">📌 Özet</p>
                    <p className="text-zinc-200">{result.summary}</p>
                  </div>
                  <div>
                    <p className="mb-0.5 font-mono text-[10px] tracking-wide text-zinc-500">💡 Hisseye Etkisi</p>
                    <p className={impactTone(result.impact)}>{result.impact}</p>
                  </div>
                  <div>
                    <p className="mb-0.5 font-mono text-[10px] tracking-wide text-zinc-500">🎯 Kritik Çıkarım</p>
                    <p className="text-zinc-200">{result.verdict}</p>
                  </div>
                  <p className="font-mono text-[9px] text-zinc-600">
                    Bilgilendirme amaçlıdır; yatırım tavsiyesi değildir.
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/** Impact metninin başına göre renk (Olumlu / Olumsuz / Nötr). */
function impactTone(impact: string): string {
  const lower = impact.toLowerCase();
  if (lower.startsWith("olumlu") || lower.includes("pozitif")) return "text-emerald-400";
  if (lower.startsWith("olumsuz") || lower.includes("negatif")) return "text-rose-400";
  return "text-zinc-300";
}

function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded border border-zinc-800 bg-[#121215]">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 px-3 py-2">
        <h2 className="font-mono text-xs tracking-wide text-zinc-300">{title}</h2>
        {action}
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Metric({
  label,
  value,
  hint,
  valueClassName,
}: {
  label: string;
  value: string;
  hint?: string;
  valueClassName?: string;
}) {
  return (
    <div className="rounded border border-zinc-800 bg-[#121215] px-3 py-3">
      <p className="font-mono text-[10px] tracking-widest text-zinc-500 uppercase">{label}</p>
      <p className={`mt-1 font-mono text-xl tabular-nums ${valueClassName ?? "text-zinc-50"}`}>{value}</p>
      {hint ? <p className="mt-1 font-mono text-[10px] text-zinc-600">{hint}</p> : null}
    </div>
  );
}

function DarkField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="mb-1 block font-mono text-[10px] text-zinc-500">{label}</label>
      {children}
    </div>
  );
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  // Hem Türkçe (Pozitif/Nötr/Negatif) hem eski İngilizce etiketleri destekle
  const normalized = sentiment.toLowerCase();
  const isPositive = normalized === "pozitif" || normalized === "positive";
  const isNegative = normalized === "negatif" || normalized === "negative";
  const tone = isPositive
    ? "border-emerald-800 text-emerald-400"
    : isNegative
      ? "border-rose-800 text-rose-400"
      : "border-zinc-700 text-zinc-500";
  const label = isPositive ? "POZ" : isNegative ? "NEG" : "NTR";
  return <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${tone}`}>{label}</span>;
}
