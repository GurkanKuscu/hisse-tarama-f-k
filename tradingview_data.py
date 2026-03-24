"""
TradingView Entegrasyonu
========================
TradingView Screener API + TA API ile BIST hisselerinin:
  - Analist hedef fiyatları
  - Analist önerileri (AL/TUT/SAT)
  - Teknik analiz sinyalleri (BUY/SELL/NEUTRAL)
  - Temel çarpanları (F/K, PD/DD, vb.)
verilerini toplu olarak çeker.

Kütüphaneler:
  - tradingview-screener: Toplu veri (temel + analist)
  - tradingview-ta: Teknik analiz önerileri
"""

import time
import json
import requests

# ── TradingView Screener API (doğrudan HTTP) ─────────────────────────────────
# tradingview-screener kütüphanesi yoksa bile çalışabilsin diye
# ham API çağrısı da dahil edildi.

TV_SCREENER_URL = "https://scanner.tradingview.com/turkey/scan"

# İstediğimiz alanlar
TV_FIELDS = [
    "name",                          # Ticker (örn: THYAO)
    "description",                   # Şirket adı
    "close",                         # Son fiyat
    "change",                        # Günlük değişim %
    "volume",                        # Hacim
    "market_cap_basic",              # Piyasa değeri
    # Çarpanlar
    "price_earnings_ttm",            # F/K (TTM)
    "price_book_fq",                 # PD/DD
    "enterprise_value_ebitda_ttm",   # FD/FAVÖK
    "price_revenue_ttm",             # FD/Satışlar (yaklaşık)
    "enterprise_value_fq",           # Firma değeri
    "dividend_yield_recent",         # Temettü verimi
    # Analist verileri
    "analyst_rating",                # Konsensüs öneri (1=Strong Buy → 5=Strong Sell)
    "analyst_rating_recommendation", # Öneri string
    "number_of_analysts",            # Analist sayısı
    "target_price",                  # Konsensüs hedef fiyat
    # Teknik
    "Recommend.All",                 # Genel teknik öneri
    "Recommend.MA",                  # Hareketli ortalama önerisi
    "Recommend.Other",               # Osilatör önerisi
    # Performans
    "Perf.W",                        # Haftalık performans
    "Perf.1M",                       # Aylık performans
    "Perf.3M",                       # 3 aylık performans
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json",
}


