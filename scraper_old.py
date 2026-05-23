import json
import re
import requests
from bs4 import BeautifulSoup


def parse_hasta_matrix_to_json(url, output_file):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"Pobieranie danych z: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"Błąd podczas pobierania strony: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    tabele = soup.find_all("table")

    wszystkie_mecze = []
    przetworzone_pary = set()

    print(f"Przetwarzanie {len(tabele)} grup ligowych...")

    for index_tab in range(len(tabele)):
        tabela = tabele[index_tab]

        elementy_th = [
            th.text.strip() for th in tabela.find_all("th") if th.text.strip()
        ]

        if not elementy_th:
            continue

        liga = elementy_th[0]

        gracze_grupy = []
        for el in elementy_th[1:]:
            if el.lower() in [
                "miejsce",
                "wygranemecze",
                "sety",
                "punkty",
                "roznica",
                "z/s",
            ]:
                break
            gracze_grupy.append(el)

        if not gracze_grupy:
            continue

        start_szukania = len(gracze_grupy) + 1
        th_wyniki = elementy_th[start_szukania:]

        aktualny_gracz_1 = None
        licznik_przeciwnika = 0

        i = 0
        while i < len(th_wyniki):
            token = th_wyniki[i]

            if token in gracze_grupy:
                aktualny_gracz_1 = token
                licznik_przeciwnika = 0
                i += 1
                continue

            if aktualny_gracz_1 and token.isdigit() and len(token) >= 5:
                if licznik_przeciwnika < len(gracze_grupy):
                    aktualny_gracz_2 = gracze_grupy[licznik_przeciwnika]

                    if aktualny_gracz_1 == aktualny_gracz_2:
                        licznik_przeciwnika += 1
                        continue

                    sety_1 = int(token[0])
                    sety_2 = int(token[1])

                    # Wyciąganie wszystkich małych punktów z reszty ciągu
                    surowe_punkty = token[2:]
                    male_punkty_płaska_lista = []

                    j = 0
                    while j < len(surowe_punkty):
                        if (
                            j + 1 < len(surowe_punkty)
                            and surowe_punkty[j] == "1"
                            and surowe_punkty[j + 1] in "0123456789"
                        ):
                            male_punkty_płaska_lista.append(
                                int(surowe_punkty[j : j + 2])
                            )
                            j += 2
                        elif (
                            j + 1 < len(surowe_punkty)
                            and surowe_punkty[j] == "2"
                            and surowe_punkty[j + 1] in "01234"
                        ):
                            male_punkty_płaska_lista.append(
                                int(surowe_punkty[j : j + 2])
                            )
                            j += 2
                        else:
                            male_punkty_płaska_lista.append(
                                int(surowe_punkty[j])
                            )
                            j += 1

                    # --- POPRAWIONA LOGIKA: Podział ciągu na pół ---
                    # Skoro pierwsza połowa listy to punkty Gracza 1, a druga to punkty Gracza 2:
                    ustrukturyzowane_sety = []
                    polowa = len(male_punkty_płaska_lista) // 2

                    punkty_g1 = male_punkty_płaska_lista[:polowa]
                    punkty_g2 = male_punkty_płaska_lista[polowa:]

                    # Łączymy w pary odpowiadające sobie indeksy (Set 1 z Set 1, Set 2 z Set 2 itd.)
                    for idx in range(len(punkty_g1)):
                        if idx < len(punkty_g2):
                            ustrukturyzowane_sety.append(
                                {
                                    "set_numer": idx + 1,
                                    "punkty_gracz_1": punkty_g1[idx],
                                    "punkty_gracz_2": punkty_g2[idx],
                                }
                            )
                    # -----------------------------------------------

                    para_klucz = tuple(
                        sorted([aktualny_gracz_1, aktualny_gracz_2])
                    )

                    if para_klucz not in przetworzone_pary:
                        mecz = {
                            "liga": liga,
                            "gracz_1": aktualny_gracz_1,
                            "gracz_2": aktualny_gracz_2,
                            "wynik_sety": {
                                "gracz_1": sety_1,
                                "gracz_2": sety_2,
                            },
                            "szczegoly_setow": ustrukturyzowane_sety,
                            "surowy_wynik_ciag": token,
                            "Zwyciezca": (
                                aktualny_gracz_1
                                if sety_1 > sety_2
                                else aktualny_gracz_2
                            ),
                        }
                        wszystkie_mecze.append(mecz)
                        przetworzone_pary.add(para_klucz)

                    licznik_przeciwnika += 1
            i += 1

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(wszystkie_mecze, f, indent=4, ensure_ascii=False)

    print(
        f"Sukces! Sparsowano {len(wszystkie_mecze)} meczów z POPRAWNĄ strukturą punktów do '{output_file}'"
    )


url_target = "https://hastalavista.pl/dyscypliny/squash/liga-open/wyniki/"
parse_hasta_matrix_to_json(url_target, "wyniki_ligi.json")