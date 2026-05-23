import os
import subprocess
import sys
import time
import webbrowser

PLIK_BAZY_JSON = "wyniki_ligi.json"
SKRYPT_SCRAPERA = "scraper.py"
SKRYPT_DASHBOARDU = "dashboard.py"
PLIK_HTML = "index.html"  # Zmień nazwę, jeśli Twój dashboard generuje plik o innej nazwie

if __name__ == "__main__":
    start_time = time.time()
    print("====================================================================")
    print(" PIPELINE URUCHOMIENIOWY: SCRAPER -> GENERATOR DASHBOARDU -> BROWSER")
    print("====================================================================\n")

    # Krok 1: Czyszczenie starego pliku bazy
    if os.path.exists(PLIK_BAZY_JSON):
        try:
            os.remove(PLIK_BAZY_JSON)
            print(" [-] Usunięto stary plik wynikowy JSON przed nowym zrzutem.")
        except Exception as e:
            print(f" [!] Ostrzeżenie przy usuwaniu starego pliku: {e}")

    # Krok 2: Odpalenie Scrapera
    print(f"\n[KROK 1/3] Uruchamianie: {SKRYPT_SCRAPERA}...")
    if os.path.exists(SKRYPT_SCRAPERA):
        try:
            subprocess.run([sys.executable, SKRYPT_SCRAPERA], check=True)
            print(f" [+] Skrypt {SKRYPT_SCRAPERA} zakończył pracę pomyślnie.")
        except subprocess.CalledProcessError:
            print(f"\n [!] BŁĄD KRYTYCZNY: Skrypt {SKRYPT_SCRAPERA} zwrócił błąd. Przerywam pipeline.")
            sys.exit(1)
    else:
        print(f" [!] Błąd: Nie odnaleziono pliku skryptu '{SKRYPT_SCRAPERA}'.")
        sys.exit(1)

    # Krok 3: Odpalenie Dashboardu
    print(f"\n[KROK 2/3] Uruchamianie: {SKRYPT_DASHBOARDU}...")
    if os.path.exists(SKRYPT_DASHBOARDU):
        try:
            subprocess.run([sys.executable, SKRYPT_DASHBOARDU], check=True)
            print(f" [+] Skrypt {SKRYPT_DASHBOARDU} zakończył pracę pomyślnie.")
        except subprocess.CalledProcessError:
            print(f"\n [!] BŁĄD KRYTYCZNY: Skrypt {SKRYPT_DASHBOARDU} zwrócił błąd.")
            sys.exit(1)
    else:
        print(f" [!] Błąd: Nie odnaleziono pliku skryptu '{SKRYPT_DASHBOARDU}'.")
        sys.exit(1)

    # Krok 4: Automatyczne otwarcie gotowego pliku HTML w przeglądarce
    print(f"\n[KROK 3/3] Otwieranie raportu w przeglądarce...")
    if os.path.exists(PLIK_HTML):
        try:
            # Konwertujemy relatywną ścieżkę na pełną bezwzględną
            sciezka_bezwzgledna = os.path.abspath(PLIK_HTML)
            webbrowser.open(f"file://{sciezka_bezwzgledna}")
            print(f" [+] Otwarto plik: {PLIK_HTML}")
        except Exception as e:
            print(f" [!] Nie udało się automatycznie otworzyć przeglądarki: {e}")
    else:
        print(f" [!] Ostrzeżenie: Nie znaleziono oczekiwanego pliku '{PLIK_HTML}'.")
        print("     Upewnij się, że dashboard.py zapisuje go pod właściwą nazwą.")

    caly_czas = time.time() - start_time
    print("\n====================================================================")
    print(f" PEŁNY PROCES ZAKOŃCZONY SUKCESEM w czasie: {caly_czas:.2f} sekund.")
    print("====================================================================")