def tv_screener_toplu_cek(min_piyasa_degeri=0):
    """
    TradingView Screener API ile BIST'teki tüm hisselerin
    temel + analist + teknik verilerini toplu çeker.
    
    Tek bir HTTP POST isteğiyle ~500 hisse gelir.
    """
    payload = {
        "columns": TV_FIELDS,
        "filter": [
            {
                "left": "is_primary",
                "operation": "equal",
                "right": True,
            },
        ],
        "options": {
            "lang": "tr",
        },
        "range": [0, 600],  # Max 600 hisse
        "sort": {
            "sortBy": "market_cap_basic",
            "sortOrder": "desc",
        },
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
    }

    if min_piyasa_degeri > 0:
        payload["filter"].append({
            "left": "market_cap_basic",
            "operation": "greater",
            "right": min_piyasa_degeri,
        })

    try:
        r = requests.post(
            TV_SCREENER_URL,
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        if r.status_code == 200:
            data = r.json()
            return data
        else:
            print(f"  [TV] Screener API hata: HTTP {r.status_code}")
            return None
    except Exception as e:
        print(f"  [TV] Screener API hata: {e}")
        return None


def tv_veri_parse(raw_data):
    """
    TradingView Screener API yanıtını standart formata çevirir.
    
    Returns:
        dict: {ticker: {tüm_veriler}}
    """
    if not raw_data or "data" not in raw_data:
        return {}

    sonuclar = {}

    for item in raw_data["data"]:
        d = item.get("d", [])
        if not d or len(d) < len(TV_FIELDS):
            continue

        # Field listesiyle eşleştir
        veri = dict(zip(TV_FIELDS, d))

        ticker = veri.get("name", "")
        if not ticker:
            continue

        stock = {
            "ticker": ticker,
            "ad": veri.get("description", ""),
            "son_fiyat": _safe_float(veri.get("close")),
            "degisim": _safe_float(veri.get("change")),
            "hacim": _safe_float(veri.get("volume")),
            "piyasa_degeri": _safe_float(veri.get("market_cap_basic")),
            # Çarpanlar
            "fk": _safe_float(veri.get("price_earnings_ttm")),
            "pddd": _safe_float(veri.get("price_book_fq")),
            "fd_favok": _safe_float(veri.get("enterprise_value_ebitda_ttm")),
            "fd_satis": _safe_float(veri.get("price_revenue_ttm")),
            "firma_degeri": _safe_float(veri.get("enterprise_value_fq")),
            "temettü_verimi": _safe_float(veri.get("dividend_yield_recent")),
            # Analist verileri
            "analist_rating": _safe_float(veri.get("analyst_rating")),
            "analist_oneri_str": veri.get("analyst_rating_recommendation"),
            "analist_sayisi": _safe_int(veri.get("number_of_analysts")),
            "hedef_fiyat": _safe_float(veri.get("target_price")),
            # Teknik sinyaller (-1 ile +1 arası; >0.1=BUY, <-0.1=SELL)
            "teknik_genel": _safe_float(veri.get("Recommend.All")),
            "teknik_ma": _safe_float(veri.get("Recommend.MA")),
            "teknik_osc": _safe_float(veri.get("Recommend.Other")),
            # Performans
            "perf_hafta": _safe_float(veri.get("Perf.W")),
            "perf_ay": _safe_float(veri.get("Perf.1M")),
            "perf_3ay": _safe_float(veri.get("Perf.3M")),
        }

        # Öneri çevir (1-5 skalası → AL/TUT/SAT)
        rating = stock["analist_rating"]
        if rating is not None:
            if rating <= 1.5:
                stock["oneri"] = "GÜÇLÜ AL"
            elif rating <= 2.5:
                stock["oneri"] = "AL"
            elif rating <= 3.5:
                stock["oneri"] = "TUT"
            elif rating <= 4.5:
                stock["oneri"] = "SAT"
            else:
                stock["oneri"] = "GÜÇLÜ SAT"
        else:
            stock["oneri"] = None

        # Teknik öneri çevir
        teknik = stock["teknik_genel"]
        if teknik is not None:
            if teknik >= 0.5:
                stock["teknik_oneri"] = "GÜÇLÜ AL"
            elif teknik >= 0.1:
                stock["teknik_oneri"] = "AL"
            elif teknik > -0.1:
                stock["teknik_oneri"] = "NÖTR"
            elif teknik > -0.5:
                stock["teknik_oneri"] = "SAT"
            else:
                stock["teknik_oneri"] = "GÜÇLÜ SAT"
        else:
            stock["teknik_oneri"] = None

        # Getiri potansiyeli hesapla
        if stock["hedef_fiyat"] and stock["son_fiyat"] and stock["son_fiyat"] > 0:
            stock["getiri_potansiyeli"] = round(
                ((stock["hedef_fiyat"] - stock["son_fiyat"]) / stock["son_fiyat"]) * 100,
                1,
            )
        else:
            stock["getiri_potansiyeli"] = None

        sonuclar[ticker] = stock

    return sonuclar


def tv_teknik_analiz_toplu(tickers: list):
    """
    tradingview-ta kütüphanesi ile toplu teknik analiz çeker.
    Kütüphane yüklü değilse atlar.
    
    Args:
        tickers: BIST ticker listesi
    
    Returns:
        dict: {ticker: {"oneri": "BUY", "buy": 8, "sell": 3, "neutral": 6}}
    """
    try:
        from tradingview_ta import TA_Handler, Interval, get_multiple_analysis
    except ImportError:
        print("  [TV-TA] tradingview-ta yüklü değil, teknik analiz atlanıyor")
        return {}

    sonuclar = {}

    # Sembolleri BIST formatına çevir
    symbols = [f"BIST:{t}" for t in tickers]

    # 50'şerli batch'ler halinde çek (API limiti)
    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]

        try:
            analyses = get_multiple_analysis(
                screener="turkey",
                interval=Interval.INTERVAL_1_DAY,
                symbols=batch,
                timeout=15,
            )

            for symbol_key, analysis in analyses.items():
                if analysis is None:
                    continue

                ticker = symbol_key.split(":")[-1] if ":" in symbol_key else symbol_key

                summary = analysis.summary
                sonuclar[ticker] = {
                    "teknik_oneri_ta": summary.get("RECOMMENDATION", ""),
                    "teknik_buy": summary.get("BUY", 0),
                    "teknik_sell": summary.get("SELL", 0),
                    "teknik_neutral": summary.get("NEUTRAL", 0),
                }

        except Exception as e:
            print(f"  [TV-TA] Batch {i // batch_size + 1} hata: {e}")

        # Rate limiting
        if i + batch_size < len(symbols):
            time.sleep(0.5)

    return sonuclar


