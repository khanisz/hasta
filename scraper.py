import requests
from bs4 import BeautifulSoup
import json

def pobierz_dane():
    BASE_URL = "https://hastalavista.pl/dyscypliny/squash/liga-open/wyniki/"
    AJAX_URL = "https://hastalavista.pl/wp-admin/admin-ajax.php?lang=pl_PL"
    
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    # --- KROK 1: Pobieranie listy wszystkich kolejek z głównej strony ---
    print("Pobieranie listy dostępnych kolejek...")
    r_base = session.get(BASE_URL)
    soup_base = BeautifulSoup(r_base.text, "html.parser")
    
    # Szukamy selecta, którego id zawiera słowo "Kolejek"
    select_kolejki = soup_base.find("select", id=lambda x: x and "Kolejek" in x)
    
    if not select_kolejki:
        print("[!] Nie udało się znaleźć dropdowna z kolejkami na głównej stronie.")
        return

    lista_kolejek = []
    # Zbieramy wszystkie opcje do słownika (ID oraz Nazwa)
    for opt in select_kolejki.find_all("option"):
        val = opt.get("value")
        # Pomijamy puste opcje (np. "Wybierz kolejkę", która ma puste value)
        if val and val.strip():
            lista_kolejek.append({
                "id": val.strip(),
                "nazwa": opt.text.strip()
            })
    
    print(f"Znaleziono {len(lista_kolejek)} kolejek. Rozpoczynam pobieranie meczów...\n")

    wszystkie_mecze = []
    unikalne_klucze = set()

    # --- KROK 2: Pobieranie meczów dla każdej kolejki po kolei ---
    for kol in lista_kolejek:
        k_id = kol["id"]
        k_nazwa = kol["nazwa"]
        
        print(f"Pobieranie: {k_nazwa} (ID: {k_id})...")
        payload = {"action": "LigiWynikiShow", "kole_id": k_id}
        
        try:
            r = session.post(AJAX_URL, data=payload)
            soup = BeautifulSoup(r.text, "html.parser")
            
            tabele_lig = soup.find_all("table", class_="ligi_wyn wyniki")
            if not tabele_lig:
                print(f"  [!] Brak tabel ligowych (prawdopodobnie brak wyników).")
                continue
                
            for tabela in tabele_lig:
                th_liga = tabela.find("th", class_="wyniki_liga_nr_th")
                nazwa_ligi = th_liga.text.strip() if th_liga else "Nieznana Liga"
                
                pierwszy_wiersz = tabela.find("tr")
                if not pierwszy_wiersz: continue
                
                przeciwnicy = []
                for th in pierwszy_wiersz.find_all("th", class_="ligi_wyn_nazwisko"):
                    divy = th.find_all("div")
                    if len(divy) >= 2:
                        imie = divy[1].text.strip()
                        nazwisko = divy[0].text.strip()
                        przeciwnicy.append(f"{imie} {nazwisko}")
                        
                wiersze = tabela.find_all("tr")
                for row in wiersze[2:]:
                    th_gracz1 = row.find("th", class_="wyniki_nazwisko_kol")
                    if not th_gracz1: continue
                    
                    divy1 = th_gracz1.find_all("div")
                    gracz_1 = f"{divy1[1].text.strip()} {divy1[0].text.strip()}" if len(divy1) >= 2 else th_gracz1.text.strip()
                    
                    komorki_meczowe = [c for c in row.find_all("th", recursive=False) 
                                       if c.get("class") and ("wyniki_mecz" in c.get("class") or "ligi_wyn_x" in c.get("class"))]
                    
                    for i, komorka in enumerate(komorki_meczowe):
                        if "ligi_wyn_x" in komorka.get("class", []):
                            continue 
                            
                        if i >= len(przeciwnicy):
                            break
                            
                        gracz_2 = przeciwnicy[i]
                        
                        klucz = tuple(sorted([gracz_1, gracz_2])) + (k_id,)
                        if klucz in unikalne_klucze:
                            continue
                            
                        tabelka_meczowa = komorka.find("table", class_="rez_punkty")
                        if not tabelka_meczowa:
                            continue 
                            
                        wiersze_meczowe = tabelka_meczowa.find_all("tr")
                        if len(wiersze_meczowe) < 2:
                            continue
                            
                        th_w1 = wiersze_meczowe[0].find_all("th")
                        th_w2 = wiersze_meczowe[1].find_all("th")
                        
                        try:
                            g1_sety = int(th_w1[0].text.strip())
                            g2_sety = int(th_w1[1].text.strip())
                            
                            g1_punkty = [th.text.strip() for th in th_w1[2:] if th.text.strip()]
                            g2_punkty = [th.text.strip() for th in th_w2 if th.text.strip()]
                            male_punkty_format = ", ".join([f"{p1}:{p2}" for p1, p2 in zip(g1_punkty, g2_punkty)])
                            
                            wszystkie_mecze.append({
                                "kolejka_id": k_id,
                                "kolejka_nazwa": k_nazwa,  # <-- Dodane nowe pole
                                "liga": nazwa_ligi,
                                "gracz_1": gracz_1,
                                "gracz_2": gracz_2,
                                "wynik_sety": {"g1": g1_sety, "g2": g2_sety},
                                "male_punkty": male_punkty_format,
                                "Zwyciezca": gracz_1 if g1_sety > g2_sety else gracz_2
                            })
                            unikalne_klucze.add(klucz)
                        except Exception as e:
                            pass # Cicha obsługa błędów pojedynczych komórek (zazwyczaj braki danych/walkowery)
                            
        except Exception as e:
            print(f"Błąd przy przetwarzaniu kolejki {k_nazwa}: {e}")

    with open("wyniki_ligi_full.json", "w", encoding="utf-8") as f:
        json.dump(wszystkie_mecze, f, indent=4, ensure_ascii=False)
        
    print(f"\nGotowe! Zapisano {len(wszystkie_mecze)} meczów ze wszystkich {len(lista_kolejek)} kolejek.")

if __name__ == "__main__":
    pobierz_dane()