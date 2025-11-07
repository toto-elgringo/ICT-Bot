"""
Interface Streamlit AVANCEE pour manager le bot de trading ICT
- Suivi temps reel
- Affichage des trades en cours
- Connexion MT5 directe
- Gestion des comptes MT5
- Backtest integre
"""

import streamlit as st
import subprocess
import os
import json
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import MT5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except:
    MT5_AVAILABLE = False
    st.error("MetaTrader5 n'est pas installe. Installez-le avec: pip install MetaTrader5")

# ===============================
# FONCTIONS UTILITAIRES
# ===============================

def save_config_to_file(config):
    """Sauvegarde la configuration dans un fichier JSON"""
    with open('bot_config.json', 'w') as f:
        json.dump(config, f, indent=4)

def load_mt5_credentials():
    """Charge les identifiants MT5 depuis un fichier"""
    if os.path.exists('mt5_credentials.json'):
        with open('mt5_credentials.json', 'r') as f:
            return json.load(f)
    # Fichier non trouvé - retourner valeurs vides
    return {"login": None, "password": None, "server": None}

def save_mt5_credentials(login, password, server):
    """Sauvegarde les identifiants MT5"""
    creds = {"login": login, "password": password, "server": server}
    with open('mt5_credentials.json', 'w') as f:
        json.dump(creds, f, indent=4)
    return creds

def connect_mt5(login, password, server):
    """Connexion a MT5"""
    if not MT5_AVAILABLE:
        return False, "MT5 non disponible"

    if mt5.initialize(login=login, password=password, server=server):
        return True, "Connexion reussie"
    else:
        error = mt5.last_error()
        return False, f"Erreur: {error}"

def get_mt5_account_info():
    """Recupere les infos du compte MT5"""
    if not MT5_AVAILABLE or not mt5.terminal_info():
        return None

    account = mt5.account_info()
    if account is None:
        return None

    return {
        'balance': account.balance,
        'equity': account.equity,
        'margin': account.margin,
        'free_margin': account.margin_free,
        'profit': account.profit,
        'currency': account.currency,
        'leverage': account.leverage,
        'name': account.name,
        'server': account.server,
        'login': account.login
    }

def get_open_positions():
    """Recupere les positions ouvertes sur MT5"""
    if not MT5_AVAILABLE or not mt5.terminal_info():
        return []

    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return []

    pos_list = []
    for pos in positions:
        pos_list.append({
            'ticket': pos.ticket,
            'symbol': pos.symbol,
            'type': 'BUY' if pos.type == 0 else 'SELL',
            'volume': pos.volume,
            'price_open': pos.price_open,
            'price_current': pos.price_current,
            'sl': pos.sl,
            'tp': pos.tp,
            'profit': pos.profit,
            'comment': pos.comment,
            'time': datetime.fromtimestamp(pos.time)
        })

    return pos_list

def get_recent_deals(hours=24):
    """Recupere les trades recents"""
    if not MT5_AVAILABLE or not mt5.terminal_info():
        return []

    from datetime import timedelta
    to_date = datetime.now()
    from_date = to_date - timedelta(hours=hours)

    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) == 0:
        return []

    deals_list = []
    for deal in deals:
        if deal.entry == 1:  # Entry deal
            deals_list.append({
                'ticket': deal.order,
                'symbol': deal.symbol,
                'type': 'BUY' if deal.type == 0 else 'SELL',
                'volume': deal.volume,
                'price': deal.price,
                'profit': deal.profit,
                'time': datetime.fromtimestamp(deal.time),
                'comment': deal.comment
            })

    return deals_list

def run_backtest_with_params(config, symbol, timeframe, bars):
    """Lance un backtest avec les parametres donnes"""
    # Lancer le backtest avec le nombre de barres specifie
    # Note: Le bot utilise les parametres de bot_config.json
    cmd = f'python ict_bot_all_in_one.py --mode backtest --symbol {symbol} --timeframe {timeframe} --bars {bars}'

    # Timeout adaptatif selon le nombre de barres
    # ~30 secondes par 100k barres + 5 minutes de marge
    timeout = max(1800, int(bars / 100000 * 30 + 300))

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)

    return result.returncode == 0, result.stdout, result.stderr

