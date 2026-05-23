import streamlit as st
import pandas as pd
import json
import plotly.express as px

# Ustawienia strony
st.set_page_config(page_title="Hasta La Vista - Statystyki Ligi", layout="wide")

@st.cache_data
def load_data():
    try:
        with open("wyniki_ligi_full.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        # Przygotowanie czytelnego formatu wyniku setów raz dla całego df
        df['sety_g1'] = df['wynik_sety'].apply(lambda x: x['g1'])
        df['sety_g2'] = df['wynik_sety'].apply(lambda x: x['g2'])
        df['Wynik_Sety'] = df.apply(lambda x: f"{x['sety_g1']}:{x['sety_g2']}", axis=1)
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("Nie znaleziono pliku wyniki_ligi_full.json. Uruchom najpierw scraper.py!")
    st.stop()

# --- SIDEBAR ---
menu = st.sidebar.radio("Nawigacja", ["Wyniki Kolejki", "Statystyki Gracza", "H2H (Pojedynek)"])
wszyscy_gracze = sorted(list(set(df['gracz_1'].unique()) | set(df['gracz_2'].unique())))

# --- SEKCJA 1: WYNIKI KOLEJKI ---
if menu == "Wyniki Kolejki":
    st.title("🏆 Wyniki Kolejek i Grup")
    
    col1, col2 = st.columns(2)
    with col1:
        kolejki = sorted(df['kolejka_nazwa'].unique(), reverse=True)
        selected_kolejka = st.selectbox("Wybierz kolejkę:", kolejki)
    with col2:
        df_kolejka = df[df['kolejka_nazwa'] == selected_kolejka]
        ligi = sorted(df_kolejka['liga'].unique())
        selected_liga = st.selectbox("Wybierz ligę/grupę:", ligi)

    df_final = df_kolejka[df_kolejka['liga'] == selected_liga].copy()
    
    st.markdown("### 📊 Tabela ligowa")
    def calculate_standings(data):
        stats = {}
        for _, row in data.iterrows():
            p1, p2, s1, s2 = row['gracz_1'], row['gracz_2'], row['sety_g1'], row['sety_g2']
            for p in [p1, p2]:
                if p not in stats: stats[p] = {"Mecze": 0, "Wygrane": 0, "Sety +": 0, "Sety -": 0}
            stats[p1]["Mecze"] += 1; stats[p2]["Mecze"] += 1
            stats[p1]["Sety +"] += s1; stats[p1]["Sety -"] += s2
            stats[p2]["Sety +"] += s2; stats[p2]["Sety -"] += s1
            if s1 > s2: stats[p1]["Wygrane"] += 1
            else: stats[p2]["Wygrane"] += 1
        return pd.DataFrame.from_dict(stats, orient='index').reset_index().rename(columns={'index': 'Gracz'}).sort_values(by=['Wygrane', 'Sety +'], ascending=False)

    st.table(calculate_standings(df_final))
    st.markdown("### 🎾 Lista meczów")
    st.dataframe(df_final[['gracz_1', 'Wynik_Sety', 'gracz_2', 'male_punkty']], use_container_width=True, hide_index=True)

# --- SEKCJA 2: STATYSTYKI GRACZA ---
elif menu == "Statystyki Gracza":
    st.title("👤 Profil Zawodnika")
    gracz = st.selectbox("Wybierz gracza:", wszyscy_gracze)
    
    mecze_gracza = df[(df['gracz_1'] == gracz) | (df['gracz_2'] == gracz)].copy()
    
    total = len(mecze_gracza)
    wygrane = len(mecze_gracza[mecze_gracza['Zwyciezca'] == gracz])
    win_rate = (wygrane / total * 100) if total > 0 else 0
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Rozegrane mecze", total)
    c2.metric("Wygrane", wygrane)
    c3.metric("Win Rate", f"{win_rate:.1f}%")

    st.markdown("### Historia meczów")
    mecze_gracza['Status'] = mecze_gracza['Zwyciezca'].apply(lambda x: "✅" if x == gracz else "❌")
    
    # Wyświetlamy tabelę z dodaną kolumną 'liga'
    st.dataframe(
        mecze_gracza[['Status', 'kolejka_nazwa', 'liga', 'gracz_1', 'Wynik_Sety', 'gracz_2', 'male_punkty']], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Status": "Wynik meczu",
            "kolejka_nazwa": "Kolejka",
            "liga": "Liga/Grupa",
            "gracz_1": "Gracz 1",
            "Wynik_Sety": "Sety",
            "gracz_2": "Gracz 2",
            "male_punkty": "Małe punkty"
        }
    )

# --- SEKCJA 3: GRACZ VS GRACZ (H2H) ---
elif menu == "H2H (Pojedynek)":
    st.title("⚔️ Head to Head")
    col1, col2 = st.columns(2)
    with col1:
        g1 = st.selectbox("Gracz 1:", wszyscy_gracze, index=0)
    with col2:
        g2 = st.selectbox("Gracz 2:", wszyscy_gracze, index=1 if len(wszyscy_gracze)>1 else 0)
    
    h2h = df[((df['gracz_1'] == g1) & (df['gracz_2'] == g2)) | 
             ((df['gracz_1'] == g2) & (df['gracz_2'] == g1))].copy()
    
    if h2h.empty:
        st.warning(f"Gracze {g1} i {g2} jeszcze ze sobą nie grali.")
    else:
        g1_wins = len(h2h[h2h['Zwyciezca'] == g1])
        g2_wins = len(h2h[h2h['Zwyciezca'] == g2])
        
        # Wykres kołowy
        fig_data = pd.DataFrame({
            "Gracz": [g1, g2],
            "Zwycięstwa": [g1_wins, g2_wins]
        })
        fig = px.pie(fig_data, values='Zwycięstwa', names='Gracz', 
                     title=f"Rozkład zwycięstw: {g1} vs {g2}",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric(f"Wygrane {g1}", g1_wins)
            st.metric(f"Wygrane {g2}", g2_wins)
        with c2:
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### Historia bezpośrednich starć")
        # Wyświetlamy tabelę z dodaną kolumną 'liga'
        st.dataframe(
            h2h[['kolejka_nazwa', 'liga', 'gracz_1', 'Wynik_Sety', 'gracz_2', 'male_punkty']], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "kolejka_nazwa": "Kolejka",
                "liga": "Liga/Grupa",
                "gracz_1": "Gracz 1",
                "Wynik_Sety": "Sety",
                "gracz_2": "Gracz 2",
                "male_punkty": "Małe punkty"
            }
        )