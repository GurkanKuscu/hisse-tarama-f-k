"""
BIST Ucuz Hisse Tarayıcı
========================
TradingView + İş Yatırım verilerini birleştirerek belirlenen kriterlere göre
ucuz hisseleri filtreler. Sonuçları HTML olarak kaydeder (GitHub Pages).
"""

import requests
import json
import os
from datetime import datetime, timezone
from config import FILTERS, SECTOR_MAP
from hedef_fiyat import toplu_hedef_fiyat_cek, getiri_potansiyeli_hesapla
from tradingview_data import tv_tam_veri_cek, teknik_oneri_renk

# ── İş Yatırım API endpointleri ──────────────────────────────────────────────
HISSE_LISTESI_URL = "https://www.isyatirim.com.tr/api/hisse/list"
TEMEL_VERI_URL = "https://www.isyatirim.com.tr/_layouts/15/Jeeves/Jes498.ashx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.isyatirim.com.tr/",
    "Accept": "application/json",
}


def hisse_listesi_cek():
    """BIST'teki tüm hisselerin listesini çeker."""
    try:
        # İş Yatırım temel göstergeler sayfası API'si
        url = "https://www.isyatirim.com.tr/api/fundamentals/stocks"
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    # Alternatif: Hisse temel verileri toplu çekme
    try:
        url = (
            "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/"
            "Common/Data.aspx/MembersInformationBy498"
        )
        params = {
            "exchange": "BIST",
            "lang": "tr-TR",
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass

    return None


def temel_verileri_cek():
    """
    İş Yatırım'dan tüm BIST hisselerinin temel verilerini toplu çeker.
    F/K, PD/DD, FD/FAVÖK, FD/Satışlar gibi çarpanları döndürür.
    """
    url = (
        "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/"
        "Common/Data.aspx/BullBear"
    )
    params = {
        "endeks": "BIST TUM",
        "doession": "",
        "lang": "tr-TR",
    }

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "d" in data:
                return data["d"]
            return data
    except Exception as e:
        print(f"[HATA] BullBear API: {e}")

    # Alternatif endpoint
    alt_url = (
        "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/"
        "Common/Data.aspx/StockFundamentals"
    )
    alt_params = {
        "exchange": "BIST",
        "lang": "tr-TR",
    }
    try:
        r = requests.get(alt_url, params=alt_params, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[HATA] StockFundamentals API: {e}")

    return None


def hisse_detay_cek(ticker: str):
    """Tek bir hisse için detaylı temel verileri çeker."""
    url = (
        "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/"
        "Common/Data.aspx/CompanyFundamentals"
    )
    params = {
        "code": f"{ticker}.E.BIST",
        "lang": "tr-TR",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, dict) and "d" in data:
                return data["d"]
            return data
    except Exception:
        return None


def toplu_temel_veri_cek_v2():
    """
    Alternatif yöntem: İş Yatırım'ın filtreleme sayfası API'sinden
    tüm hisselerin çarpanlarını çeker.
    """
    url = (
        "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/"
        "Common/Data.aspx/OneClickData"
    )
    # Farklı veri setlerini dene
    datasets = [
        {
            "amamarkettype": "BIST",
            "lang": "tr-TR",
            "reportType": "fundamental",
        },
        {
            "exchange": "BIST",
            "lang": "tr-TR",
        },
    ]

    for params in datasets:
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                data = r.json()
                if data:
                    return data
        except Exception:
            continue

    return None


def finnet_verileri_cek():
    """
    Finnet üzerinden BIST temel verilerini çeker.
    Yedek kaynak olarak kullanılır.
    """
    url = "https://www.isyatirim.com.tr/_Layouts/15/IsYatirim.Website/Common/Data.aspx/Filtres2"
    params = {
        "endeks": "BIST TUM",
        "lang": "tr-TR",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def veri_normalize(raw_data):
    """
    Farklı API formatlarından gelen verileri standart formata çevirir.
    Her hisse için: ticker, fk, pddd, fd_favok, fd_satis, favok_marj, net_kar, piyasa_degeri
    """
    stocks = []

    if not raw_data:
        return stocks

    # Eğer liste ise
    items = raw_data if isinstance(raw_data, list) else [raw_data]

    for item in items:
        if not isinstance(item, dict):
            continue

        stock = {}

        # Ticker çıkar
        for key in ["code", "Code", "HISSE_KODU", "hisse_kodu", "ticker", "Ticker", "TICKER", "symbol", "Symbol"]:
            if key in item:
                val = str(item[key]).replace(".E.BIST", "").replace(".BIST", "").strip()
                if val:
                    stock["ticker"] = val
                    break

        if "ticker" not in stock:
            continue

        # Şirket adı
        for key in ["title", "Title", "HISSE_ADI", "hisse_adi", "name", "Name", "ACIKLAMA"]:
            if key in item:
                stock["ad"] = str(item[key]).strip()
                break

        # Sayısal alanları çıkar
        field_map = {
            "fk": ["fk", "FK", "F_K", "f_k", "pe", "PE", "peRatio", "FK_ORAN", "fk_oran"],
            "pddd": ["pddd", "PDDD", "PD_DD", "pd_dd", "pbRatio", "PB", "pb", "PDDD_ORAN", "pddd_oran"],
            "fd_favok": ["fdfavok", "FDFAVOK", "FD_FAVOK", "fd_favok", "evEbitda", "EV_EBITDA", "ev_ebitda"],
            "fd_satis": ["fdsatis", "FDSATIS", "FD_SATIS", "fd_satis", "evSales", "EV_SALES", "ev_sales"],
            "piyasa_degeri": ["piyasaDegeri", "PIYASA_DEGERI", "piyasa_degeri", "marketCap", "MarketCap", "PIYASA_DEGERI_MN"],
            "net_kar": ["netKar", "NET_KAR", "net_kar", "netIncome", "NetIncome"],
            "favok": ["favok", "FAVOK", "ebitda", "EBITDA", "Ebitda"],
            "satis": ["satis", "SATIS", "revenue", "Revenue", "SATIS_GELIRI"],
            "favok_marj": ["favokMarj", "FAVOK_MARJ", "favok_marj", "ebitdaMargin"],
            "son_fiyat": ["kapanis", "KAPANIS", "lastPrice", "LastPrice", "SON_FIYAT", "son_fiyat", "close", "Close"],
        }

        for field, keys in field_map.items():
            for key in keys:
                if key in item and item[key] is not None:
                    try:
                        val = float(str(item[key]).replace(",", ".").replace("%", "").strip())
                        stock[field] = val
                        break
                    except (ValueError, TypeError):
                        continue

        if stock.get("ticker"):
            stocks.append(stock)

    return stocks


def filtrele(stocks, filters):
    """Belirlenen kriterlere göre hisseleri filtreler."""
    sonuclar = []

    for s in stocks:
        ticker = s.get("ticker", "")

        # F/K filtresi
        fk = s.get("fk")
        if fk is not None:
            if filters["fk_max"] and fk > filters["fk_max"]:
                continue
            if filters["fk_min"] and fk < filters["fk_min"]:
                continue
        elif filters.get("fk_zorunlu", False):
            continue

        # PD/DD filtresi
        pddd = s.get("pddd")
        if pddd is not None:
            if filters["pddd_max"] and pddd > filters["pddd_max"]:
                continue
        elif filters.get("pddd_zorunlu", False):
            continue

        # FD/FAVÖK filtresi
        fd_favok = s.get("fd_favok")
        if fd_favok is not None:
            if filters["fd_favok_max"] and fd_favok > filters["fd_favok_max"]:
                continue
        elif filters.get("fd_favok_zorunlu", False):
            continue

        # FD/Satışlar filtresi
        fd_satis = s.get("fd_satis")
        if fd_satis is not None:
            if filters["fd_satis_max"] and fd_satis > filters["fd_satis_max"]:
                continue
        elif filters.get("fd_satis_zorunlu", False):
            continue

        # Negatif F/K'yı çıkar (zarar eden şirketler)
        if filters.get("negatif_fk_cikar", True) and fk is not None and fk < 0:
            continue

        # Skor hesapla (düşük = daha ucuz)
        skor = hesapla_skor(s, filters)
        s["skor"] = skor

        sonuclar.append(s)

    # Skora göre sırala (en ucuz önce)
    sonuclar.sort(key=lambda x: x.get("skor", 999))

    return sonuclar


def hesapla_skor(stock, filters):
    """
    Çoklu çarpan bazlı ucuzluk skoru.
    Her çarpanı max değere normalize edip ağırlıklı ortalama alır.
    Düşük skor = daha ucuz hisse.
    """
    skor = 0
    agirlik_toplam = 0

    metrikler = {
        "fk": {"deger": stock.get("fk"), "max": filters["fk_max"] or 15, "agirlik": 0.30},
        "pddd": {"deger": stock.get("pddd"), "max": filters["pddd_max"] or 3, "agirlik": 0.25},
        "fd_favok": {"deger": stock.get("fd_favok"), "max": filters["fd_favok_max"] or 10, "agirlik": 0.25},
        "fd_satis": {"deger": stock.get("fd_satis"), "max": filters["fd_satis_max"] or 2, "agirlik": 0.20},
    }

    for key, m in metrikler.items():
        if m["deger"] is not None and m["deger"] > 0:
            normalize = m["deger"] / m["max"]
            skor += normalize * m["agirlik"]
            agirlik_toplam += m["agirlik"]

    if agirlik_toplam > 0:
        skor = skor / agirlik_toplam
    else:
        skor = 999  # Veri yoksa en sona at

    return round(skor, 3)


def html_olustur(sonuclar, filters, tarih):
    """Sonuçları şık bir HTML sayfası olarak oluşturur."""

    top_n = filters.get("goster_adet", 50)
    gosterilecek = sonuclar[:top_n]

    rows_html = ""
    for i, s in enumerate(gosterilecek, 1):
        fk_val = f'{s.get("fk", "-"):.1f}' if isinstance(s.get("fk"), (int, float)) else "-"
        pddd_val = f'{s.get("pddd", "-"):.2f}' if isinstance(s.get("pddd"), (int, float)) else "-"
        fd_favok_val = f'{s.get("fd_favok", "-"):.1f}' if isinstance(s.get("fd_favok"), (int, float)) else "-"
        fd_satis_val = f'{s.get("fd_satis", "-"):.2f}' if isinstance(s.get("fd_satis"), (int, float)) else "-"
        skor_val = f'{s.get("skor", "-"):.3f}' if isinstance(s.get("skor"), (int, float)) else "-"
        fiyat_val = f'{s.get("son_fiyat", "-"):.2f}' if isinstance(s.get("son_fiyat"), (int, float)) else "-"

        # Hedef fiyat verileri
        hedef_val = f'{s.get("hedef_fiyat"):.2f}' if isinstance(s.get("hedef_fiyat"), (int, float)) else "-"
        oneri_raw = s.get("oneri", "-")
        getiri_pot = s.get("getiri_potansiyeli")
        getiri_val = f'{getiri_pot:+.1f}%' if isinstance(getiri_pot, (int, float)) else "-"

        # Öneri badge rengi
        oneri_class = {
            "AL": "oneri-al",
            "TUT": "oneri-tut",
            "SAT": "oneri-sat",
        }.get(oneri_raw, "oneri-yok")

        # Getiri potansiyeli rengi
        if isinstance(getiri_pot, (int, float)):
            if getiri_pot > 30:
                getiri_class = "getiri-yuksek"
            elif getiri_pot > 10:
                getiri_class = "getiri-orta"
            elif getiri_pot > 0:
                getiri_class = "getiri-dusuk"
            else:
                getiri_class = "getiri-negatif"
        else:
            getiri_class = ""

        # Teknik analiz
        teknik_raw = s.get("teknik_oneri") or s.get("teknik_oneri_ta") or "-"
        teknik_class = teknik_oneri_renk(teknik_raw) if teknik_raw != "-" else "oneri-yok"
        analist_n = s.get("analist_sayisi")
        analist_str = f'({analist_n})' if analist_n else ""

        # Skor rengini belirle
        skor = s.get("skor", 999)
        if skor < 0.4:
            skor_class = "skor-cok-ucuz"
        elif skor < 0.6:
            skor_class = "skor-ucuz"
        elif skor < 0.8:
            skor_class = "skor-normal"
        else:
            skor_class = "skor-pahali"

        rows_html += f"""
        <tr>
            <td class="rank">#{i}</td>
            <td class="ticker">
                <a href="https://www.tradingview.com/symbols/BIST-{s['ticker']}/"
                   target="_blank">{s['ticker']}</a>
            </td>
            <td class="ad">{s.get('ad', '-')}</td>
            <td class="num">{fk_val}</td>
            <td class="num">{pddd_val}</td>
            <td class="num">{fd_favok_val}</td>
            <td class="num">{fd_satis_val}</td>
            <td class="num">{fiyat_val}</td>
            <td class="num">{hedef_val}</td>
            <td class="num {getiri_class}">{getiri_val}</td>
            <td class="num"><span class="oneri-badge {oneri_class}">{oneri_raw}</span> <span class="analist-n">{analist_str}</span></td>
            <td class="num"><span class="oneri-badge {teknik_class}">{teknik_raw}</span></td>
            <td class="num {skor_class}">{skor_val}</td>
        </tr>"""

    # Filtre bilgisi
    filtre_info = f"""
    F/K ≤ {filters['fk_max'] or '∞'} | 
    PD/DD ≤ {filters['pddd_max'] or '∞'} | 
    FD/FAVÖK ≤ {filters['fd_favok_max'] or '∞'} | 
    FD/Satışlar ≤ {filters['fd_satis_max'] or '∞'}
    """

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BIST Ucuz Hisse Tarayıcı</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: #1a2234;
            --bg-row-hover: #1e293b;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-green: #22c55e;
            --accent-emerald: #10b981;
            --accent-blue: #3b82f6;
            --accent-amber: #f59e0b;
            --accent-red: #ef4444;
            --border: #1e293b;
            --border-subtle: rgba(255,255,255,0.06);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Space Grotesk', system-ui, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}

        .bg-grid {{
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
            z-index: 0;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
            position: relative;
            z-index: 1;
        }}

        header {{
            text-align: center;
            margin-bottom: 2.5rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}

        .logo {{
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--accent-emerald);
            margin-bottom: 0.75rem;
        }}

        h1 {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #e2e8f0, #22c55e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }}

        .subtitle {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        .meta-bar {{
            display: flex;
            gap: 1.5rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 1.25rem;
        }}

        .meta-item {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
            background: var(--bg-secondary);
            padding: 0.4rem 0.8rem;
            border-radius: 6px;
            border: 1px solid var(--border-subtle);
        }}

        .meta-item span {{
            color: var(--accent-emerald);
            font-weight: 600;
        }}

        /* ─── Filtre kartları ─── */
        .filters {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .filter-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 1rem 1.25rem;
            text-align: center;
        }}

        .filter-card .label {{
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 0.4rem;
        }}

        .filter-card .value {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent-emerald);
        }}

        /* ─── Tablo ─── */
        .table-wrap {{
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid var(--border-subtle);
            background: var(--bg-secondary);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
        }}

        thead th {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            background: var(--bg-card);
            padding: 0.9rem 1rem;
            text-align: right;
            white-space: nowrap;
            position: sticky;
            top: 0;
            border-bottom: 2px solid var(--border);
        }}

        thead th:nth-child(1),
        thead th:nth-child(2),
        thead th:nth-child(3) {{
            text-align: left;
        }}

        tbody tr {{
            border-bottom: 1px solid var(--border-subtle);
            transition: background 0.15s;
        }}

        tbody tr:hover {{
            background: var(--bg-row-hover);
        }}

        td {{
            padding: 0.75rem 1rem;
            white-space: nowrap;
        }}

        td.rank {{
            font-family: 'JetBrains Mono', monospace;
            color: var(--text-muted);
            font-size: 0.8rem;
            width: 50px;
        }}

        td.ticker a {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            color: var(--accent-blue);
            text-decoration: none;
            font-size: 0.95rem;
        }}

        td.ticker a:hover {{
            color: var(--accent-emerald);
            text-decoration: underline;
        }}

        td.ad {{
            color: var(--text-secondary);
            font-size: 0.82rem;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        td.num {{
            font-family: 'JetBrains Mono', monospace;
            text-align: right;
            color: var(--text-primary);
        }}

        .skor-cok-ucuz {{
            color: var(--accent-green) !important;
            font-weight: 700;
        }}

        .skor-ucuz {{
            color: var(--accent-emerald) !important;
            font-weight: 600;
        }}

        .skor-normal {{
            color: var(--accent-amber) !important;
        }}

        .skor-pahali {{
            color: var(--accent-red) !important;
        }}

        /* ─── Hedef Fiyat & Öneri ─── */
        .oneri-badge {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            letter-spacing: 0.05em;
        }}

        .oneri-al {{
            background: rgba(34, 197, 94, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(34, 197, 94, 0.3);
        }}

        .oneri-tut {{
            background: rgba(245, 158, 11, 0.15);
            color: var(--accent-amber);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .oneri-sat {{
            background: rgba(239, 68, 68, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}

        .oneri-yok {{
            color: var(--text-muted);
        }}

        .getiri-yuksek {{
            color: var(--accent-green) !important;
            font-weight: 700;
        }}

        .getiri-orta {{
            color: var(--accent-emerald) !important;
            font-weight: 600;
        }}

        .getiri-dusuk {{
            color: var(--accent-amber) !important;
        }}

        .getiri-negatif {{
            color: var(--accent-red) !important;
        }}

        .analist-n {{
            font-size: 0.65rem;
            color: var(--text-muted);
            margin-left: 0.15rem;
        }}

        /* ─── Footer ─── */
        footer {{
            text-align: center;
            margin-top: 2.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.78rem;
        }}

        footer a {{
            color: var(--accent-blue);
            text-decoration: none;
        }}

        .disclaimer {{
            margin-top: 0.75rem;
            font-size: 0.7rem;
            color: var(--text-muted);
            opacity: 0.7;
        }}

        /* ─── Boş durum ─── */
        .empty-state {{
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-muted);
        }}

        .empty-state .icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}

        /* ─── Responsive ─── */
        @media (max-width: 768px) {{
            .container {{ padding: 1rem; }}
            h1 {{ font-size: 1.4rem; }}
            table {{ font-size: 0.8rem; }}
            td, th {{ padding: 0.5rem 0.6rem; }}
            td.ad {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="bg-grid"></div>
    <div class="container">
        <header>
            <div class="logo">▲ BIST Screener</div>
            <h1>Ucuz Hisse Tarayıcı</h1>
            <p class="subtitle">Temel çarpanlara göre BIST'in en ucuz hisseleri</p>
            <div class="meta-bar">
                <div class="meta-item">Tarama: <span>{tarih}</span></div>
                <div class="meta-item">Bulunan: <span>{len(sonuclar)}</span> hisse</div>
                <div class="meta-item">Gösterilen: <span>{len(gosterilecek)}</span></div>
            </div>
        </header>

        <div class="filters">
            <div class="filter-card">
                <div class="label">F/K ≤</div>
                <div class="value">{filters['fk_max'] or '∞'}</div>
            </div>
            <div class="filter-card">
                <div class="label">PD/DD ≤</div>
                <div class="value">{filters['pddd_max'] or '∞'}</div>
            </div>
            <div class="filter-card">
                <div class="label">FD/FAVÖK ≤</div>
                <div class="value">{filters['fd_favok_max'] or '∞'}</div>
            </div>
            <div class="filter-card">
                <div class="label">FD/Satışlar ≤</div>
                <div class="value">{filters['fd_satis_max'] or '∞'}</div>
            </div>
        </div>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Ticker</th>
                        <th>Şirket</th>
                        <th>F/K</th>
                        <th>PD/DD</th>
                        <th>FD/FAVÖK</th>
                        <th>FD/Satış</th>
                        <th>Fiyat</th>
                        <th>Hedef ₺</th>
                        <th>Potansiyel</th>
                        <th>Analist</th>
                        <th>Teknik</th>
                        <th>Skor</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="13" class="empty-state"><div class="icon">📊</div><div>Kriterlere uyan hisse bulunamadı veya veri çekilemedi.</div></td></tr>'}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Veriler <a href="https://www.tradingview.com" target="_blank">TradingView</a> ve
               <a href="https://www.isyatirim.com.tr" target="_blank">İş Yatırım</a>'dan alınmaktadır.</p>
            <p class="disclaimer">
                ⚠️ Bu tarayıcı yatırım tavsiyesi değildir. Kendi araştırmanızı yapın.
                Veriler gecikebilir veya eksik olabilir.
            </p>
        </footer>
    </div>
</body>
</html>"""

    return html


def main():
    print("=" * 60)
    print("BIST Ucuz Hisse Tarayıcı (v2 — TradingView + İş Yatırım)")
    print("=" * 60)

    tarih = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── ADIM 1: TradingView'dan toplu veri çek (birincil kaynak) ──────────
    print("\n[1/5] TradingView'dan veriler çekiliyor...")
    tv_data = tv_tam_veri_cek()

    stocks = []

    if tv_data:
        # TradingView verisini stocks listesine çevir
        stocks = list(tv_data.values())
        print(f"  ✓ TradingView'dan {len(stocks)} hisse alındı")
    else:
        # ── FALLBACK: İş Yatırım API ──────────────────────────────────────
        print("  ✗ TradingView başarısız, İş Yatırım deneniyor...")

        print("\n[1/5] İş Yatırım temel veriler çekiliyor...")
        raw = temel_verileri_cek()

        if not raw:
            print("  → BullBear API başarısız, alternatif deneniyor...")
            raw = toplu_temel_veri_cek_v2()

        if not raw:
            print("  → Alternatif de başarısız, Finnet deneniyor...")
            raw = finnet_verileri_cek()

        if not raw:
            print("  ✗ Hiçbir kaynaktan veri çekilemedi!")
            html = html_olustur([], FILTERS, tarih)
            kaydet(html)
            return

        print(f"  ✓ Ham veri alındı ({type(raw).__name__})")
        stocks = veri_normalize(raw)

    if not stocks:
        print("  ✗ Parse edilebilen hisse yok!")
        html = html_olustur([], FILTERS, tarih)
        kaydet(html)
        return

    # ── ADIM 2: Normalize ─────────────────────────────────────────────────
    print(f"\n[2/5] {len(stocks)} hisse normalize edildi")

    # ── ADIM 3: Filtrele ──────────────────────────────────────────────────
    print(f"\n[3/5] Filtreler uygulanıyor...")
    print(f"  F/K ≤ {FILTERS['fk_max']} | PD/DD ≤ {FILTERS['pddd_max']} | "
          f"FD/FAVÖK ≤ {FILTERS['fd_favok_max']} | FD/Satışlar ≤ {FILTERS['fd_satis_max']}")

    sonuclar = filtrele(stocks, FILTERS)
    print(f"  ✓ {len(sonuclar)} hisse kriterlere uydu")

    # ── ADIM 4: Eksik hedef fiyatları İş Yatırım'dan tamamla ─────────────
    eksik_hedef = [s for s in sonuclar if not s.get("hedef_fiyat")]
    if eksik_hedef:
        print(f"\n[4/5] {len(eksik_hedef)} hisse için İş Yatırım hedef fiyat deneniyor...")
        eksik_tickers = [s["ticker"] for s in eksik_hedef]
        iy_veriler = toplu_hedef_fiyat_cek(eksik_tickers)

        iy_bulunan = 0
        for s in sonuclar:
            ticker = s["ticker"]
            if not s.get("hedef_fiyat") and ticker in iy_veriler:
                hv = iy_veriler[ticker]
                s["hedef_fiyat"] = hv.get("hedef_fiyat")
                if not s.get("oneri"):
                    s["oneri"] = hv.get("oneri")

                if s.get("hedef_fiyat") and s.get("son_fiyat"):
                    s["getiri_potansiyeli"] = getiri_potansiyeli_hesapla(
                        s["son_fiyat"], s["hedef_fiyat"]
                    )
                iy_bulunan += 1

        print(f"  ✓ İş Yatırım'dan ek {iy_bulunan} hisse için hedef fiyat bulundu")
    else:
        print(f"\n[4/5] Tüm hisselerin hedef fiyatı TradingView'dan geldi ✓")

    # Özet istatistik
    hedef_var = sum(1 for s in sonuclar if s.get("hedef_fiyat"))
    oneri_var = sum(1 for s in sonuclar if s.get("oneri"))
    teknik_var = sum(1 for s in sonuclar if s.get("teknik_oneri") or s.get("teknik_oneri_ta"))
    print(f"\n  Hedef fiyat: {hedef_var}/{len(sonuclar)} | "
          f"Analist öneri: {oneri_var}/{len(sonuclar)} | "
          f"Teknik sinyal: {teknik_var}/{len(sonuclar)}")

    # ── ADIM 5: HTML oluştur ──────────────────────────────────────────────
    print(f"\n[5/5] HTML oluşturuluyor...")
    html = html_olustur(sonuclar, FILTERS, tarih)
    kaydet(html)

    # Özet
    print(f"\n{'=' * 60}")
    print(f"TOP 10 EN UCUZ HİSSELER:")
    print(f"{'=' * 60}")
    for i, s in enumerate(sonuclar[:10], 1):
        fk = f'{s.get("fk", 0):.1f}' if s.get("fk") else "-"
        pddd = f'{s.get("pddd", 0):.2f}' if s.get("pddd") else "-"
        hedef = f'{s.get("hedef_fiyat", 0):.2f}' if s.get("hedef_fiyat") else "-"
        oneri = s.get("oneri") or "-"
        teknik = s.get("teknik_oneri") or s.get("teknik_oneri_ta") or "-"
        print(f"  {i:2d}. {s['ticker']:8s} | F/K: {fk:>6s} | PD/DD: {pddd:>6s} | "
              f"Hedef: {hedef:>8s} | {oneri:>6s} | Teknik: {teknik}")


def kaydet(html):
    """HTML dosyasını kaydeder."""
    # docs/ klasörü (GitHub Pages için)
    os.makedirs("docs", exist_ok=True)
    output_path = "docs/index.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  ✓ Kaydedildi: {output_path}")

    # Ayrıca JSON olarak da kaydet (ileride kullanmak için)
    json_path = "docs/latest.json"
    # JSON verisi daha sonra eklenebilir


if __name__ == "__main__":
    main()