# ===============================
# Configuration de la page
# ===============================
st.set_page_config(
    page_title="ICT Trading Bot Manager v2",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialisation de la session state
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'bot_process' not in st.session_state:
    st.session_state.bot_process = None
if 'mt5_connected' not in st.session_state:
    st.session_state.mt5_connected = False
if 'mt5_credentials' not in st.session_state:
    st.session_state.mt5_credentials = load_mt5_credentials()

# Verifier si le processus du bot est toujours vivant
if st.session_state.bot_process is not None:
    if st.session_state.bot_process.poll() is not None:
        # Le processus s'est termine
        st.session_state.bot_running = False
        st.session_state.bot_process = None
        if 'bot_log_file' in st.session_state and st.session_state.bot_log_file:
            try:
                st.session_state.bot_log_file.close()
            except:
                pass
            st.session_state.bot_log_file = None

if 'config' not in st.session_state:
    st.session_state.config = {
        'RISK_PER_TRADE': 0.01,
        'RR_TAKE_PROFIT': 1.8,
        'MAX_CONCURRENT_TRADES': 2,
        'COOLDOWN_BARS': 5,
        'ML_THRESHOLD': 0.40,
        'USE_SESSION_ADAPTIVE_RR': True,
        'RR_LONDON': 1.2,
        'RR_NEWYORK': 1.5,
        'RR_DEFAULT': 1.3,
        'USE_ML_META_LABELLING': True,
        'MAX_ML_SAMPLES': 500,
        'USE_ATR_FILTER': True,
        'ATR_FVG_MIN_RATIO': 0.2,
        'ATR_FVG_MAX_RATIO': 2.5,
        'USE_CIRCUIT_BREAKER': True,
        'DAILY_DD_LIMIT': 0.03,
        'USE_ADAPTIVE_RISK': True,
        'SYMBOL': 'EURUSD',
        'TIMEFRAME': 'M5'
    }

# ===============================
# TITRE PRINCIPAL
# ===============================
st.title("🤖 ICT Trading Bot Manager v2.0")
st.markdown("### Centre de Controle Avance avec Suivi Temps Reel")
st.markdown("---")

# ===============================
# SIDEBAR - CONNEXION MT5
# ===============================
with st.sidebar:
    st.header("🔌 Connexion MT5")

    with st.expander("⚙️ Parametres de Connexion", expanded=not st.session_state.mt5_connected):
        mt5_login = st.number_input(
            "Login",
            value=st.session_state.mt5_credentials.get('login') or 0,
            step=1
        )
        mt5_password = st.text_input(
            "Password",
            value=st.session_state.mt5_credentials.get('password', ''),
            type="password"
        )
        mt5_server = st.text_input(
            "Server",
            value=st.session_state.mt5_credentials.get('server', '')
        )

        col_conn1, col_conn2 = st.columns(2)
        with col_conn1:
            if st.button("🔌 Connecter", use_container_width=True):
                success, msg = connect_mt5(mt5_login, mt5_password, mt5_server)
                if success:
                    st.session_state.mt5_connected = True
                    st.session_state.mt5_credentials = save_mt5_credentials(mt5_login, mt5_password, mt5_server)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with col_conn2:
            if st.button("💾 Sauvegarder", use_container_width=True):
                st.session_state.mt5_credentials = save_mt5_credentials(mt5_login, mt5_password, mt5_server)
                st.success("Sauvegarde OK")

    # Statut MT5
    if st.session_state.mt5_connected and MT5_AVAILABLE and mt5.terminal_info():
        st.success("✅ MT5 Connecte")
        account_info = get_mt5_account_info()
        if account_info:
            st.metric("Balance", f"${account_info['balance']:,.2f}")
            st.metric("Equity", f"${account_info['equity']:,.2f}")
            st.metric("Profit", f"${account_info['profit']:,.2f}")
    else:
        st.error("❌ MT5 Deconnecte")

    st.markdown("---")

    # ===============================
    # CONTROLES DU BOT
    # ===============================
    st.header("🎛️ Controles du Bot")

    if st.session_state.bot_running:
        if st.button("⏸️ PAUSE BOT", type="primary", use_container_width=True):
            if st.session_state.bot_process:
                st.session_state.bot_process.terminate()
                st.session_state.bot_process = None
            if 'bot_log_file' in st.session_state and st.session_state.bot_log_file:
                try:
                    st.session_state.bot_log_file.close()
                except:
                    pass
                st.session_state.bot_log_file = None
            st.session_state.bot_running = False
            st.success("Bot arrete")
            st.rerun()
    else:
        if st.button("▶️ START BOT", type="primary", use_container_width=True):
            if not st.session_state.mt5_connected:
                st.error("Connectez-vous d'abord a MT5 !")
            else:
                save_config_to_file(st.session_state.config)

                # Rediriger les logs vers un fichier avec unbuffered mode
                log_file = open('bot_live.log', 'w', buffering=1)
                st.session_state.bot_process = subprocess.Popen(
                    ["python", "-u", "ict_bot_all_in_one.py", "--mode", "live"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                st.session_state.bot_running = True
                st.session_state.bot_log_file = log_file
                st.success("Bot demarre - Attendez quelques secondes puis cliquez sur 'Rafraichir'")
                st.rerun()

    # Statut
    st.markdown("---")
    st.subheader("📊 Statut")
    if st.session_state.bot_running:
        st.success("✅ Bot EN COURS")
    else:
        st.error("❌ Bot ARRETE")

    st.info(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

    # Afficher les logs du bot si disponibles
    if st.session_state.bot_running or os.path.exists('bot_live.log'):
        with st.expander("📋 Logs du Bot", expanded=True):
            try:
                if os.path.exists('bot_live.log'):
                    # Forcer le flush du fichier de log si ouvert
                    if 'bot_log_file' in st.session_state and st.session_state.bot_log_file:
                        try:
                            st.session_state.bot_log_file.flush()
                            os.fsync(st.session_state.bot_log_file.fileno())
                        except:
                            pass

                    with open('bot_live.log', 'r', encoding='utf-8', errors='ignore') as f:
                        logs = f.read()
                        logs_stripped = logs.strip()
                        if logs_stripped:
                            # Afficher seulement les dernières 100 lignes
                            lines = logs.split('\n')
                            recent_logs = '\n'.join(lines[-100:])
                            st.code(recent_logs, language='text')
                        else:
                            st.info(f"Aucun log disponible pour le moment... (taille fichier: {len(logs)} bytes)")
                else:
                    st.info("Aucun log disponible")
            except Exception as e:
                st.warning(f"Impossible de lire les logs: {e}")

    if st.button("🔄 Rafraichir", use_container_width=True):
        st.rerun()

# ===============================
# ONGLETS PRINCIPAUX
# ===============================
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard Live", "⚙️ Parametres", "🧪 Backtest", "📈 Historique"])

# ===============================
# TAB 1: DASHBOARD LIVE
# ===============================
with tab1:
    st.header("📊 Dashboard Live")

    if not st.session_state.mt5_connected:
        st.warning("⚠️ Connectez-vous a MT5 pour voir les donnees en temps reel")
    else:
        # Infos compte
        account_info = get_mt5_account_info()
        if account_info:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Balance", f"${account_info['balance']:,.2f}")
            with col2:
                st.metric("Equity", f"${account_info['equity']:,.2f}")
            with col3:
                profit_delta = account_info['profit']
                st.metric("Profit", f"${profit_delta:,.2f}", delta=f"{profit_delta:,.2f}")
            with col4:
                st.metric("Marge Libre", f"${account_info['free_margin']:,.2f}")
            with col5:
                st.metric("Levier", f"1:{account_info['leverage']}")

        st.markdown("---")

        # Positions ouvertes
        st.subheader("📍 Positions Ouvertes")
        positions = get_open_positions()

        if len(positions) > 0:
            df_positions = pd.DataFrame(positions)
            df_positions['profit_color'] = df_positions['profit'].apply(
                lambda x: '🟢' if x > 0 else '🔴' if x < 0 else '⚪'
            )

            # Afficher les positions
            for idx, pos in enumerate(positions):
                with st.expander(
                    f"{pos['profit_color']} {pos['type']} {pos['symbol']} | "
                    f"Ticket: {pos['ticket']} | "
                    f"Profit: ${pos['profit']:,.2f}",
                    expanded=True
                ):
                    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
                    with col_p1:
                        st.metric("Volume", f"{pos['volume']:.2f} lots")
                        st.metric("Prix Entree", f"{pos['price_open']:.5f}")
                    with col_p2:
                        st.metric("Prix Actuel", f"{pos['price_current']:.5f}")
                        pips = (pos['price_current'] - pos['price_open']) * 10000
                        if pos['type'] == 'SELL':
                            pips = -pips
                        st.metric("Pips", f"{pips:,.1f}")
                    with col_p3:
                        st.metric("Stop Loss", f"{pos['sl']:.5f}" if pos['sl'] > 0 else "N/A")
                        st.metric("Take Profit", f"{pos['tp']:.5f}" if pos['tp'] > 0 else "N/A")
                    with col_p4:
                        st.metric("Profit", f"${pos['profit']:,.2f}")
                        st.caption(f"Ouvert: {pos['time'].strftime('%Y-%m-%d %H:%M')}")
        else:
            st.info("Aucune position ouverte")

        st.markdown("---")

        # Trades recents
        st.subheader("🕐 Trades Recents (24h)")
        deals = get_recent_deals(hours=24)

        if len(deals) > 0:
            df_deals = pd.DataFrame(deals)
            st.dataframe(
                df_deals[['time', 'symbol', 'type', 'volume', 'price', 'profit']],
                use_container_width=True,
                hide_index=True
            )

            # Stats rapides
            total_profit = df_deals['profit'].sum()
            winning_trades = len(df_deals[df_deals['profit'] > 0])
            total_trades = len(df_deals)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            col_st1, col_st2, col_st3 = st.columns(3)
            with col_st1:
                st.metric("Profit 24h", f"${total_profit:,.2f}")
            with col_st2:
                st.metric("Trades", total_trades)
            with col_st3:
                st.metric("Win Rate 24h", f"{win_rate:.1f}%")
        else:
            st.info("Aucun trade dans les dernieres 24h")

# ===============================
# TAB 2: PARAMETRES
# ===============================
with tab2:
    st.header("⚙️ Configuration du Bot")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("🎯 Risque & Money Management")
        st.session_state.config['RISK_PER_TRADE'] = st.slider(
            "Risque par trade (%)",
            min_value=0.001,
            max_value=0.05,
            value=st.session_state.config['RISK_PER_TRADE'],
            step=0.001,
            format="%.3f"
        )

        st.session_state.config['RR_TAKE_PROFIT'] = st.slider(
            "Risk/Reward",
            min_value=1.0,
            max_value=3.0,
            value=st.session_state.config['RR_TAKE_PROFIT'],
            step=0.1
        )

        st.session_state.config['MAX_CONCURRENT_TRADES'] = st.slider(
            "Max trades concurrents",
            min_value=1,
            max_value=5,
            value=st.session_state.config['MAX_CONCURRENT_TRADES']
        )

        st.session_state.config['COOLDOWN_BARS'] = st.slider(
            "Cooldown (barres)",
            min_value=1,
            max_value=20,
            value=st.session_state.config['COOLDOWN_BARS']
        )

    with col2:
        st.subheader("🧠 Machine Learning")
        st.session_state.config['USE_ML_META_LABELLING'] = st.checkbox(
            "Activer ML Meta-Labelling",
            value=st.session_state.config['USE_ML_META_LABELLING']
        )

        if st.session_state.config['USE_ML_META_LABELLING']:
            st.session_state.config['ML_THRESHOLD'] = st.slider(
                "Seuil ML",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.config['ML_THRESHOLD'],
                step=0.05
            )

            st.session_state.config['MAX_ML_SAMPLES'] = st.slider(
                "Max echantillons ML",
                min_value=100,
                max_value=1000,
                value=st.session_state.config['MAX_ML_SAMPLES'],
                step=50
            )

        st.subheader("📈 RR Adaptatif")
        st.session_state.config['USE_SESSION_ADAPTIVE_RR'] = st.checkbox(
            "RR adaptatif par session",
            value=st.session_state.config['USE_SESSION_ADAPTIVE_RR']
        )

        if st.session_state.config['USE_SESSION_ADAPTIVE_RR']:
            st.session_state.config['RR_LONDON'] = st.slider(
                "RR London", 1.0, 2.5, st.session_state.config['RR_LONDON'], 0.1
            )
            st.session_state.config['RR_NEWYORK'] = st.slider(
                "RR New York", 1.0, 2.5, st.session_state.config['RR_NEWYORK'], 0.1
            )

    with col3:
        st.subheader("🔧 Filtres & Protection")
        st.session_state.config['USE_ATR_FILTER'] = st.checkbox(
            "Filtre ATR",
            value=st.session_state.config['USE_ATR_FILTER']
        )

        if st.session_state.config['USE_ATR_FILTER']:
            st.session_state.config['ATR_FVG_MIN_RATIO'] = st.slider(
                "ATR Min", 0.1, 1.0, st.session_state.config['ATR_FVG_MIN_RATIO'], 0.05
            )
            st.session_state.config['ATR_FVG_MAX_RATIO'] = st.slider(
                "ATR Max", 1.0, 5.0, st.session_state.config['ATR_FVG_MAX_RATIO'], 0.1
            )

        st.session_state.config['USE_CIRCUIT_BREAKER'] = st.checkbox(
            "Circuit Breaker",
            value=st.session_state.config['USE_CIRCUIT_BREAKER']
        )

        if st.session_state.config['USE_CIRCUIT_BREAKER']:
            st.session_state.config['DAILY_DD_LIMIT'] = st.slider(
                "Limite DD journalier",
                0.01, 0.10, st.session_state.config['DAILY_DD_LIMIT'], 0.01,
                format="%.2f"
            )

        st.session_state.config['USE_ADAPTIVE_RISK'] = st.checkbox(
            "Risque Adaptatif",
            value=st.session_state.config['USE_ADAPTIVE_RISK']
        )

    st.markdown("---")
    if st.button("💾 Sauvegarder la Configuration", type="secondary", use_container_width=True):
        save_config_to_file(st.session_state.config)
        st.success("Configuration sauvegardee !")

# ===============================
# TAB 3: BACKTEST
# ===============================
with tab3:
    st.header("🧪 Backtester avec Parametres Actuels")

    col_bt1, col_bt2, col_bt3 = st.columns(3)

    with col_bt1:
        bt_symbol = st.selectbox(
            "Symbole",
            ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'],
            index=0
        )

    with col_bt2:
        bt_timeframe = st.selectbox(
            "Timeframe",
            ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
            index=1
        )

    with col_bt3:
        bt_bars = st.number_input(
            "Nombre de barres",
            min_value=1000,
            max_value=1000000,
            value=100000,
            step=1000
        )

    st.info("ℹ️ Le backtest utilisera les parametres configures dans l'onglet 'Parametres'")

    if st.button("🚀 Lancer le Backtest", type="primary", use_container_width=True):
        with st.spinner("Backtest en cours... Cela peut prendre quelques minutes..."):
            success, stdout, stderr = run_backtest_with_params(
                st.session_state.config,
                bt_symbol,
                bt_timeframe,
                bt_bars
            )

            if success:
                st.success("✅ Backtest termine avec succes !")
                st.text_area("Output", stdout, height=300)
            else:
                st.error("❌ Erreur lors du backtest")
                st.text_area("Erreur", stderr, height=200)

# ===============================
# TAB 4: HISTORIQUE
# ===============================
with tab4:
    st.header("📈 Historique des Backtests")

    # Charger tous les backtests depuis le dossier backtest/
    backtest_dir = 'backtest'
    if os.path.exists(backtest_dir):
        backtest_files = sorted(
            [os.path.join(backtest_dir, f) for f in os.listdir(backtest_dir)
             if f.startswith('backtest_') and f.endswith('.json')],
            reverse=True
        )
    else:
        backtest_files = []

    if backtest_files:
        # Section 1: Consultation individuelle avec suppression
        st.subheader("🔍 Consulter un Backtest")

        col_select, col_delete = st.columns([4, 1])
        with col_select:
            selected_bt = st.selectbox("Selectionner un backtest", backtest_files, key="select_bt_single")
        with col_delete:
            st.write("")  # Spacer pour alignement
            st.write("")  # Spacer pour alignement
            if st.button("🗑️ Supprimer", type="secondary", key="delete_single"):
                try:
                    os.remove(selected_bt)
                    st.success(f"✅ Backtest supprimé: {os.path.basename(selected_bt)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erreur lors de la suppression: {e}")

        try:
            with open(selected_bt, 'r') as f:
                backtest_data = json.load(f)

            # Metriques - gestion des deux formats de JSON
            # Nouveau format : donnees dans 'metrics'
            # Ancien format : donnees a la racine
            if 'metrics' in backtest_data:
                metrics = backtest_data['metrics']
                trades = metrics.get('trades', 0)
                winrate = metrics.get('winrate', 0)
                pnl = metrics.get('pnl', 0)
                max_dd = metrics.get('max_dd', 0)
            else:
                trades = backtest_data.get('trades', 0)
                winrate = backtest_data.get('winrate', 0)
                pnl = backtest_data.get('pnl', 0)
                max_dd = backtest_data.get('max_dd', 0)

            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            with col_h1:
                st.metric("Trades", trades)
            with col_h2:
                st.metric("Win Rate", f"{winrate:.2f}%")
            with col_h3:
                st.metric("PnL", f"${pnl:,.2f}")
            with col_h4:
                st.metric("Max DD", f"{max_dd:.2f}%")
        except json.JSONDecodeError:
            st.error(f"Erreur: Le fichier {selected_bt} est vide ou corrompu")
            st.warning("Ce fichier de backtest n'est pas valide. Lancez un nouveau backtest.")
            backtest_data = None

        # Equity curve
        if backtest_data and 'equity_curve' in backtest_data:
            st.subheader("Courbe d'Equity")
            equity_df = pd.DataFrame(backtest_data['equity_curve'])

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=equity_df.index,
                y=equity_df['equity'],
                mode='lines',
                name='Equity',
                line=dict(color='green', width=2)
            ))

            fig.update_layout(
                xaxis_title="Trade",
                yaxis_title="Equity ($)",
                hovermode='x unified',
                height=400
            )

            st.plotly_chart(fig, use_container_width=True)

        # Section 2: Comparaison de backtests
        st.markdown("---")
        st.subheader("📊 Comparer des Backtests")

        # Créer un mapping entre noms courts et chemins complets
        # Format attendu: backtest_SYMBOL_TIMEFRAME_YYYYMMDD_HHMMSS.json
        backtest_mapping = {}
        for bt_file in backtest_files:
            filename = os.path.basename(bt_file)
            # Extraire SYMBOL_TIMEFRAME du nom de fichier
            if filename.startswith('backtest_') and filename.endswith('.json'):
                parts = filename.replace('backtest_', '').replace('.json', '').split('_')
                if len(parts) >= 4:
                    # Les 2 premières parties sont SYMBOL et TIMEFRAME
                    short_name = f"{parts[0]}_{parts[1]}"
                    # Si le même nom court existe, ajouter la date/heure pour le différencier
                    if short_name in backtest_mapping:
                        short_name = f"{parts[0]}_{parts[1]} ({parts[2]}_{parts[3]})"
                    backtest_mapping[short_name] = bt_file

        # Multiselect avec noms courts
        selected_short_names = st.multiselect(
            "Sélectionnez les backtests à comparer",
            list(backtest_mapping.keys()),
            default=[],
            key="compare_backtests"
        )

        if selected_short_names:
            # Récupérer les chemins complets à partir des noms courts
            selected_backtests = [backtest_mapping[name] for name in selected_short_names]

            # Créer un mapping inversé (chemin -> nom court)
            inverse_mapping = {v: k for k, v in backtest_mapping.items()}

            # Créer le tableau de comparaison
            comparison_data = []

            for bt_file in selected_backtests:
                try:
                    with open(bt_file, 'r') as f:
                        bt_data = json.load(f)

                    # Extraire les métriques
                    if 'metrics' in bt_data:
                        metrics = bt_data['metrics']
                        trades = metrics.get('trades', 0)
                        winrate = metrics.get('winrate', 0)
                        pnl = metrics.get('pnl', 0)
                        max_dd = metrics.get('max_dd', 0)
                    else:
                        trades = bt_data.get('trades', 0)
                        winrate = bt_data.get('winrate', 0)
                        pnl = bt_data.get('pnl', 0)
                        max_dd = bt_data.get('max_dd', 0)

                    # Utiliser le nom court dans le tableau
                    short_name = inverse_mapping.get(bt_file, os.path.basename(bt_file))

                    # Ajouter au tableau
                    comparison_data.append({
                        'Backtest': short_name,
                        'Trades': trades,
                        'Win Rate (%)': f"{winrate:.2f}",
                        'PnL ($)': f"{pnl:,.2f}",
                        'Max DD (%)': f"{max_dd:.2f}"
                    })

                except (json.JSONDecodeError, FileNotFoundError):
                    short_name = inverse_mapping.get(bt_file, os.path.basename(bt_file))
                    st.warning(f"⚠️ Impossible de charger: {short_name}")

            if comparison_data:
                # Créer le DataFrame et afficher le tableau
                comparison_df = pd.DataFrame(comparison_data)

                st.dataframe(
                    comparison_df,
                    use_container_width=True,
                    hide_index=True
                )

                st.info(f"📈 {len(comparison_data)} backtest(s) comparé(s)")
            else:
                st.warning("Aucun backtest valide sélectionné pour la comparaison")
        else:
            st.info("👆 Sélectionnez au moins un backtest pour commencer la comparaison")
    else:
        st.warning("Aucun backtest disponible")

# Footer
st.markdown("---")
st.markdown("🤖 **ICT Trading Bot Manager v2.0** - Interface Avancee avec Suivi Temps Reel")
