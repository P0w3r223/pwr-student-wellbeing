"""Analiza dobrostanu studentów Politechniki Wrocławskiej.

Pakiet dzieli się na cztery warstwy o rozłącznych odpowiedzialnościach:

* `schema`  — opis kwestionariusza: zmienne, skale, etykiety
* `prepare` — przekształcenie surowego eksportu w ramkę gotową do analiz
* `stats`   — testy statystyczne i tabele wyników
* `plots`   — wykresy

Konwencja: identyfikatory po angielsku, dokumentacja i dane po polsku.
"""

from .prepare import prepare_data

__all__ = ["prepare_data"]
