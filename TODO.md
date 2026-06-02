# Zadania z podzialem na kamienie milowe

## Kamień milowy 2.: Architektura Transformatorów i Jednostek w Mapping API
- Wdrożenie obsługi kluczy `"transform"` i `"unit"` wewnątrz `portal_data_mapping.json` oraz silnika `mapping.py`.
- Zbudowanie pliku `transformers.py` z rejestrem bezpiecznych funkcji do konwersji typów (np. `cm_to_m`, `date_to_quarter`, string_split).
- Zapewnienie pełnej agnostyczności danych wyjściowych dla aplikacji nadrzędnej (jednolite typy i jednostki).
- **Testy**: Testy jednostkowe funkcji transformujących w izolacji.

## Kamień milowy 3.: Rozwiązanie Priorytetyzacji Zdjęć (Galerie)
- Zaimplementowanie transformatorów specjalistycznych dla galerii RynekPierwotny i Otodom.
- Zmodyfikowanie ścieżki w JSON, by zwracała gotową, płaską listę stringów bez duplikatów dla wszystkich portali.
- **Testy**: Unit testy weryfikujące, czy transformator wybiera poprawną rozdzielczość na podstawie wycinków `raw_rp_*.json`.

## Kamień milowy 4.: Segmentacja i Agregacja (Sygnały i Typy Transakcji)
- Wdrożenie agregatora oceniającego sygnały i określającego segment (dom/mieszkanie/komercyjne) oraz typ transakcji (rent/sale).
- Usunięcie na stałe hardkodowanej logiki z klas aplikacji nadrzędnej.
- **Testy**: Testy integracyjne na `porta_data_mapping_tests` potwierdzające poprawne klasyfikowanie segmentów.

## Kamień milowy 5.: Zaawansowane Ekstrakcje Adresów
- Zaimplementowanie transformatorów tekstowych lub regex dla wydobywania danych adresowych z opisów (TabelaOfert, RynekPierwotny) oraz usuwania przedrostków "ul." (Otodom).
- **Testy**: Testy weryfikujące wycinanie i odgadywanie dzielnic/miast z ciągów tekstowych.

## Kamień milowy 6.: Wyczyszczenie i Zakończenie Refaktoringu
- Aktualizacja wersji, dokumentacji, uruchomienie wszystkich testów, i pushowanie na GitHuba gotowego nowego mechanizmu mapowania.