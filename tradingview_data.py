"""
TradingView Entegrasyonu
========================
TradingView Screener API + TA API ile BIST hisselerinin:
  - Analist hedef fiyatları
  - Analist önerileri (AL/TUT/SAT)
  - Teknik analiz sinyalleri (BUY/SELL/NEUTRAL)
  - Temel çarpanları (F/K, PD/DD, vb.)
verilerini toplu olarak çeker.
"""

import time
import requests

TV_SCREENER_URL = "https://scanner.tradingview.com/turkey/scan"

TV_FIELDS = [
    "name",
    "description",
    "close",
    "change",
    "volume",
    "market_cap_basic",
    "price_earnings_ttm",
    "price_book_fq",
    "enterprise_value_ebitda_ttm",
    "price_revenue_ttm",
    "enterprise_value_fq",
    "dividend_yield_recent",
    "analyst_rating",
    "analyst_rating_recommendation",
    "number_of_analysts",
    "target_price",
    "Recommend.All",
    "Recommend.MA",
    "Recommend.Other",
    "Perf.W",
    "Perf.1M",
    "Perf.3M",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}


def tv_screener_toplu_cek():
    """
    TradingView Screener API ile BIST'teki tüm hisselerin
    temel + analist + teknik verilerini toplu çeker.
    """
    # v2 payload formatı (2024 sonrası geçerli)
    payload = {
        "columns": TV_FIELDS,
        "filter": [
            {
                "left": "is_primary",
                "operation": "equal",
                "right": True,
            },
            {
                "left": "type",
                "operation": "in_range",
                "right": ["stock", "dr", "fund"],
            },
        ],
        "options": {
            "lang": "tr",
        },
        "range": [0, 600],
        "sort": {
            "sortBy": "market_cap_basic",
            "sortOrder": "desc",
        },
        "symbols": {},
    }

    # Önce yeni format dene
    for attempt, pload in enumerate([payload, _payload_v1()], 1):
        try:
            r = requests.post(
                TV_SCREENER_URL,
                json=pload,
                headers=HEADERS,
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                if data and "data" in data and len(data["data"]) > 0:
                    print(f"  [TV] Screener API başarılı (format {attempt})")
                    return data
                else:
                    print(f"  [TV] Format {attempt}: Boş yanıt")
            else:
                print(f"  [TV] Screener API hata: HTTP {r.status_code}")
        except Exception as e:
            print(f"  [TV] Screener API hata: {e}")

    return None


def _payload_v1():
    """Eski TradingView payload formatı (fallback)."""
    return {
        "columns": TV_FIELDS,
        "filter": [
            {
                "left": "is_primary",
                "operation": "equal",
                "right": True,
            },
        ],
        "markets": ["turkey"],
        "options": {"lang": "tr"},
        "range": [0, 600],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "symbols": {"query": {"types": ["stock"]}},
    }


def tv_veri_parse(raw_data):
    """
    TradingView Screener API yanıtını standart formata çevirir.
    Returns: dict {ticker: {tüm_veriler}}
    """
    if not raw_data or "data" not in raw_data:
        return {}

    sonuclar = {}

    for item in raw_data["data"]:
        d = item.get("d", [])
        if not d:
            continue

        # Eksik field'ları None ile tamamla
        while len(d) < len(TV_FIELDS):
            d.append(None)

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
            "fk": _safe_float(veri.get("price_earnings_ttm")),
            "pddd": _safe_float(veri.get("price_book_fq")),
            "fd_favok": _safe_float(veri.get("enterprise_value_ebitda_ttm")),
            "fd_satis": _safe_float(veri.get("price_revenue_ttm")),
            "firma_degeri": _safe_float(veri.get("enterprise_value_fq")),
            "temettü_verimi": _safe_float(veri.get("dividend_yield_recent")),
            "analist_rating": _safe_float(veri.get("analyst_rating")),
            "analist_oneri_str": veri.get("analyst_rating_recommendation"),
            "analist_sayisi": _safe_int(veri.get("number_of_analysts")),
            "hedef_fiyat": _safe_float(veri.get("target_price")),
            "teknik_genel": _safe_float(veri.get("Recommend.All")),
            "teknik_ma": _safe_float(veri.get("Recommend.MA")),
            "teknik_osc": _safe_float(veri.get("Recommend.Other")),
            "perf_hafta": _safe_float(veri.get("Perf.W")),
            "perf_ay": _safe_float(veri.get("Perf.1M")),
            "perf_3ay": _safe_float(veri.get("Perf.3M")),
        }

        # Analist öneri çevir (1-5 → AL/TUT/SAT)
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

        # Getiri potansiyeli
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
    """
    try:
        from tradingview_ta import Interval, get_multiple_analysis
    except ImportError:
        return {}

    sonuclar = {}
    symbols = [f"BIST:{t}" for t in tickers]
    batch_size = 50

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i: i + batch_size]
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

        if i + batch_size < len(symbols):
            time.sleep(0.5)

    return sonuclar


def tv_tam_veri_cek(mevcut_stocks: list = None):
    """
    Ana fonksiyon: TradingView'dan tüm verileri çeker ve birleştirir.
    Returns: dict {ticker: {birleştirilmiş tüm veriler}}
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

    if mevcut_stocks:
        tickers = [s["ticker"] for s in mevcut_stocks if "ticker" in s]
    else:
        tickers = list(sonuclar.keys())

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


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val):
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
    if "GÜÇLÜ AL" in o or "STRONG_BUY" in o or "STRONG BUY" in o:
        return "oneri-al"
    elif "AL" in o or "BUY" in o:
        return "oneri-al"
    elif "TUT" in o or "NÖTR" in o or "NEUTRAL" in o or "HOLD" in o:
        return "oneri-tut"
    elif "SAT" in o or "SELL" in o:
        return "oneri-sat"
    return ""
