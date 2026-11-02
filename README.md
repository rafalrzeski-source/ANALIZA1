# SportLab 3.1

Aktualizacja obejmuje poprawki źródeł danych, Ligę Mistrzów i selekcję rynków według realnych kursów.

## Aktualizacja bez Terminala
1. Otwórz repozytorium GitHub `rafalrzeski-source/ANALIZA1`.
2. Podmień `app.py` i `requirements.txt` na pliki z ZIP, następnie zatwierdź (Commit changes).
3. Streamlit powinien sam zaktualizować aplikację. W razie błędu sprawdź logi Streamlit.

## Tenis — najważniejsze
Dotychczasowe zewnętrzne archiwum Valuebetennis bywa niedostępne. Aby analiza działała niezależnie od niego:
1. Otwórz https://tennisdata.app/downloads/ i pobierz CSV ATP/WTA za 2026 i 2025 (jeśli dostępne).
2. W aplikacji przejdź do Tenis i w polu **Archiwum ATP/WTA** wczytaj te pliki (można kilka naraz).
3. Zobaczysz liczbę wczytanych meczów, listę nazwisk i wybór zawodników. W analizie wymagane jest minimum 6 wcześniejszych wyników każdego zawodnika.
4. Jeśli nie chcesz wczytywać plików przy każdej wizycie, umieść je w folderze `tennis_data/` w repozytorium. Nazwy muszą zawierać `atp` albo `wta`.

Wczytanie danych nie jest równoznaczne z dostępem do aktualnych kursów. Nie ma automatycznej gwarancji działania zewnętrznego źródła. Rynki setów i gemów wymagają osobnej weryfikacji danych i nie są generowane na podstawie zgadywanych wartości.

## Kursy
Opcjonalny klucz The Odds API: w Streamlit Cloud → Settings → Secrets dodaj:

```toml
THE_ODDS_API_KEY = "TWOJ_KLUCZ_API"
```

Nie umieszczaj klucza w publicznym GitHub. Bez zweryfikowanego kursu SportLab pokazuje statystyki, ale nie udaje, że istnieje zakład do zagrania. Przy zweryfikowanym kursie minimalny próg wynosi 1,35, a wymagana szacowana przewaga wynosi 3%. Nie gwarantuje to zysku.

## Rozgrywki
- Ekstraklasa: poprawiony odczyt schematu Home/Away/HG/AG z Football-Data.co.uk.
- Liga Mistrzów UEFA: zakończone mecze pobierane z ESPN, o ile API zwróci historię danego sezonu. Bez odpowiednich danych analiza nie zostanie wygenerowana.
- NBA: progi punktowe wyłącznie z dostępnych linii The Odds API; żadnych arbitralnych 209,5 itd.

## Uczciwe ograniczenia
Nie można tu przetestować zewnętrznych serwerów z poziomu środowiska budowania. Została sprawdzona składnia aplikacji i lokalne testy parserów; konieczny jest test działania po wdrożeniu. The Odds API nie musi zwracać wszystkich polskich bukmacherów, wszystkich meczów lub rynków alternatywnych. Modele są uproszczone, niezwalidowane i nie uwzględniają wszystkich kontuzji, składów i zmian formy.