def tv_tam_veri_cek(mevcut_stocks: list = None):
    """
    Ana fonksiyon: TradingView'dan tüm verileri çeker ve birleştirir.
    
    Args:
        mevcut_stocks: Mevcut hisse listesi (varsa sadece bunlar için TA çek)
    
    Returns:
        dict: {ticker: {birleştirilmiş tüm veriler}}
    """
    print("  → TradingView Screener API çağrılıyor...")
    raw = tv_screener_toplu_cek()

    if not raw:
        print("  ✗ TradingView'dan veri alınamadı")
        return {}

    sonuclar = tv_veri_parse(raw)
    toplam = len(sonuclar)
    hedefli = sum(1 for s in sonuclar.values() if s.get("hedef_fiyat"))
    analistli = sum(1 for s in sonuclar.values() if s.get("analist_sayisi"))

    print(f"  ✓ {toplam} hisse çekildi")
    print(f"  ✓ {hedefli} hisse için analist hedef fiyatı var")
    print(f"  ✓ {analistli} hisse analist takibinde")

    # tradingview-ta ile teknik analiz ekle (opsiyonel)
    if mevcut_stocks:
        tickers = [s["ticker"] for s in mevcut_stocks if "ticker" in s]
    else:
        tickers = list(sonuclar.keys())

    # Sadece filtrelenmiş hisseler için TA çek (hız için)
    if len(tickers) <= 200:
        print(f"  → {len(tickers)} hisse için teknik analiz çekiliyor...")
        ta_data = tv_teknik_analiz_toplu(tickers)

        for ticker, ta in ta_data.items():
            if ticker in sonuclar:
                sonuclar[ticker].update(ta)

        if ta_data:
            print(f"  ✓ {len(ta_data)} hisse için teknik analiz alındı")
    else:
        print(f"  → Teknik analiz: {len(tickers)} hisse çok fazla, screener verisi kullanılacak")

    return sonuclar


# ── Yardımcı fonksiyonlar ────────────────────────────────────────────────────

def _safe_float(val):
    """Güvenli float dönüşüm."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val):
    """Güvenli int dönüşüm."""
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def teknik_oneri_renk(oneri: str) -> str:
    """Teknik öneri için CSS class döndürür."""
    if not oneri:
        return ""
    o = oneri.upper()
    if "GÜÇLÜ AL" in o or "STRONG_BUY" in o:
        return "oneri-al"
    elif "AL" in o or "BUY" in o:
        return "oneri-al"
    elif "TUT" in o or "NÖTR" in o or "NEUTRAL" in o or "HOLD" in o:
        return "oneri-tut"
    elif "SAT" in o or "SELL" in o:
        return "oneri-sat"
    return ""
