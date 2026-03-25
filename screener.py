"""
BIST Ucuz Hisse Tarayıcı v3
============================
TradingView Scanner API üzerinden BIST hisselerini tarar.
Basit, güvenilir, debug çıktılı. Tek dosya, dış modül bağımlılığı yok.
"""

import requests
import json
import os
import traceback
from datetime import datetime, timezone

# ── Ayarlar ───────────────────────────────────────────────────────────────────
FILTERS = {
    "fk_max": 10,
    "fk_min": 0,
    "pddd_max": 2.0,
    "fd_favok_max": 8,
    "fd_satis_max": 1.5,
    "goster_adet": 50,
}

# ── TradingView Scanner API ──────────────────────────────────────────────────
TV_URL = "https://scanner.tradingview.com/turkey/scan"

TV_COLUMNS = [
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
    "dividend_yield_recent",
    "Recommend.All",
    "Recommend.MA",
    "Recommend.Other",
    "analyst_rating",
    "number_of_analysts",
    "target_price",
    "Perf.W",
    "Perf.1M",
    "Perf.3M",
]


def veri_cek():
    """TradingView Scanner API ile BIST verilerini çeker."""

    payload = {
        "columns": TV_COLUMNS,
        "options": {"lang": "tr"},
        "range": [0, 600],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": ["stock"]}},
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }

    print(f"[API] POST {TV_URL}")

    try:
        r = requests.post(TV_URL, json=payload, headers=headers, timeout=30)
        print(f"[API] HTTP Status: {r.status_code}")
        print(f"[API] Response boyut: {len(r.text)} byte")

        if r.status_code != 200:
            print(f"[API] HATA body: {r.text[:500]}")
            return []

        data = r.json()
        print(f"[API] totalCount: {data.get('totalCount', '?')}")

        if "data" not in data:
            print(f"[API] 'data' key yok! Keys: {list(data.keys())}")
            print(f"[API] İlk 500 char: {json.dumps(data)[:500]}")
            return []

        stocks = []
        for item in data["data"]:
            d = item.get("d", [])
            if len(d) < len(TV_COLUMNS):
                continue

            vals = dict(zip(TV_COLUMNS, d))

            stock = {
                "ticker": vals.get("name", ""),
                "ad": vals.get("description", ""),
                "son_fiyat": _f(vals.get("close")),
                "degisim": _f(vals.get("change")),
                "piyasa_degeri": _f(vals.get("market_cap_basic")),
                "fk": _f(vals.get("price_earnings_ttm")),
                "pddd": _f(vals.get("price_book_fq")),
                "fd_favok": _f(vals.get("enterprise_value_ebitda_ttm")),
                "fd_satis": _f(vals.get("price_revenue_ttm")),
                "hedef_fiyat": _f(vals.get("target_price")),
                "analist_sayisi": _i(vals.get("number_of_analysts")),
                "analist_rating": _f(vals.get("analyst_rating")),
                "teknik_genel": _f(vals.get("Recommend.All")),
                "temettü": _f(vals.get("dividend_yield_recent")),
            }

            if not stock["ticker"]:
                continue

            # Analist öneri çevir (1=Strong Buy, 5=Strong Sell)
            rv = stock["analist_rating"]
            if rv is not None:
                if rv <= 1.5: stock["oneri"] = "GÜÇLÜ AL"
                elif rv <= 2.5: stock["oneri"] = "AL"
                elif rv <= 3.5: stock["oneri"] = "TUT"
                elif rv <= 4.5: stock["oneri"] = "SAT"
                else: stock["oneri"] = "GÜÇLÜ SAT"
            else:
                stock["oneri"] = None

            # Teknik öneri çevir
            tv = stock["teknik_genel"]
            if tv is not None:
                if tv >= 0.5: stock["teknik_oneri"] = "GÜÇLÜ AL"
                elif tv >= 0.1: stock["teknik_oneri"] = "AL"
                elif tv > -0.1: stock["teknik_oneri"] = "NÖTR"
                elif tv > -0.5: stock["teknik_oneri"] = "SAT"
                else: stock["teknik_oneri"] = "GÜÇLÜ SAT"
            else:
                stock["teknik_oneri"] = None

            # Getiri potansiyeli
            if stock["hedef_fiyat"] and stock["son_fiyat"] and stock["son_fiyat"] > 0:
                stock["getiri_potansiyeli"] = round(
                    ((stock["hedef_fiyat"] - stock["son_fiyat"]) / stock["son_fiyat"]) * 100, 1
                )
            else:
                stock["getiri_potansiyeli"] = None

            stocks.append(stock)

        print(f"[API] {len(stocks)} hisse parse edildi")

        # İlk 3 hisseyi debug olarak göster
        for s in stocks[:3]:
            print(f"  > {s['ticker']:8s} F/K={s['fk']}  PD/DD={s['pddd']}  FD/FAVÖK={s['fd_favok']}  Hedef={s['hedef_fiyat']}")

        return stocks

    except Exception as e:
        print(f"[API] EXCEPTION: {e}")
        traceback.print_exc()
        return []


