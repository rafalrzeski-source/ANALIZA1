# SportLab 3.3 — wybór spotkania z terminarza

Wybierz piłkę nożną, datę, ligę z potwierdzonymi meczami i konkretny mecz. Godziny według Polski. Zachowano tenis ATP/WTA, NBA i propozycje statystyczne bez obowiązkowych kursów.

## Instalacja na GitHub / Streamlit
W repozytorium ANALIZA1 zastąp pliki `app.py` i `requirements.txt`, następnie Commit changes. Streamlit sam uruchomi nową wersję.

## Ograniczenia
Terminarze pobierane są z publicznych endpointów ESPN. Jeśli źródło nie udostępnia meczów dla danej ligi/daty, liga nie pojawi się na liście. W tym przypadku nie są generowane fikcyjne spotkania. Analiza korzysta z dotychczasowych źródeł historycznych Football-Data i ESPN; gdy nazwy drużyn między źródłami nie pasują lub jest za mało historii, aplikacja jasno o tym informuje. Tenis pozostaje zależny od dostępności historycznych danych i nie został naprawiony tą aktualizacją. Wymagane jest sprawdzenie działania po wdrożeniu, ponieważ nie ma tu dostępu do serwerów ESPN.
