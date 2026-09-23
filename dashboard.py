import streamlit as st
import pandas as pd
import json
import re
import plotly.express as px

# Ustawienia strony
st.set_page_config(page_title="Hasta La Vista - Statystyki Ligi", layout="wide")

DANE_PLIK = "wyniki_wszystkich_lig.json"


@st.cache_data
def load_data():
    try:
        with open(DANE_PLIK, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)

        # Wynik setow - klucze 'gracz_1'/'gracz_2'
        df["sety_g1"] = df["wynik_sety"].apply(lambda x: x["gracz_1"])
        df["sety_g2"] = df["wynik_sety"].apply(lambda x: x["gracz_2"])
        df["Wynik_Sety"] = df.apply(lambda x: f"{x['sety_g1']}:{x['sety_g2']}", axis=1)

        # Czytelny string z malymi punktami, budowany ze szczegoly_setow
        def _male_punkty(szczegoly):
            if not szczegoly:
                return ""
            return ", ".join(
                f"{s['punkty_gracz_1']}:{s['punkty_gracz_2']}" for s in szczegoly
            )

        df["male_punkty"] = df["szczegoly_setow"].apply(_male_punkty)

        # Etykieta kolejki - skladana z kolejka_numer + kolejka_data
        def _kolejka_nazwa(row):
            numer = row.get("kolejka_numer")
            data = row.get("kolejka_data")
            if numer is not None and data:
                return f"{numer} - {data}"
            return "brak danych"

        df["kolejka_nazwa"] = df.apply(_kolejka_nazwa, axis=1)

        return df
    except FileNotFoundError:
        return pd.DataFrame()


def oblicz_pelne_statystyki(data):
    """Pelne statystyki graczy w grupie - odpowiednik kolumn z oryginalnej
    strony: miejsce, wygrane mecze, sety (zdobyte/stracone/roznica),
    punkty (zdobyte/stracone/roznica). Sortowanie: wygrane, potem roznica
    setow, potem roznica punktow (typowy tiebreak w lidze squasha)."""
    stats = {}
    for _, row in data.iterrows():
        p1, p2 = row["gracz_1"], row["gracz_2"]
        s1, s2 = row["sety_g1"], row["sety_g2"]
        for p in (p1, p2):
            if p not in stats:
                stats[p] = {
                    "Mecze": 0,
                    "Wygrane": 0,
                    "Sety Z": 0,
                    "Sety S": 0,
                    "Punkty Z": 0,
                    "Punkty S": 0,
                }
        stats[p1]["Mecze"] += 1
        stats[p2]["Mecze"] += 1
        stats[p1]["Sety Z"] += s1
        stats[p1]["Sety S"] += s2
        stats[p2]["Sety Z"] += s2
        stats[p2]["Sety S"] += s1
        if s1 > s2:
            stats[p1]["Wygrane"] += 1
        else:
            stats[p2]["Wygrane"] += 1
        for s in row["szczegoly_setow"] or []:
            pk1, pk2 = s["punkty_gracz_1"], s["punkty_gracz_2"]
            stats[p1]["Punkty Z"] += pk1
            stats[p1]["Punkty S"] += pk2
            stats[p2]["Punkty Z"] += pk2
            stats[p2]["Punkty S"] += pk1

    wynik = (
        pd.DataFrame.from_dict(stats, orient="index")
        .reset_index()
        .rename(columns={"index": "Gracz"})
    )
    wynik["_Sety +/-"] = wynik["Sety Z"] - wynik["Sety S"]
    wynik["_Punkty +/-"] = wynik["Punkty Z"] - wynik["Punkty S"]
    wynik = wynik.sort_values(
        by=["Wygrane", "_Sety +/-", "_Punkty +/-"], ascending=False
    ).reset_index(drop=True)
    wynik.insert(0, "Miejsce", wynik.index + 1)

    def _fmt(z, s, roznica):
        znak = "+" if roznica >= 0 else ""
        return f"{z}:{s} ({znak}{roznica})"

    wynik["Sety"] = wynik.apply(
        lambda r: _fmt(r["Sety Z"], r["Sety S"], r["_Sety +/-"]), axis=1
    )
    wynik["Punkty"] = wynik.apply(
        lambda r: _fmt(r["Punkty Z"], r["Punkty S"], r["_Punkty +/-"]), axis=1
    )

    return wynik[
        [
            "Miejsce",
            "Gracz",
            "Mecze",
            "Wygrane",
            "Sety",
            "Punkty",
        ]
    ]