def filtrele(stocks):
    """Kriterlere göre filtreler ve skor atar."""
    sonuclar = []

    for s in stocks:
        fk = s.get("fk")
        pddd = s.get("pddd")
        fd_favok = s.get("fd_favok")
        fd_satis = s.get("fd_satis")

        # Negatif F/K çıkar
        if fk is not None and fk < 0:
            continue

        # F/K filtresi
        if fk is not None and FILTERS["fk_max"] and fk > FILTERS["fk_max"]:
            continue

        # PD/DD filtresi
        if pddd is not None and FILTERS["pddd_max"] and pddd > FILTERS["pddd_max"]:
            continue

        # FD/FAVÖK filtresi  
        if fd_favok is not None and FILTERS["fd_favok_max"] and fd_favok > FILTERS["fd_favok_max"]:
            continue

        # FD/Satışlar filtresi
        if fd_satis is not None and FILTERS["fd_satis_max"] and fd_satis > FILTERS["fd_satis_max"]:
            continue

        # Skor (düşük = daha ucuz)
        skor = 0
        n = 0
        if fk and fk > 0:
            skor += (fk / (FILTERS["fk_max"] or 15)) * 0.30
            n += 0.30
        if pddd and pddd > 0:
            skor += (pddd / (FILTERS["pddd_max"] or 3)) * 0.25
            n += 0.25
        if fd_favok and fd_favok > 0:
            skor += (fd_favok / (FILTERS["fd_favok_max"] or 10)) * 0.25
            n += 0.25
        if fd_satis and fd_satis > 0:
            skor += (fd_satis / (FILTERS["fd_satis_max"] or 2)) * 0.20
            n += 0.20

        s["skor"] = round(skor / n, 3) if n > 0 else 999
        sonuclar.append(s)

    sonuclar.sort(key=lambda x: x.get("skor", 999))
    return sonuclar


