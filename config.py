"""
BIST Tarayıcı Filtre Ayarları
==============================
Bu dosyadan filtreleri ihtiyacına göre ayarlayabilirsin.
None = sınır yok demek.
"""

# ── Ana filtreler ─────────────────────────────────────────────────────────────
FILTERS = {
    # Fiyat/Kazanç oranı (düşük = ucuz)
    "fk_max": 10,          # F/K ≤ 10 (görseldeki: 3.7)
    "fk_min": 0,           # Negatif F/K'yı çıkar

    # Piyasa Değeri / Defter Değeri (düşük = ucuz)
    "pddd_max": 2.0,       # PD/DD ≤ 2 (görseldeki: 0.3)

    # Firma Değeri / FAVÖK (düşük = ucuz)
    "fd_favok_max": 8,     # FD/FAVÖK ≤ 8 (görseldeki: 4.7)

    # Firma Değeri / Satışlar (düşük = ucuz)
    "fd_satis_max": 1.5,   # FD/Satışlar ≤ 1.5 (görseldeki: 0.7)

    # Negatif F/K olan (zarar eden) şirketleri çıkar
    "negatif_fk_cikar": True,

    # Zorunlu alan kontrolleri (True = bu veri yoksa hisseyi çıkar)
    "fk_zorunlu": False,
    "pddd_zorunlu": False,
    "fd_favok_zorunlu": False,
    "fd_satis_zorunlu": False,

    # Kaç hisse göster
    "goster_adet": 50,
}

# ── Agresif mod (çok ucuz hisseler) ──────────────────────────────────────────
# Görseldeki gibi çok düşük çarpanlı hisseleri bulmak için:
FILTERS_AGRESIF = {
    "fk_max": 5,
    "fk_min": 0,
    "pddd_max": 1.0,
    "fd_favok_max": 5,
    "fd_satis_max": 1.0,
    "negatif_fk_cikar": True,
    "fk_zorunlu": False,
    "pddd_zorunlu": False,
    "fd_favok_zorunlu": False,
    "fd_satis_zorunlu": False,
    "goster_adet": 30,
}

# ── Geniş mod (daha fazla hisse göster) ──────────────────────────────────────
FILTERS_GENIS = {
    "fk_max": 15,
    "fk_min": 0,
    "pddd_max": 3.0,
    "fd_favok_max": 12,
    "fd_satis_max": 2.0,
    "negatif_fk_cikar": True,
    "fk_zorunlu": False,
    "pddd_zorunlu": False,
    "fd_favok_zorunlu": False,
    "fd_satis_zorunlu": False,
    "goster_adet": 100,
}

# ── Sektör haritası (opsiyonel) ───────────────────────────────────────────────
SECTOR_MAP = {
    # İleride sektör bazlı filtreleme için
    # "BANKA": {"fk_max": 8, "pddd_max": 1.5},
    # "HOLDING": {"fk_max": 12, "pddd_max": 2.0},
}
