"""
BIST Ucuz Hisse Tarayıcı v3.1
"""

import requests
import json
import os
import traceback
from datetime import datetime, timezone

FILTERS = {
    "fk_max": 10,
    "fk_min": 0,
    "pddd_max": 2.0,
    "fd_favok_max": 8,
    "fd_satis_max": 1.5,
    "goster_adet": 50,
}

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
    "Perf.W",
    "Perf.1M",
    "Perf.3M",
]


def veri_cek():
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
            print(f"[API] HATA: {r.text[:500]}")
            return []

        data = r.json()
        print(f"[API] totalCount: {data.get('totalCount', '?')}")

        if "data" not in data:
            print(f"[API] 'data' key yok! Keys: {list(data.keys())}")
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
                "fk": _f(vals.get("price_earnings_ttm")),
                "pddd": _f(vals.get("price_book_fq")),
                "fd_favok": _f(vals.get("enterprise_value_ebitda_ttm")),
                "fd_satis": _f(vals.get("price_revenue_ttm")),
                "teknik_genel": _f(vals.get("Recommend.All")),
            }
            if not stock["ticker"]:
                continue

            # Teknik öneri
            tv = stock["teknik_genel"]
            if tv is not None:
                if tv >= 0.5: stock["teknik_oneri"] = "GÜÇLÜ AL"
                elif tv >= 0.1: stock["teknik_oneri"] = "AL"
                elif tv > -0.1: stock["teknik_oneri"] = "NÖTR"
                elif tv > -0.5: stock["teknik_oneri"] = "SAT"
                else: stock["teknik_oneri"] = "GÜÇLÜ SAT"
            else:
                stock["teknik_oneri"] = None

            stocks.append(stock)

        print(f"[API] {len(stocks)} hisse parse edildi")
        for s in stocks[:3]:
            print(f"  > {s['ticker']:8s} F/K={s['fk']}  PD/DD={s['pddd']}  FD/FAVÖK={s['fd_favok']}")
        return stocks

    except Exception as e:
        print(f"[API] EXCEPTION: {e}")
        traceback.print_exc()
        return []


def filtrele(stocks):
    sonuclar = []
    for s in stocks:
        fk = s.get("fk")
        pddd = s.get("pddd")
        fd_favok = s.get("fd_favok")
        fd_satis = s.get("fd_satis")

        if fk is not None and fk < 0: continue
        if fk is not None and FILTERS["fk_max"] and fk > FILTERS["fk_max"]: continue
        if pddd is not None and FILTERS["pddd_max"] and pddd > FILTERS["pddd_max"]: continue
        if fd_favok is not None and FILTERS["fd_favok_max"] and fd_favok > FILTERS["fd_favok_max"]: continue
        if fd_satis is not None and FILTERS["fd_satis_max"] and fd_satis > FILTERS["fd_satis_max"]: continue

        skor = 0
        n = 0
        if fk and fk > 0:
            skor += (fk / (FILTERS["fk_max"] or 15)) * 0.30; n += 0.30
        if pddd and pddd > 0:
            skor += (pddd / (FILTERS["pddd_max"] or 3)) * 0.25; n += 0.25
        if fd_favok and fd_favok > 0:
            skor += (fd_favok / (FILTERS["fd_favok_max"] or 10)) * 0.25; n += 0.25
        if fd_satis and fd_satis > 0:
            skor += (fd_satis / (FILTERS["fd_satis_max"] or 2)) * 0.20; n += 0.20

        s["skor"] = round(skor / n, 3) if n > 0 else 999
        sonuclar.append(s)

    sonuclar.sort(key=lambda x: x.get("skor", 999))
    return sonuclar