def html_olustur(sonuclar, tarih):
    """Sonuçları HTML sayfası olarak oluşturur."""
    top_n = FILTERS.get("goster_adet", 50)
    gosterilecek = sonuclar[:top_n]

    rows = ""
    for i, s in enumerate(gosterilecek, 1):
        fk = f'{s["fk"]:.1f}' if s.get("fk") is not None else "-"
        pddd = f'{s["pddd"]:.2f}' if s.get("pddd") is not None else "-"
        fd_favok = f'{s["fd_favok"]:.1f}' if s.get("fd_favok") is not None else "-"
        fd_satis = f'{s["fd_satis"]:.2f}' if s.get("fd_satis") is not None else "-"
        fiyat = f'{s["son_fiyat"]:.2f}' if s.get("son_fiyat") is not None else "-"
        hedef = f'{s["hedef_fiyat"]:.2f}' if s.get("hedef_fiyat") is not None else "-"
        skor = f'{s["skor"]:.3f}' if s.get("skor") is not None else "-"

        getiri = s.get("getiri_potansiyeli")
        getiri_str = f'{getiri:+.1f}%' if getiri is not None else "-"
        getiri_cls = ""
        if getiri is not None:
            if getiri > 30: getiri_cls = "g-high"
            elif getiri > 10: getiri_cls = "g-mid"
            elif getiri > 0: getiri_cls = "g-low"
            else: getiri_cls = "g-neg"

        oneri = s.get("oneri") or "-"
        oneri_cls = ""
        if "AL" in str(oneri): oneri_cls = "badge-al"
        elif "TUT" in str(oneri) or "NÖTR" in str(oneri): oneri_cls = "badge-tut"
        elif "SAT" in str(oneri): oneri_cls = "badge-sat"

        teknik = s.get("teknik_oneri") or "-"
        teknik_cls = ""
        if "AL" in str(teknik): teknik_cls = "badge-al"
        elif "NÖTR" in str(teknik): teknik_cls = "badge-tut"
        elif "SAT" in str(teknik): teknik_cls = "badge-sat"

        analist_n = f'({s["analist_sayisi"]})' if s.get("analist_sayisi") else ""

        skor_cls = ""
        sv = s.get("skor", 999)
        if sv < 0.4: skor_cls = "s-1"
        elif sv < 0.6: skor_cls = "s-2"
        elif sv < 0.8: skor_cls = "s-3"
        else: skor_cls = "s-4"

        rows += f"""<tr>
<td class="r">#{i}</td>
<td class="t"><a href="https://www.tradingview.com/symbols/BIST-{s['ticker']}/" target="_blank">{s['ticker']}</a></td>
<td class="a">{s.get('ad','')}</td>
<td class="n">{fk}</td>
<td class="n">{pddd}</td>
<td class="n">{fd_favok}</td>
<td class="n">{fd_satis}</td>
<td class="n">{fiyat}</td>
<td class="n">{hedef}</td>
<td class="n {getiri_cls}">{getiri_str}</td>
<td class="n"><span class="b {oneri_cls}">{oneri}</span> <span class="an">{analist_n}</span></td>
<td class="n"><span class="b {teknik_cls}">{teknik}</span></td>
<td class="n {skor_cls}">{skor}</td>
</tr>
"""

    empty = '<tr><td colspan="13" style="text-align:center;padding:3rem;color:#64748b;">Kriterlere uyan hisse bulunamadı veya veri çekilemedi.</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BIST Ucuz Hisse Tarayıcı</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a0e17;--bg2:#111827;--bg3:#1a2234;--tx:#e2e8f0;--tx2:#94a3b8;--tx3:#64748b;--gr:#22c55e;--em:#10b981;--bl:#3b82f6;--am:#f59e0b;--rd:#ef4444;--bd:rgba(255,255,255,.06)}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Inter,system-ui,sans-serif;background:var(--bg);color:var(--tx);line-height:1.6}}