def render_macierz_wynikow(df_final, statystyki=None):
    """Buduje tabele-macierz podobna do tej na hastalavista.pl:
    wiersze i kolumny to gracze, komorka to wynik ich bezposredniego meczu,
    a po prawej stronie kazdego wiersza dodatkowe kolumny statystyk
    (miejsce, wygrane, sety, punkty) - tak jak na oryginalnej stronie.
    statystyki: DataFrame z oblicz_pelne_statystyki - jesli podany, ustala
    tez kolejnosc graczy (od najlepszego) zamiast sortowania alfabetycznego."""
    gracze_w_danych = set(df_final["gracz_1"]) | set(df_final["gracz_2"])
    if statystyki is not None:
        kolejnosc_graczy = statystyki["Gracz"].tolist()
        gracze = [p for p in kolejnosc_graczy if p in gracze_w_danych]
        gracze += sorted(gracze_w_danych - set(gracze))
        staty_lookup = statystyki.set_index("Gracz").to_dict("index")
    else:
        gracze = sorted(gracze_w_danych)
        staty_lookup = {}

    mecz_lookup = {}
    for _, row in df_final.iterrows():
        klucz = frozenset([row["gracz_1"], row["gracz_2"]])
        mecz_lookup[klucz] = row

    DODATKOWE_KOLUMNY = [
        ("Miejsce", "Miejsce"),
        ("Wygrane", "Wygrane"),
        ("Sety", "Sety"),
        ("Punkty", "Punkty"),
    ]

    naglowek_th = (
        '<th style="border:1px solid #ccc;padding:4px 6px;background:#e2e5ea;'
        'font-size:11px;white-space:nowrap;">{}</th>'
    )

    html = [
        '<div style="overflow-x:auto;">',
        '<table style="border-collapse:collapse;font-size:12px;text-align:center;">',
        "<tr>",
        '<th style="border:1px solid #ccc;padding:4px;background:#f0f2f6;"></th>',
    ]
    for p in gracze:
        html.append(
            '<th style="border:1px solid #ccc;padding:4px 2px;background:#f0f2f6;'
            'max-width:60px;font-size:11px;">' + p + "</th>"
        )
    for etykieta, _ in DODATKOWE_KOLUMNY:
        html.append(naglowek_th.format(etykieta))
    html.append("</tr>")

    for p1 in gracze:
        html.append(
            '<tr><th style="border:1px solid #ccc;padding:4px 8px;background:#f0f2f6;'
            'text-align:left;white-space:nowrap;">' + p1 + "</th>"
        )
        for p2 in gracze:
            if p1 == p2:
                html.append(
                    '<td style="border:1px solid #ccc;padding:4px;background:#e8e8e8;"></td>'
                )
                continue

            row = mecz_lookup.get(frozenset([p1, p2]))
            if row is None:
                html.append(
                    '<td style="border:1px solid #ccc;padding:4px;color:#bbb;">-</td>'
                )
                continue

            p1_pierwszy = row["gracz_1"] == p1
            s1 = row["sety_g1"] if p1_pierwszy else row["sety_g2"]
            s2 = row["sety_g2"] if p1_pierwszy else row["sety_g1"]

            szczegoly = row["szczegoly_setow"] or []
            if p1_pierwszy:
                pts = ", ".join(
                    f"{s['punkty_gracz_1']}:{s['punkty_gracz_2']}" for s in szczegoly
                )
            else:
                pts = ", ".join(
                    f"{s['punkty_gracz_2']}:{s['punkty_gracz_1']}" for s in szczegoly
                )

            kolor = "#1a7a1a" if row["Zwyciezca"] == p1 else "#aa3333"
            html.append(
                '<td style="border:1px solid #ccc;padding:4px;white-space:nowrap;">'
                f'<div style="font-weight:bold;color:{kolor}">{s1}:{s2}</div>'
                f'<div style="font-size:10px;color:#666">{pts}</div>'
                "</td>"
            )

        staty = staty_lookup.get(p1)
        for etykieta, klucz in DODATKOWE_KOLUMNY:
            wartosc = staty.get(klucz, "") if staty else ""
            html.append(
                '<td style="border:1px solid #ccc;padding:4px 6px;background:#f7f8fa;'
                'font-size:11px;font-weight:600;">' + str(wartosc) + "</td>"
            )
        html.append("</tr>")
    html.append("</table></div>")
    return "".join(html)


df = load_data()

