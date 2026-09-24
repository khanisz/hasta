import json
import re
import time
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://hastalavista.pl/dyscypliny/badminton/liga-open/wyniki-ostatniej-kolejki/"
AJAX_URL = "https://hastalavista.pl/wp-admin/admin-ajax.php"

# Zostawiamy tylko ligi/sezony, ktorych nazwa zawiera to slowo (bez wzgledu
# na wielkosc liter) - np. "Liga Open - sezon Lato 2026". Inne badmintonowe
# ligi na tej stronie (40+, Deblowa, Kobiet, student, Uczelniana...) sa
# pomijane.
FILTR_NAZWY = "open"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

AJAX_HEADERS = {
    **HEADERS,
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL,
    "Origin": "https://hastalavista.pl",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


def pobierz_liste_lig(session):
    """Pobiera liste lig/sezonow (liga_id + nazwa) z glownej strony,
    ograniczajac do tych, ktorych nazwa zawiera FILTR_NAZWY (np. 'Open')."""
    resp = session.get(BASE_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    select = soup.find("select", id="rez_ligi_ListaLig")
    if not select:
        print("UWAGA: nie znaleziono selecta 'rez_ligi_ListaLig' w HTML strony glownej.")
        return []

    ligi = []
    for opt in select.find_all("option"):
        liga_id = opt.get("value")
        nazwa = opt.text.strip()
        if not liga_id:
            continue
        if FILTR_NAZWY.lower() not in nazwa.lower():
            continue
        ligi.append({"liga_id": liga_id, "nazwa": nazwa})
    return ligi


def pobierz_wszystkie_kolejki(session, liga_id, debug=False):
    """Wola Ligi_ListaKolejek, zwraca liste WSZYSTKICH kolejek danej ligi jako
    [{"kole_id": ..., "numer": ..., "data": ...}, ...], posortowana rosnaco
    wg numeru kolejki (od najstarszej do najnowszej)."""
    data = {
        "action": "Ligi_ListaKolejek",
        "liga_id": liga_id,
        "dotyczy": "ligi_wyniki",
    }
    resp = session.post(AJAX_URL, data=data, headers=AJAX_HEADERS)
    resp.raise_for_status()

    if debug:
        print("\n----- SUROWA ODPOWIEDZ Ligi_ListaKolejek -----")
        print(resp.text[:2000])
        print("----- KONIEC FRAGMENTU -----\n")

    soup = BeautifulSoup(resp.text, "html.parser")
    opcje = soup.find_all("option")

    if not opcje:
        print(f"  Brak kolejek / nieoczekiwany format odpowiedzi dla liga_id={liga_id}")
        return []

    kolejki = []
    for opt in opcje:
        kole_id = opt.get("value")
        tekst = opt.get_text(strip=True)  # np. "7 - 2026-09-13"
        numer, data_kolejki = None, None
        dopasowanie = re.match(r"\s*(\d+)\s*-\s*(\d{4}-\d{2}-\d{2})\s*$", tekst)
        if dopasowanie:
            numer = int(dopasowanie.group(1))
            data_kolejki = dopasowanie.group(2)
        else:
            print(f"  UWAGA: nie udalo sie rozpoznac formatu 'numer - data' w '{tekst}'")
        if kole_id:
            kolejki.append({"kole_id": kole_id, "numer": numer, "data": data_kolejki})

    # Sortujemy rosnaco - jesli numer sie nie da ustalic, wpadanie na koniec
    kolejki.sort(key=lambda k: (k["numer"] is None, k["numer"]))
    return kolejki


def _tekst_z_divow(th):
    """Wyciaga nazwisko+imie z komorki naglowkowej, ktora zawiera zagniezdzone <div>."""
    divs = th.find_all("div")
    if divs:
        return " ".join(d.get_text(strip=True) for d in divs)
    return th.get_text(strip=True)


def _to_int_or_none(txt):
    txt = (txt or "").strip()
    return int(txt) if txt.isdigit() else None


def parsuj_tabele_wynikow(html_fragment):
    """Parsuje fragment HTML (odpowiedz LigiWynikiShow) na liste meczow.

    Czyta bezposrednio strukture HTML: kazdy mecz to osobna komorka
    <th class="wyniki_mecz" data-liza_id1=".." data-liza_id2="..">
    zawierajaca wlasna, zagniezdzona tabelke z wynikiem setow i punktow.
    Dziala tak samo dla badmintona jak dla squasha (badminton moze miec do
    3 setow do 21 pkt zamiast do 11, ale struktura HTML jest identyczna -
    liczba setow jest wykrywana dynamicznie, wiec nie trzeba nic zakladac).
    """
    soup = BeautifulSoup(html_fragment, "html.parser")
    tabele = soup.find_all("table", class_="ligi_wyn")

    wszystkie_mecze = []
    przetworzone_klucze = set()

    for tabela in tabele:
        trs = tabela.find_all("tr", recursive=False)
        if len(trs) < 3:
            continue

        header_row1 = trs[0]
        header_ths = header_row1.find_all("th", recursive=False)
        if not header_ths:
            continue

        liga_nazwa = header_ths[0].get("data-liga_nr") or header_ths[0].get_text(strip=True)

        col_players = []
        for th in header_ths[1:]:
            if th.find("div") is not None:
                col_players.append(_tekst_z_divow(th))
            else:
                break

        n = len(col_players)
        if n == 0:
            continue

        data_rows = trs[2:2 + n]

        for r, row in enumerate(data_rows):
            row_ths = row.find_all("th", recursive=False)
            if not row_ths:
                continue

            gracz_1 = _tekst_z_divow(row_ths[0])

            mecz_cells = [
                th for th in row_ths[1:]
                if "wyniki_mecz" in (th.get("class") or [])
            ]

            oczekiwani_przeciwnicy = [p for i, p in enumerate(col_players) if i != r]

            if len(mecz_cells) != len(oczekiwani_przeciwnicy):
                print(
                    f"  UWAGA: '{liga_nazwa}' / '{gracz_1}': liczba komorek meczowych "
                    f"({len(mecz_cells)}) != liczba oczekiwanych przeciwnikow "
                    f"({len(oczekiwani_przeciwnicy)}) - pomijam ten wiersz"
                )
                continue

            for gracz_2, cell in zip(oczekiwani_przeciwnicy, mecz_cells):
                liza_id1 = cell.get("data-liza_id1")
                liza_id2 = cell.get("data-liza_id2")

                nested = cell.find("table")
                if not nested:
                    continue
                nested_trs = nested.find_all("tr")
                if len(nested_trs) < 2:
                    continue

                row0 = nested_trs[0].find_all("th")
                row1 = nested_trs[1].find_all("th")
                if len(row0) < 2:
                    continue

                sety_1 = _to_int_or_none(row0[0].get_text())
                sety_2 = _to_int_or_none(row0[1].get_text())
                if sety_1 is None or sety_2 is None:
                    continue

                punkty_1_raw = [th.get_text(strip=True) for th in row0[2:]]
                punkty_2_raw = [th.get_text(strip=True) for th in row1]

                szczegoly_setow = []
                for idx, (p1, p2) in enumerate(zip(punkty_1_raw, punkty_2_raw)):
                    if p1.isdigit() and p2.isdigit():
                        szczegoly_setow.append(
                            {
                                "set_numer": idx + 1,
                                "punkty_gracz_1": int(p1),
                                "punkty_gracz_2": int(p2),
                            }
                        )

                if liza_id1 and liza_id2:
                    klucz = (liga_nazwa,) + tuple(sorted([liza_id1, liza_id2]))
                else:
                    klucz = (liga_nazwa,) + tuple(sorted([gracz_1, gracz_2]))

                if klucz in przetworzone_klucze:
                    continue
                przetworzone_klucze.add(klucz)

                wszystkie_mecze.append(
                    {
                        "liga": liga_nazwa,
                        "gracz_1": gracz_1,
                        "gracz_2": gracz_2,
                        "gracz_1_id": liza_id1,
                        "gracz_2_id": liza_id2,
                        "wynik_sety": {"gracz_1": sety_1, "gracz_2": sety_2},
                        "szczegoly_setow": szczegoly_setow,
                        "Zwyciezca": gracz_1 if sety_1 > sety_2 else gracz_2,
                    }
                )

    return wszystkie_mecze


def parsuj_wszystkie_ligi(output_file="wyniki_badminton_open.json", debug=False, limit=None):
    session = requests.Session()

    print(f"Pobieranie listy lig/sezonow zawierajacych '{FILTR_NAZWY}'...")
    ligi = pobierz_liste_lig(session)
    print(f"Znaleziono {len(ligi)} pasujacych lig/sezonow.")

    if not ligi:
        print("Nie znaleziono zadnych lig - przerywam.")
        return

    if limit:
        ligi = ligi[:limit]
        print(f"(tryb debug: przetwarzam tylko pierwsze {limit})")

    wszystkie_mecze = []
    pobrano_dnia = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for idx, liga in enumerate(ligi):
        liga_id = liga["liga_id"]
        nazwa = liga["nazwa"]
        print(f"[{idx + 1}/{len(ligi)}] {nazwa} (liga_id={liga_id})")

        kolejki = pobierz_wszystkie_kolejki(session, liga_id, debug=(debug and idx == 0))
        if not kolejki:
            print(f"  Pomijam '{nazwa}' - brak kolejek.")
            continue

        time.sleep(0.3)

        # KAZDA kolejka to osobny, kompletny zestaw wynikow tej rundy - jesli
        # ta sama para gra ze soba w kilku roznych kolejkach, to sa to ROZNE,
        # prawdziwe mecze, wiec nie deduplikujemy miedzy kolejkami.
        mecze_z_ligi = []

        for k_idx, kolejka in enumerate(kolejki):
            kole_id = kolejka["kole_id"]
            data = {"action": "LigiWynikiShow", "kole_id": kole_id}
            try:
                resp = session.post(AJAX_URL, data=data, headers=AJAX_HEADERS)
                resp.raise_for_status()
            except Exception as e:
                print(f"  Blad pobierania wynikow (kolejka {kolejka['numer']}) dla '{nazwa}': {e}")
                continue

            if debug and idx == 0 and k_idx == 0:
                print("\n----- SUROWA ODPOWIEDZ LigiWynikiShow (pierwsza kolejka) -----")
                print(resp.text[:2000])
                print("----- KONIEC FRAGMENTU -----\n")

            mecze_z_kolejki = parsuj_tabele_wynikow(resp.text)
            for m in mecze_z_kolejki:
                m["sezon"] = nazwa
                m["liga_id"] = liga_id
                m["kolejka_numer"] = kolejka.get("numer")
                m["kolejka_data"] = kolejka.get("data")
                m["pobrano_dnia"] = pobrano_dnia
                mecze_z_ligi.append(m)

            if debug and idx == 0:
                print(f"    kolejka {kolejka['numer']} ({kolejka['data']}): {len(mecze_z_kolejki)} meczow")

            time.sleep(0.3)  # uprzejmosc wobec serwera

        wszystkie_mecze.extend(mecze_z_ligi)
        print(f"  -> Sparsowano {len(mecze_z_ligi)} meczow z {len(kolejki)} kolejek.")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(wszystkie_mecze, f, indent=4, ensure_ascii=False)

    print(
        f"\nSukces! Lacznie sparsowano {len(wszystkie_mecze)} meczow "
        f"z {len(ligi)} lig/sezonow -> '{output_file}'"
    )


if __name__ == "__main__":
    # KROK 1 (ZALECANY): najpierw uruchom z debug=True i limit=1, zeby sprawdzic
    # na jednej lidze (pierwszej pasujacej do filtra 'Open'), czy wszystko
    # dziala poprawnie.
    # parsuj_wszystkie_ligi(output_file="wyniki_badminton_test.json", debug=True, limit=1)

    # UWAGA: pelny przebieg (KROK 2 ponizej) robi zapytanie per KOLEJKA per
    # LIGA - liczba lig bedzie duzo mniejsza niz w squashu (tylko te z 'Open'
    # w nazwie), ale i tak moze to potrwac kilka minut.

    # KROK 2: gdy krok 1 zadziala poprawnie, odkomentuj ponizsze, zeby pobrac
    # WSZYSTKIE pasujace ligi/sezony na raz:
    parsuj_wszystkie_ligi(output_file="wyniki_badminton_open.json", debug=False)