"""
BIST Tarayıcı Filtre Ayarları
==============================
None = sınır yok demek.
"""

FILTERS = {
    "fk_max": 10,
    "fk_min": 0,
    "pddd_max": 2.0,
    "fd_favok_max": 8,
    "fd_satis_max": 1.5,
    "negatif_fk_cikar": True,
    "fk_zorunlu": False,
    "pddd_zorunlu": False,
    "fd_favok_zorunlu": False,
    "fd_satis_zorunlu": False,
    "goster_adet": 50,
}

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

SECTOR_MAP = {}