if df.empty:
    st.error(f"Nie znaleziono pliku {DANE_PLIK}. Uruchom najpierw scraper!")
    st.stop()

# --- SIDEBAR ---
menu = st.sidebar.radio(
    "Nawigacja",
    [
        "Wyniki Kolejki",
        "Statystyki Gracza",
        "H2H (Pojedynek)",
        "Historia Gracza",
        "Ranking Wszechczasów",
    ],
)

# Sezon jako globalny filtr - ta sama nazwa grupy (np. EKSTRALIGA) powtarza
# sie w wielu roznych sezonach, wiec bez tego filtra dane z roznych lat
# mieszalyby sie ze soba. Nie dotyczy zakladek "Historia Gracza" i "Ranking
# Wszechczasow", ktore celowo patrza na wszystkie sezony naraz.
WSZYSTKIE_SEZONY = "Wszystkie sezony"


def posortuj_sezony(dane):
    """Sortuje sezony malejaco wg liga_id (wyzsze ID = nowszy wpis w WordPressie),
    zamiast alfabetycznie po nazwie."""
    tmp = dane[["sezon", "liga_id"]].drop_duplicates().copy()
    tmp["_liga_id_num"] = pd.to_numeric(tmp["liga_id"], errors="coerce")
    tmp = tmp.sort_values("_liga_id_num", ascending=False)
    return tmp["sezon"].tolist()


def posortuj_kolejki(dane):
    """Sortuje kolejki malejaco wg kolejka_numer (liczbowo, nie alfabetycznie -
    inaczej '10 - ...' wypadaloby przed '2 - ...')."""
    tmp = dane[["kolejka_nazwa", "kolejka_numer"]].drop_duplicates().copy()
    tmp = tmp.sort_values("kolejka_numer", ascending=False, na_position="last")
    return tmp["kolejka_nazwa"].tolist()


def posortuj_grupy(nazwy):
    """Sortuje nazwy grup tak, ze EKSTRALIGA jest pierwsza, potem 1 LIGA,
    2 LIGA, 3 LIGA... rosnaco liczbowo (nie alfabetycznie - inaczej
    '10 LIGA' wypadaloby przed '2 LIGA')."""

    def klucz(nazwa):
        if nazwa.strip().upper().startswith("EKSTRALIGA"):
            return (0, 0, nazwa)
        dopasowanie = re.match(r"\s*(\d+)", nazwa)
        if dopasowanie:
            return (1, int(dopasowanie.group(1)), nazwa)
        return (2, 0, nazwa)

    return sorted(nazwy, key=klucz)


sezony = posortuj_sezony(df)
selected_sezon = st.sidebar.selectbox("Sezon:", [WSZYSTKIE_SEZONY] + sezony)
if selected_sezon == WSZYSTKIE_SEZONY:
    df_sezon = df.copy()
else:
    df_sezon = df[df["sezon"] == selected_sezon]

wszyscy_gracze = sorted(
    list(set(df_sezon["gracz_1"].unique()) | set(df_sezon["gracz_2"].unique()))
)

# --- SEKCJA 1: WYNIKI KOLEJKI ---
if menu == "Wyniki Kolejki":
    st.title("🏆 Wyniki Kolejek i Grup")

    # Ta zakladka pokazuje jeden, konkretny "snapshot" (kolejka + grupa), wiec
    # przy "Wszystkie sezony" trzeba dodatkowo zawezic do jednej edycji ligi -
    # inaczej ta sama nazwa grupy z dwoch roznych sezonow mogla by sie wymieszac.
    if selected_sezon == WSZYSTKIE_SEZONY:
        dostepne_sezony_tab = posortuj_sezony(df_sezon)
        sezon_tab = st.selectbox("Zawęź do sezonu (dla tej zakładki):", dostepne_sezony_tab)
        df_sezon_tab = df_sezon[df_sezon["sezon"] == sezon_tab]
    else:
        sezon_tab = selected_sezon
        df_sezon_tab = df_sezon

    st.caption(f"Sezon: {sezon_tab}")

    kolejki = posortuj_kolejki(df_sezon_tab)
    selected_kolejka = st.selectbox("Wybierz kolejkę:", kolejki)

    df_kolejka = df_sezon_tab[df_sezon_tab["kolejka_nazwa"] == selected_kolejka]
    grupy = posortuj_grupy(df_kolejka["liga"].unique().tolist())

    for grupa in grupy:
        df_final = df_kolejka[df_kolejka["liga"] == grupa].copy()
        tabela_standings = oblicz_pelne_statystyki(df_final)

        st.markdown(f"### {grupa}")
        st.markdown(render_macierz_wynikow(df_final, statystyki=tabela_standings), unsafe_allow_html=True)

