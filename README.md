# SportLab 3.0

Nowa wersja aplikacji Streamlit: nowoczesny ciemny panel, piłka nożna, ATP/WTA i NBA, wyjaśnienia propozycji, rynki OVER/UNDER, dodatkowe zdarzenia oraz kombinacje (dla piłki).

## Jak wdrożyć bez instalowania czegokolwiek
1. Otwórz swoje repozytorium `rafalrzeski-source/ANALIZA1` na GitHub.
2. **Zastąp** pliki `app.py` i `requirements.txt` plikami z tego archiwum (nie dodawaj `app3.py` obok).
3. Kliknij **Commit changes**. Streamlit Community Cloud zwykle sam wykona aktualizację.
4. Odśwież aplikację. Jeśli wyświetla błąd instalacji, otwórz logi aplikacji w Streamlit Cloud.

## Prawdziwe kursy — konfiguracja opcjonalna
Kursy **nie są gwarantowane** i **nie są pobierane bezpośrednio z Superbet ani Betclic**. Integracja z The Odds API działa dopiero po skonfigurowaniu własnego klucza API:
- Streamlit Community Cloud → aplikacja → Settings → Secrets.
- Wpisz:

```toml
THE_ODDS_API_KEY = "TWOJ_KLUCZ_API"
```

- Zapisz. Aplikacja sprawdza kursy tylko dla niektórych obsługiwanych rozgrywek i rynków, jeśli dostawca zwraca właściwy mecz i rynek. Inne typy pokaże bez kursu.
- Nie wklejaj klucza API do publicznego repozytorium GitHub.

## Dane
- Piłka: football-data.co.uk, dla Ekstraklasy `new/POL.csv` (a nie `P1`, które oznacza Portugalię).
- Tenis: Valuebetennis, https://www.valuebetennis.com/en/donnees.htm, dane CC BY 4.0, CSV z ostatnich sezonów.
- NBA: ESPN public scoreboard.

## Ograniczenia
Dane mogą być niedostępne lub opóźnione. Tenis wyszukuje wpisany fragment nazwiska i pokazuje podpowiedzi, ale nie obiecuje pełnej listy bez dostępu do archiwum. Procenty są heurystyczne, nieskalibrowane i nie uwzględniają aktualnych kontuzji. Zdarzenie o wysokim prawdopodobieństwie nie musi być opłacalne. Nie należy traktować propozycji jako gwarancji.