def html_olustur(sonuclar, tarih):
    top_n = FILTERS.get("goster_adet", 50)
    gosterilecek = sonuclar[:top_n]

    rows = ""
    for i, s in enumerate(gosterilecek, 1):
        fk = f'{s["fk"]:.1f}' if s.get("fk") is not None else "-"
        pddd = f'{s["pddd"]:.2f}' if s.get("pddd") is not None else "-"
        fd_favok = f'{s["fd_favok"]:.1f}' if s.get("fd_favok") is not None else "-"
        fd_satis = f'{s["fd_satis"]:.2f}' if s.get("fd_satis") is not None else "-"
        fiyat = f'{s["son_fiyat"]:.2f}' if s.get("son_fiyat") is not None else "-"
        skor = f'{s["skor"]:.3f}' if s.get("skor") is not None else "-"

        teknik = s.get("teknik_oneri") or "-"
        teknik_cls = ""
        if "AL" in str(teknik): teknik_cls = "badge-al"
        elif "NÖTR" in str(teknik): teknik_cls = "badge-tut"
        elif "SAT" in str(teknik): teknik_cls = "badge-sat"

        sv = s.get("skor", 999)
        skor_cls = "s-1" if sv < 0.4 else "s-2" if sv < 0.6 else "s-3" if sv < 0.8 else "s-4"

        rows += f"""<tr>
<td class="r">#{i}</td>
<td class="t"><a href="https://www.tradingview.com/symbols/BIST-{s['ticker']}/" target="_blank">{s['ticker']}</a></td>
<td class="a">{s.get('ad','')}</td>
<td class="n">{fk}</td>
<td class="n">{pddd}</td>
<td class="n">{fd_favok}</td>
<td class="n">{fd_satis}</td>
<td class="n">{fiyat}</td>
<td class="n"><span class="b {teknik_cls}">{teknik}</span></td>
<td class="n {skor_cls}">{skor}</td>
</tr>
"""

    empty = '<tr><td colspan="10" style="text-align:center;padding:3rem;color:#64748b;">Kriterlere uyan hisse bulunamadı veya veri çekilemedi.</td></tr>'

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
.c{{max-width:1400px;margin:0 auto;padding:1.5rem}}
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
table{{width:100%;border-collapse:collapse;font-size:.85rem}}
thead th{{font-family:'JetBrains Mono',monospace;font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--tx3);background:var(--bg3);padding:.75rem .7rem;text-align:right;white-space:nowrap;position:sticky;top:0;border-bottom:2px solid rgba(255,255,255,.08)}}
thead th:nth-child(-n+3){{text-align:left}}
tbody tr{{border-bottom:1px solid var(--bd);transition:background .15s}}
tbody tr:hover{{background:rgba(30,41,59,.7)}}
td{{padding:.6rem .7rem;white-space:nowrap}}
td.r{{font-family:'JetBrains Mono',monospace;color:var(--tx3);font-size:.75rem;width:40px}}
td.t a{{font-family:'JetBrains Mono',monospace;font-weight:700;color:var(--bl);text-decoration:none;font-size:.92rem}}
td.t a:hover{{color:var(--em);text-decoration:underline}}
td.a{{color:var(--tx2);font-size:.8rem;max-width:200px;overflow:hidden;text-overflow:ellipsis}}
td.n{{font-family:'JetBrains Mono',monospace;text-align:right;color:var(--tx)}}
.b{{font-family:'JetBrains Mono',monospace;font-size:.67rem;font-weight:700;padding:.18rem .45rem;border-radius:3px;letter-spacing:.04em}}
.badge-al{{background:rgba(34,197,94,.15);color:var(--gr);border:1px solid rgba(34,197,94,.3)}}
.badge-tut{{background:rgba(245,158,11,.15);color:var(--am);border:1px solid rgba(245,158,11,.3)}}
.badge-sat{{background:rgba(239,68,68,.15);color:var(--rd);border:1px solid rgba(239,68,68,.3)}}
.s-1{{color:var(--gr)!important;font-weight:700}}
.s-2{{color:var(--em)!important;font-weight:600}}
.s-3{{color:var(--am)!important}}
.s-4{{color:var(--rd)!important}}
footer{{text-align:center;margin-top:2rem;padding-top:1rem;border-top:1px solid var(--bd);color:var(--tx3);font-size:.72rem}}
footer a{{color:var(--bl);text-decoration:none}}
.disc{{margin-top:.5rem;font-size:.65rem;opacity:.6}}
@media(max-width:768px){{.c{{padding:.8rem}}h1{{font-size:1.2rem}}table{{font-size:.78rem}}td,th{{padding:.4rem .4rem}}td.a{{display:none}}}}
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
<th>FD/FAVÖK</th><th>FD/Satış</th><th>Fiyat</th><th>Teknik</th><th>Skor</th>
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
    if v is None: return None
    try: return float(v)
    except (ValueError, TypeError): return None


def _i(v):
    if v is None: return None
    try: return int(float(v))
    except (ValueError, TypeError): return None


def main():
    print("=" * 60)
    print("BIST Ucuz Hisse Tarayıcı v3.1")
    print("=" * 60)

    tarih = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print("\n[1/3] TradingView'dan veriler çekiliyor...")
    stocks = veri_cek()

    if not stocks:
        print("\n[HATA] Hiç veri çekilemedi!")
    else:
        print(f"\n[2/3] Filtreler uygulanıyor...")
        stocks = filtrele(stocks)
        print(f"  > {len(stocks)} hisse kriterlere uydu")

    print(f"\n[3/3] HTML oluşturuluyor...")
    html = html_olustur(stocks, tarih)

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  > docs/index.html kaydedildi ({len(html)} byte)")

    if stocks:
        print(f"\nTOP 5:")
        for i, s in enumerate(stocks[:5], 1):
            print(f"  {i}. {s['ticker']:8s} F/K={str(s.get('fk','?')):>6} PD/DD={str(s.get('pddd','?')):>5} Skor={s.get('skor','?')}")


if __name__ == "__main__":
    main()
