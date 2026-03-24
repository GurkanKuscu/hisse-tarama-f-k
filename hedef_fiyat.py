"""
Hedef Fiyat Modülü
==================
İş Yatırım'dan hedef fiyat / konsensüs verisi çeker.
BeautifulSoup bağımlılığı kaldırıldı — sadece JSON API'leri kullanılır.
"""

import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.isyatirim.com.tr/",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

BASE_URL = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/Data.aspx"

ONERI_MAP = {
    "BUY": "AL",
    "HOLD": "TUT",
    "SELL": "SAT",
    "OUTPERFORM": "AL",
    "UNDERPERFORM": "SAT",
    "NEUTRAL": "TUT",
    "MARKET PERFORM": "TUT",
    "ENDEKS ÜZERİ": "AL",
    "ENDEKS ALTI": "SAT",
    "ENDEKSE PARALEL": "TUT",
}


def takip_listesi_cek():
    """
    İş Yatırım'ın takip listesi verisini çeker.
    Birden fazla endpoint dener.
    """
    endpoints = [
        {"url": f"{BASE_URL}/CoverageList", "params": {"lang": "tr-TR"}},
        {"url": f"{BASE_URL}/StockRecommendations", "params": {"lang": "tr-TR"}},
        {"url": "https://www.isyatirim.com.tr/api/research/coverage", "params": {}},
        {
            "url": f"{BASE_URL}/OneClickData",
            "params": {"reportType": "consensus", "lang": "tr-TR"},
        },
    ]

    for ep in endpoints:
        try:
            r = requests.get(ep["url"], params=ep["params"], headers=HEADERS, timeout=20)
            if r.status_code == 200:
                data = r.json()
                if data:
                    return data
        except Exception:
            continue

    return None


def hisse_ozet_api(ticker: str):
    """Tek hisse için İş Yatırım konsensüs API'si."""
    endpoints = [
        {
            "url": f"{BASE_URL}/CompanyConsensus",
            "params": {"code": f"{ticker}.E.BIST", "lang": "tr-TR"},
        },
        {
            "url": f"{BASE_URL}/CompanySummary",
            "params": {"code": f"{ticker}.E.BIST", "lang": "tr-TR"},
        },
        {
            "url": f"{BASE_URL}/StockSummary",
            "params": {"hisse": ticker, "lang": "tr-TR"},
        },
    ]

    for ep in endpoints:
        try:
            r = requests.get(ep["url"], params=ep["params"], headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "d" in data:
                    data = data["d"]
                if data:
                    return data
        except Exception:
            continue

    return None


def toplu_hedef_fiyat_cek(tickers: list, max_workers: int = 5):
    """
    Birden fazla hisse için paralel hedef fiyat çeker.

    Returns:
        dict: {ticker: {"hedef_fiyat": X, "oneri": "AL/TUT/SAT", "getiri_potansiyeli": Y}}
    """
    sonuclar = {}

    # Önce toplu takip listesini dene
    print("  → Takip listesi API deneniyor...")
    takip = takip_listesi_cek()
    if takip:
        sonuclar = _takip_listesi_parse(takip)
        print(f"  ✓ Takip listesinden {len(sonuclar)} hisse için hedef fiyat alındı")

    # Eksik olanlar için tek tek çek (max 100 istek)
    eksik = [t for t in tickers if t not in sonuclar]

    if eksik and len(eksik) <= 100:
        print(f"  → {len(eksik)} hisse için detay API deneniyor...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, ticker in enumerate(eksik):
                if i > 0 and i % 10 == 0:
                    time.sleep(1)
                futures[executor.submit(_tek_hisse_hedef, ticker)] = ticker

            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    result = future.result()
                    if result:
                        sonuclar[ticker] = result
                except Exception:
                    pass

        print(f"  ✓ Toplam {len(sonuclar)} hisse için hedef fiyat verisi")

    return sonuclar


def _tek_hisse_hedef(ticker: str):
    """Tek hisse için API'yi dener."""
    api_data = hisse_ozet_api(ticker)
    if api_data:
        return _api_veri_parse(api_data, ticker)
    return None


def _takip_listesi_parse(raw_data):
    """Takip listesi verisini standart formata çevirir."""
    sonuclar = {}
    items = raw_data if isinstance(raw_data, list) else [raw_data]

    for item in items:
        if not isinstance(item, dict):
            continue

        ticker = None
        for key in ["code", "Code", "HISSE_KODU", "ticker", "Ticker", "symbol"]:
            if key in item:
                ticker = str(item[key]).replace(".E.BIST", "").replace(".BIST", "").strip()
                break

        if not ticker:
            continue

        result = {"ticker": ticker}

        for key in ["hedefFiyat", "hedef_fiyat", "targetPrice", "target_price", "HEDEF_FIYAT", "HedefFiyat"]:
            if key in item and item[key] is not None:
                try:
                    result["hedef_fiyat"] = float(str(item[key]).replace(",", "."))
                    break
                except (ValueError, TypeError):
                    continue

        for key in ["oneri", "Oneri", "ONERI", "recommendation", "Recommendation", "tavsiye"]:
            if key in item and item[key]:
                oneri = str(item[key]).strip().upper()
                result["oneri"] = ONERI_MAP.get(oneri, oneri)
                break

        for key in ["getiriPotansiyeli", "getiri_potansiyeli", "upside", "returnPotential"]:
            if key in item and item[key] is not None:
                try:
                    result["getiri_potansiyeli"] = float(
                        str(item[key]).replace(",", ".").replace("%", "")
                    )
                    break
                except (ValueError, TypeError):
                    continue

        if len(result) > 1:
            sonuclar[ticker] = result

    return sonuclar


def _api_veri_parse(data, ticker):
    """API'den gelen veriyi standart formata çevirir."""
    if not data:
        return None

    result = {"ticker": ticker}
    items = data if isinstance(data, list) else [data]

    for item in items:
        if not isinstance(item, dict):
            continue
        for key, val in item.items():
            kl = key.lower()
            if ("hedef" in kl or "target" in kl) and ("fiyat" in kl or "price" in kl):
                try:
                    result["hedef_fiyat"] = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    pass
            elif any(k in kl for k in ["oneri", "tavsiye", "recommendation"]):
                if val:
                    oneri = str(val).strip().upper()
                    result["oneri"] = ONERI_MAP.get(oneri, oneri)
            elif any(k in kl for k in ["getiri", "upside", "potansiyel"]):
                try:
                    result["getiri_potansiyeli"] = float(
                        str(val).replace(",", ".").replace("%", "")
                    )
                except (ValueError, TypeError):
                    pass

    return result if len(result) > 1 else None


def getiri_potansiyeli_hesapla(son_fiyat, hedef_fiyat):
    """Son fiyat ve hedef fiyattan getiri potansiyelini hesaplar."""
    if son_fiyat and hedef_fiyat and son_fiyat > 0:
        return round(((hedef_fiyat - son_fiyat) / son_fiyat) * 100, 1)
    return None
