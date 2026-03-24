# 📊 BIST Ucuz Hisse Tarayıcı

BIST'teki tüm hisseleri temel çarpanlara göre tarayan, en ucuz hisseleri listeleyen ve İş Yatırım hedef fiyat/konsensüs verilerini gösteren otomatik tarayıcı.

## Kriterler

| Çarpan | Açıklama | Varsayılan |
|--------|----------|------------|
| **F/K** | Fiyat / Kazanç | ≤ 10 |
| **PD/DD** | Piyasa Değeri / Defter Değeri | ≤ 2.0 |
| **FD/FAVÖK** | Firma Değeri / FAVÖK | ≤ 8 |
| **FD/Satışlar** | Firma Değeri / Satışlar | ≤ 1.5 |

Her hisseye bu çarpanların ağırlıklı ortalamasından bir **ucuzluk skoru** atanır. Düşük skor = daha ucuz.

## Hedef Fiyat & Konsensüs

Filtreleme sonrası bulunan hisseler için İş Yatırım'dan ek veriler çekilir:
- **Hedef Fiyat (₺)**: Analistlerin 12 aylık hedef fiyatı
- **Getiri Potansiyeli (%)**: Mevcut fiyat vs hedef fiyat farkı
- **Öneri**: AL / TUT / SAT tavsiyesi

> Not: Hedef fiyat verisi İş Yatırım'ın takip listesindeki hisseler için mevcuttur.
> Takip listesinde olmayan hisseler için bu sütunlar "-" gösterir.

## Kurulum

### 1. Repo'yu Fork Et
Bu repo'yu GitHub hesabına fork et.

### 2. GitHub Pages Aç
- **Settings → Pages → Source** → `Deploy from a branch`
- **Branch**: `main`, **Folder**: `/docs`
- Kaydet

### 3. Otomatik Çalıştır
GitHub Actions haftaiçi her gün 21:30 Türkiye saati (borsa kapanışından sonra) çalışır.

Manuel çalıştırmak için: **Actions → BIST Günlük Tarama → Run workflow**

### 4. Sonuçları Gör
`https://<github-kullanıcı-adın>.github.io/bist-screener/`

## Filtre Ayarları

`config.py` dosyasından filtreleri değiştirebilirsin:

```python
FILTERS = {
    "fk_max": 10,        # F/K ≤ 10
    "pddd_max": 2.0,     # PD/DD ≤ 2
    "fd_favok_max": 8,   # FD/FAVÖK ≤ 8
    "fd_satis_max": 1.5, # FD/Satışlar ≤ 1.5
}
```

3 hazır profil var:
- **FILTERS** → Dengeli (varsayılan)
- **FILTERS_AGRESIF** → Çok ucuz hisseler (F/K ≤ 5, PD/DD ≤ 1)
- **FILTERS_GENIS** → Daha geniş tarama (F/K ≤ 15)

Agresif modu kullanmak için `screener.py`'de:
```python
from config import FILTERS_AGRESIF as FILTERS
```

## Lokal Çalıştırma

```bash
pip install -r requirements.txt
python screener.py
# → docs/index.html oluşur, tarayıcıda aç
```

## Veri Kaynağı

Veriler [İş Yatırım](https://www.isyatirim.com.tr) API'sinden çekilir.

## ⚠️ Sorumluluk Reddi

Bu araç **yatırım tavsiyesi değildir**. Sadece filtreleme aracıdır. Yatırım kararlarınızı kendi araştırmanıza dayandırın.