# --- SEKCJA 2: STATYSTYKI GRACZA ---
elif menu == "Statystyki Gracza":
    st.title("👤 Profil Zawodnika")
    st.caption(f"Sezon: {selected_sezon}")
    gracz = st.selectbox("Wybierz gracza:", wszyscy_gracze)

    mecze_gracza = df_sezon[
        (df_sezon["gracz_1"] == gracz) | (df_sezon["gracz_2"] == gracz)
    ].copy()

    total = len(mecze_gracza)
    wygrane = len(mecze_gracza[mecze_gracza["Zwyciezca"] == gracz])
    win_rate = (wygrane / total * 100) if total > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Rozegrane mecze", total)
    c2.metric("Wygrane", wygrane)
    c3.metric("Win Rate", f"{win_rate:.1f}%")

    st.markdown("### Historia meczów")
    mecze_gracza["Status"] = mecze_gracza["Zwyciezca"].apply(
        lambda x: "✅" if x == gracz else "❌"
    )

    st.dataframe(
        mecze_gracza[
            ["Status", "sezon", "kolejka_nazwa", "liga", "gracz_1", "Wynik_Sety", "gracz_2", "male_punkty"]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status": "Wynik meczu",
            "sezon": "Sezon",
            "kolejka_nazwa": "Kolejka",
            "liga": "Liga/Grupa",
            "gracz_1": "Gracz 1",
            "Wynik_Sety": "Sety",
            "gracz_2": "Gracz 2",
            "male_punkty": "Małe punkty",
        },
    )

# --- SEKCJA 3: GRACZ VS GRACZ (H2H) ---
elif menu == "H2H (Pojedynek)":
    st.title("⚔️ Head to Head")
    st.caption(f"Sezon: {selected_sezon}")
    col1, col2 = st.columns(2)
    with col1:
        g1 = st.selectbox("Gracz 1:", wszyscy_gracze, index=0)
    with col2:
        g2 = st.selectbox(
            "Gracz 2:", wszyscy_gracze, index=1 if len(wszyscy_gracze) > 1 else 0
        )

    h2h = df_sezon[
        ((df_sezon["gracz_1"] == g1) & (df_sezon["gracz_2"] == g2))
        | ((df_sezon["gracz_1"] == g2) & (df_sezon["gracz_2"] == g1))
    ].copy()

    if h2h.empty:
        st.warning(f"Gracze {g1} i {g2} jeszcze ze sobą nie grali.")
    else:
        g1_match_wins = 0
        g2_match_wins = 0
        g1_set_wins = 0
        g2_set_wins = 0
        g1_point_wins = 0
        g2_point_wins = 0

        for _, row in h2h.iterrows():
            is_g1_first = row["gracz_1"] == g1

            if row["Zwyciezca"] == g1:
                g1_match_wins += 1
            else:
                g2_match_wins += 1

            if is_g1_first:
                g1_set_wins += row["sety_g1"]
                g2_set_wins += row["sety_g2"]
            else:
                g1_set_wins += row["sety_g2"]
                g2_set_wins += row["sety_g1"]

            for s in row["szczegoly_setow"] or []:
                p1, p2 = s["punkty_gracz_1"], s["punkty_gracz_2"]
                if is_g1_first:
                    g1_point_wins += p1
                    g2_point_wins += p2
                else:
                    g1_point_wins += p2
                    g2_point_wins += p1

        st.subheader("📊 Porównanie statystyk")

        comparison_data = {
            "Statystyka": ["Wygrane mecze", "Wygrane sety", "Zdobyte małe punkty"],
            g1: [g1_match_wins, g1_set_wins, g1_point_wins],
            "vs": ["-", "-", "-"],
            g2: [g2_match_wins, g2_set_wins, g2_point_wins],
        }

        comp_df = pd.DataFrame(comparison_data)
        st.table(comp_df.set_index("Statystyka"))

        st.divider()

        fig_data = pd.DataFrame(
            {"Gracz": [g1, g2], "Zwycięstwa": [g1_match_wins, g2_match_wins]}
        )
        fig = px.pie(
            fig_data,
            values="Zwycięstwa",
            names="Gracz",
            title="Dominacja w meczach",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set1,
        )

        c_left, c_right = st.columns([1, 1])
        with c_left:
            st.plotly_chart(fig, use_container_width=True)
        with c_right:
            st.markdown("### Ostatnie spotkania")
            h2h_display = h2h[
                ["sezon", "kolejka_nazwa", "liga", "gracz_1", "Wynik_Sety", "gracz_2", "Zwyciezca"]
            ].copy()
            h2h_display = h2h_display.rename(columns={"Zwyciezca": "Zwycięzca 🏆"})
            st.dataframe(h2h_display, use_container_width=True, hide_index=True)

