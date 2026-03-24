"""
Hedef Fiyat Modülü
==================
İş Yatırım ve alternatif kaynaklardan hedef fiyat / konsensüs verisi çeker.

Veri kaynakları (öncelik sırasına göre):
1. İş Yatırım Takip Listesi / Coverage List API
2. İş Yatırım hisse detay sayfası scraping (BeautifulSoup)
3. Fallback: Hedef fiyat verisi yoksa "-" gösterir
"""

import requests
import time
import json
import re
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.isyatirim.com.tr/",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
}

# İş Yatırım'ın bilinen API pattern'leri
BASE_URL = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/Data.aspx"


def takip_listesi_cek():
    """
    İş Yatırım'ın takip listesi (coverage list) verisini çeker.
    Hedef fiyat, öneri (AL/TUT/SAT), getiri potansiyeli içerir.
    Bu endpoint login gerektirmeyebilir.
    """
    endpoints = [
        # Coverage list API endpoint'leri
        {
            "url": f"{BASE_URL}/CoverageList",
            "params": {"lang": "tr-TR"},
        },
        {
            "url": f"{BASE_URL}/StockRecommendations",
            "params": {"lang": "tr-TR"},
        },
        {
            "url": "https://www.isyatirim.com.tr/api/research/coverage",
            "params": {},
        },
        {
            "url": f"{BASE_URL}/OneClickData",
            "params": {
                "reportType": "consensus",
                "lang": "tr-TR",
            },
        },
    ]

    for ep in endpoints:
        try:
            r = requests.get(
                ep["url"],
                params=ep["params"],
                headers=HEADERS,
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json()
                if data:
                    print(f"  ✓ Takip listesi alındı: {ep['url']}")
                    return data
        except Exception:
            continue

    return None


def hisse_detay_sayfasi_parse(ticker: str):
    """
    İş Yatırım hisse detay sayfasından hedef fiyat bilgisini
    HTML parse ederek çeker.
    """
    url = (
        "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/"
        f"temel-degerler.aspx?hession={ticker}.E.BIST"
    )

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        result = {"ticker": ticker}

        # Hedef fiyat bilgisini ara (farklı CSS selector'ları dene)
        # İş Yatırım sayfasında genellikle "Konsensüs" veya "Hedef Fiyat" başlığı altında
        selectors = [
            # Consensus / hedef fiyat alanları
            {"text_match": "Hedef Fiyat", "type": "label"},
            {"text_match": "Konsensüs", "type": "label"},
            {"text_match": "Target", "type": "label"},
            {"text_match": "Öneri", "type": "label"},
        ]

        # Tüm text içeren elementleri tara
        all_text = soup.get_text()

        # Hedef fiyat pattern'lerini ara
        patterns = [
            r'[Hh]edef\s*[Ff]iyat[ıi]?\s*[:\s]*([0-9]+[.,][0-9]+)',
            r'[Tt]arget\s*[Pp]rice\s*[:\s]*([0-9]+[.,][0-9]+)',
            r'konsensüs.*?([0-9]+[.,][0-9]+)\s*TL',
        ]

        for pattern in patterns:
            match = re.search(pattern, all_text)
            if match:
                try:
                    val = float(match.group(1).replace(",", "."))
                    result["hedef_fiyat"] = val
                    break
                except ValueError:
                    continue

        # Öneri (AL/TUT/SAT) pattern'lerini ara
        oneri_patterns = [
            r'Öneri\s*[:\s]*(AL|TUT|SAT|ENDEKS)',
            r'Recommendation\s*[:\s]*(BUY|HOLD|SELL|OUTPERFORM|UNDERPERFORM)',
        ]

        for pattern in oneri_patterns:
            match = re.search(pattern, all_text, re.IGNORECASE)
            if match:
                oneri = match.group(1).upper()
                # İngilizce → Türkçe çevir
                oneri_map = {
                    "BUY": "AL",
                    "HOLD": "TUT",
                    "SELL": "SAT",
                    "OUTPERFORM": "AL",
                    "UNDERPERFORM": "SAT",
                }
                result["oneri"] = oneri_map.get(oneri, oneri)
                break

        # Script tag'lerinden JSON veri çıkar
        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and ("hedefFiyat" in script.string or "targetPrice" in script.string):
                # JSON parse et
                json_patterns = [
                    r'"hedefFiyat"\s*:\s*([0-9.]+)',
                    r'"targetPrice"\s*:\s*([0-9.]+)',
                    r'"consensus"\s*:\s*\{([^}]+)\}',
                ]
                for jp in json_patterns:
                    m = re.search(jp, script.string)
                    if m:
                        try:
                            result["hedef_fiyat"] = float(m.group(1))
                        except (ValueError, IndexError):
                            pass

        return result if len(result) > 1 else None

    except Exception:
        return None


def hisse_ozet_api(ticker: str):
    """
    İş Yatırım'ın hisse özet API'sinden konsensüs verisi çeker.
    """
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
            r = requests.get(
                ep["url"],
                params=ep["params"],
                headers=HEADERS,
                timeout=10,
            )
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
    Birden fazla hisse için paralel olarak hedef fiyat çeker.
    Rate limiting'e dikkat eder.

    Args:
        tickers: Hisse kodları listesi
        max_workers: Paralel istek sayısı (çok yüksek tutma!)

    Returns:
        dict: {ticker: {"hedef_fiyat": X, "oneri": "AL/TUT/SAT", "getiri_potansiyeli": Y}}
    """
    sonuclar = {}

    # Önce toplu API'yi dene
    print("  → Takip listesi API deneniyor...")
    takip = takip_listesi_cek()
    if takip:
        sonuclar = _takip_listesi_parse(takip)
        print(f"  ✓ Takip listesinden {len(sonuclar)} hisse için hedef fiyat alındı")

    # Eksik olanlar için tek tek çek
    eksik = [t for t in tickers if t not in sonuclar]

    if eksik and len(eksik) <= 100:  # Çok fazla istek atma
        print(f"  → {len(eksik)} hisse için detay sayfaları taranıyor...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, ticker in enumerate(eksik):
                # Rate limiting: her 10 istekte 1 saniye bekle
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
    """Tek hisse için tüm kaynakları dener."""
    # Önce API
    api_data = hisse_ozet_api(ticker)
    if api_data:
        parsed = _api_veri_parse(api_data, ticker)
        if parsed:
            return parsed

    # Sonra sayfa scraping
    sayfa_data = hisse_detay_sayfasi_parse(ticker)
    if sayfa_data and "hedef_fiyat" in sayfa_data:
        return sayfa_data

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

        # Hedef fiyat
        for key in [
            "hedefFiyat", "hedef_fiyat", "targetPrice", "target_price",
            "HEDEF_FIYAT", "HedefFiyat", "TargetPrice",
        ]:
            if key in item and item[key] is not None:
                try:
                    result["hedef_fiyat"] = float(str(item[key]).replace(",", "."))
                    break
                except (ValueError, TypeError):
                    continue

        # Öneri
        for key in [
            "oneri", "Oneri", "ONERI", "recommendation", "Recommendation",
            "tavsiye", "Tavsiye",
        ]:
            if key in item and item[key]:
                oneri = str(item[key]).strip().upper()
                oneri_map = {
                    "BUY": "AL", "HOLD": "TUT", "SELL": "SAT",
                    "OUTPERFORM": "AL", "UNDERPERFORM": "SAT",
                    "NEUTRAL": "TUT", "MARKET PERFORM": "TUT",
                    "ENDEKS ÜZERİ": "AL", "ENDEKS ALTI": "SAT",
                    "ENDEKSE PARALEL": "TUT",
                }
                result["oneri"] = oneri_map.get(oneri, oneri)
                break

        # Getiri potansiyeli
        for key in [
            "getiriPotansiyeli", "getiri_potansiyeli", "upside",
            "GETIRI_POTANSIYELI", "returnPotential",
        ]:
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

    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        return None

    for item in items:
        if not isinstance(item, dict):
            continue

        for key, val in item.items():
            key_lower = key.lower()

            if any(k in key_lower for k in ["hedef", "target"]) and "fiyat" in key_lower or "price" in key_lower:
                try:
                    result["hedef_fiyat"] = float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    pass

            elif any(k in key_lower for k in ["oneri", "tavsiye", "recommendation"]):
                if val:
                    result["oneri"] = str(val).strip().upper()

            elif any(k in key_lower for k in ["getiri", "upside", "potansiyel"]):
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