.c{{max-width:1500px;margin:0 auto;padding:1.5rem}}
header{{text-align:center;margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:1px solid var(--bd)}}
.logo{{font-size:.7rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--em);margin-bottom:.5rem}}
h1{{font-family:'JetBrains Mono',monospace;font-size:1.8rem;font-weight:700;background:linear-gradient(135deg,#e2e8f0,#22c55e);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:.3rem}}
.sub{{color:var(--tx3);font-size:.85rem}}
.meta{{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap;margin-top:1rem}}
.mi{{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--tx2);background:var(--bg2);padding:.35rem .7rem;border-radius:5px;border:1px solid var(--bd)}}
.mi span{{color:var(--em);font-weight:600}}
.filters{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.8rem;margin-bottom:1.5rem}}
.fc{{background:var(--bg3);border:1px solid var(--bd);border-radius:8px;padding:.8rem 1rem;text-align:center}}
.fc .l{{font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;color:var(--tx3);margin-bottom:.3rem}}
.fc .v{{font-family:'JetBrains Mono',monospace;font-size:1.3rem;font-weight:700;color:var(--em)}}
.tw{{overflow-x:auto;border-radius:10px;border:1px solid var(--bd);background:var(--bg2)}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
thead th{{font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);background:var(--bg3);padding:.7rem .6rem;text-align:right;white-space:nowrap;position:sticky;top:0;border-bottom:2px solid rgba(255,255,255,.08)}}
thead th:nth-child(-n+3){{text-align:left}}
tbody tr{{border-bottom:1px solid var(--bd);transition:background .15s}}
tbody tr:hover{{background:rgba(30,41,59,.7)}}
td{{padding:.55rem .6rem;white-space:nowrap}}
td.r{{font-family:'JetBrains Mono',monospace;color:var(--tx3);font-size:.75rem;width:40px}}
td.t a{{font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--bl);text-decoration:none;font-size:.9rem}}
td.t a:hover{{color:var(--em);text-decoration:underline}}
td.a{{color:var(--tx2);font-size:.78rem;max-width:180px;overflow:hidden;text-overflow:ellipsis}}
td.n{{font-family:'JetBrains Mono',monospace;text-align:right;color:var(--tx)}}
.b{{font-family:'JetBrains Mono',monospace;font-size:.65rem;font-weight:700;padding:.15rem .4rem;border-radius:3px;letter-spacing:.04em}}
.badge-al{{background:rgba(34,197,94,.15);color:var(--gr);border:1px solid rgba(34,197,94,.3)}}
.badge-tut{{background:rgba(245,158,11,.15);color:var(--am);border:1px solid rgba(245,158,11,.3)}}
.badge-sat{{background:rgba(239,68,68,.15);color:var(--rd);border:1px solid rgba(239,68,68,.3)}}
.an{{font-size:.6rem;color:var(--tx3)}}
.g-high{{color:var(--gr)!important;font-weight:700}}
.g-mid{{color:var(--em)!important;font-weight:600}}
.g-low{{color:var(--am)!important}}
.g-neg{{color:var(--rd)!important}}
.s-1{{color:var(--gr)!important;font-weight:700}}
.s-2{{color:var(--em)!important;font-weight:600}}
.s-3{{color:var(--am)!important}}
.s-4{{color:var(--rd)!important}}
footer{{text-align:center;margin-top:2rem;padding-top:1rem;border-top:1px solid var(--bd);color:var(--tx3);font-size:.72rem}}
footer a{{color:var(--bl);text-decoration:none}}
.disc{{margin-top:.5rem;font-size:.65rem;opacity:.6}}
@media(max-width:768px){{.c{{padding:.8rem}}h1{{font-size:1.2rem}}table{{font-size:.75rem}}td,th{{padding:.4rem .3rem}}td.a{{display:none}}}}
</style>
</head>
<body>
<div class="c">
<header>
<div class="logo">▲ BIST Screener</div>
<h1>Ucuz Hisse Tarayıcı</h1>
<p class="sub">Temel çarpanlara göre BIST'in en ucuz hisseleri</p>
<div class="meta">
<div class="mi">Tarama: <span>{tarih}</span></div>
<div class="mi">Bulunan: <span>{len(sonuclar)}</span> hisse</div>
<div class="mi">Gösterilen: <span>{len(gosterilecek)}</span></div>
</div>
</header>
<div class="filters">
<div class="fc"><div class="l">F/K ≤</div><div class="v">{FILTERS['fk_max']}</div></div>
<div class="fc"><div class="l">PD/DD ≤</div><div class="v">{FILTERS['pddd_max']}</div></div>
<div class="fc"><div class="l">FD/FAVÖK ≤</div><div class="v">{FILTERS['fd_favok_max']}</div></div>
<div class="fc"><div class="l">FD/Satışlar ≤</div><div class="v">{FILTERS['fd_satis_max']}</div></div>
</div>
<div class="tw">
<table>
<thead><tr>
<th>#</th><th>Ticker</th><th>Şirket</th><th>F/K</th><th>PD/DD</th>
<th>FD/FAVÖK</th><th>FD/Satış</th><th>Fiyat</th><th>Hedef ₺</th>
<th>Potansiyel</th><th>Analist</th><th>Teknik</th><th>Skor</th>
</tr></thead>
<tbody>
{rows if rows else empty}
</tbody>
</table>
</div>
<footer>
<p>Veriler <a href="https://www.tradingview.com" target="_blank">TradingView</a>'dan alınmaktadır.</p>
<p class="disc">⚠️ Bu tarayıcı yatırım tavsiyesi değildir. Kendi araştırmanızı yapın.</p>
</footer>
</div>
</body>
</html>"""


def _f(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _i(v):
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def main():
    print("=" * 60)
    print("BIST Ucuz Hisse Tarayıcı v3")
    print("=" * 60)

    tarih = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Veri çek
    print("\n[1/3] TradingView'dan veriler çekiliyor...")
    stocks = veri_cek()

    if not stocks:
        print("\n[HATA] Hiç veri çekilemedi!")
        print("[HATA] Boş sayfa oluşturuluyor...")
    else:
        print(f"\n[2/3] Filtreler uygulanıyor...")
        stocks = filtrele(stocks)
        print(f"  > {len(stocks)} hisse kriterlere uydu")

    # HTML
    print(f"\n[3/3] HTML oluşturuluyor...")
    html = html_olustur(stocks, tarih)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  > docs/index.html kaydedildi ({len(html)} byte)")

    # Özet
    if stocks:
        print(f"\nTOP 5:")
        for i, s in enumerate(stocks[:5], 1):
            print(f"  {i}. {s['ticker']:8s} F/K={str(s.get('fk','?')):>6} PD/DD={str(s.get('pddd','?')):>5} Skor={s.get('skor','?')}")


if __name__ == "__main__":
    main()