# --- SEKCJA 4: HISTORIA GRACZA (wszystkie sezony) ---
elif menu == "Historia Gracza":
    st.title("📈 Historia Gracza")
    st.caption("Ta zakładka pokazuje dane ze WSZYSTKICH załadowanych sezonów naraz")

    wszyscy_gracze_globalnie = sorted(
        list(set(df["gracz_1"].unique()) | set(df["gracz_2"].unique()))
    )
    gracz = st.selectbox("Wybierz gracza:", wszyscy_gracze_globalnie)

    mecze = df[(df["gracz_1"] == gracz) | (df["gracz_2"] == gracz)].copy()

    if mecze.empty:
        st.warning("Brak danych dla tego gracza.")
    else:
        mecze["wygrany"] = mecze["Zwyciezca"] == gracz

        c1, c2, c3 = st.columns(3)
        c1.metric("Mecze łącznie (wszystkie sezony)", len(mecze))
        c2.metric("Wygrane łącznie", int(mecze["wygrany"].sum()))
        c3.metric("Win Rate łącznie", f"{mecze['wygrany'].mean() * 100:.1f}%")

        podsumowanie = (
            mecze.groupby("sezon")
            .agg(Mecze=("wygrany", "count"), Wygrane=("wygrany", "sum"))
            .reset_index()
        )
        podsumowanie["Win Rate %"] = (
            podsumowanie["Wygrane"] / podsumowanie["Mecze"] * 100
        ).round(1)

        liga_per_sezon = (
            mecze.groupby("sezon")["liga"]
            .agg(lambda x: ", ".join(sorted(set(x))))
            .rename("Liga/Grupa")
        )
        podsumowanie = podsumowanie.merge(liga_per_sezon, on="sezon").rename(
            columns={"sezon": "Sezon"}
        )

        st.markdown("### Podsumowanie sezon po sezonie")
        st.dataframe(podsumowanie, use_container_width=True, hide_index=True)

        st.markdown("### Forma w czasie")
        fig = px.bar(
            podsumowanie,
            x="Sezon",
            y="Win Rate %",
            hover_data=["Mecze", "Wygrane", "Liga/Grupa"],
            title=f"Win rate gracza {gracz} w poszczególnych sezonach",
        )
        st.plotly_chart(fig, use_container_width=True)

# --- SEKCJA 5: RANKING WSZECHCZASÓW ---
elif menu == "Ranking Wszechczasów":
    st.title("🏅 Ranking Wszechczasów")
    st.caption(
        "Uwzględnia wszystkie załadowane sezony i ligi/grupy łącznie "
        "(np. gracz w EKSTRALIDZE i w 1 LIDZE w różnych sezonach liczy się razem)"
    )

    jako_gracz_1 = df[["gracz_1", "Zwyciezca"]].rename(columns={"gracz_1": "Gracz"})
    jako_gracz_2 = df[["gracz_2", "Zwyciezca"]].rename(columns={"gracz_2": "Gracz"})
    wszyscy = pd.concat([jako_gracz_1, jako_gracz_2], ignore_index=True)
    wszyscy["Wygrana"] = wszyscy["Gracz"] == wszyscy["Zwyciezca"]

    ranking = (
        wszyscy.groupby("Gracz")
        .agg(Mecze=("Wygrana", "count"), Wygrane=("Wygrana", "sum"))
        .reset_index()
    )
    ranking["Win Rate %"] = (ranking["Wygrane"] / ranking["Mecze"] * 100).round(1)
    ranking = ranking.sort_values(by=["Wygrane", "Win Rate %"], ascending=False)

    max_mecze = int(ranking["Mecze"].max()) if not ranking.empty else 1
    min_mecze = st.slider(
        "Minimalna liczba rozegranych meczów:", 1, max_mecze, min(5, max_mecze)
    )
    ranking_filtr = ranking[ranking["Mecze"] >= min_mecze].reset_index(drop=True)
    ranking_filtr.index = ranking_filtr.index + 1  # ranking od 1, nie od 0

    st.dataframe(ranking_filtr, use_container_width=True)