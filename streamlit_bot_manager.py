"""
Interface Streamlit AVANCEE pour manager le bot de trading ICT
- Gestion multi-bots
- Suivi temps reel
- Affichage des trades en cours
- Connexion MT5 directe par bot
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
import uuid

# Import MT5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except:
    MT5_AVAILABLE = False
    st.error("MetaTrader5 n'est pas installe. Installez-le avec: pip install MetaTrader5")

# Import Grid Search Engine (version batch optimisée uniquement)
try:
    from grid_search_engine_batch import (
        run_grid_search_batch as run_grid_search,
        save_top_results,
        generate_all_combinations
    )
    GRID_SEARCH_AVAILABLE = True
except ImportError:
    GRID_SEARCH_AVAILABLE = False
    st.error("⚠️ Fichier grid_search_engine_batch.py manquant!")

# ===============================
# GESTION DES CONFIGURATIONS
# ===============================

def ensure_config_directory():
    """Crée le dossier config/ s'il n'existe pas"""
    if not os.path.exists('config'):
        os.makedirs('config')

def create_default_config():
    """Crée la configuration par défaut si elle n'existe pas"""
    ensure_config_directory()
    default_config_path = 'config/Default.json'

    if not os.path.exists(default_config_path):
        default_config = {
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
            # v2.0 ICT Strategy Enhancements
            'USE_BOS_RECENCY_FILTER': True,
            'BOS_MAX_AGE': 20,
            'USE_FVG_MITIGATION_FILTER': True,
            'USE_MARKET_STRUCTURE_FILTER': True,
            'FVG_BOS_MAX_DISTANCE': 20,
            'USE_ORDER_BLOCK_SL': True,
            'USE_EXTREME_VOLATILITY_FILTER': True,
            'VOLATILITY_MULTIPLIER_MAX': 3.0
        }
        with open(default_config_path, 'w') as f:
            json.dump(default_config, f, indent=4)

    return default_config_path

def load_configs_list():
    """Retourne la liste des noms de configurations disponibles"""
    ensure_config_directory()
    create_default_config()  # Créer Default si inexistant

    configs = []
    for file in os.listdir('config'):
        if file.endswith('.json'):
            configs.append(file.replace('.json', ''))

    return sorted(configs)

def load_config_by_name(config_name):
    """Charge une configuration par son nom"""
    config_path = f'config/{config_name}.json'

    if not os.path.exists(config_path):
        # Si la config n'existe pas, créer Default et la retourner
        create_default_config()
        config_path = 'config/Default.json'

    with open(config_path, 'r') as f:
        return json.load(f)

def save_config_by_name(config_name, config):
    """Sauvegarde une configuration avec un nom donné"""
    ensure_config_directory()
    config_path = f'config/{config_name}.json'

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

def delete_config(config_name):
    """Supprime une configuration (sauf Default)"""
    if config_name == 'Default':
        return False, "Impossible de supprimer la configuration Default"

    config_path = f'config/{config_name}.json'

    if os.path.exists(config_path):
        os.remove(config_path)
        return True, f"Configuration '{config_name}' supprimée"
    else:
        return False, f"Configuration '{config_name}' introuvable"

def get_bots_using_config(config_name):
    """Retourne la liste des bots qui utilisent une config donnée"""
    bots_config = load_bots_config()
    bots_using = []

    for bot in bots_config.get('bots', []):
        if bot.get('config_name') == config_name:
            bots_using.append(bot['name'])

    return bots_using

# ===============================
# GESTION DES MODÈLES ML
# ===============================

def ensure_ml_directory():
    """Crée le dossier machineLearning/ s'il n'existe pas"""
    if not os.path.exists('machineLearning'):
        os.makedirs('machineLearning')

def get_ml_model_path(bot_name):
    """Retourne le chemin du fichier .pkl pour un bot donné"""
    ensure_ml_directory()
    # Nettoyer le nom du bot pour le nom de fichier (supprimer les caractères spéciaux)
    safe_name = "".join(c for c in bot_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_name = safe_name.replace(' ', '_')
    return f'machineLearning/{safe_name}.pkl'

def delete_ml_model(bot_name):
    """Supprime le fichier .pkl d'un bot"""
    ml_path = get_ml_model_path(bot_name)
    if os.path.exists(ml_path):
        try:
            os.remove(ml_path)
            return True, f"Modèle ML '{ml_path}' supprimé"
        except Exception as e:
            return False, f"Erreur lors de la suppression du modèle ML: {e}"
    return True, "Aucun modèle ML à supprimer"

# ===============================
# GESTION DES LOGS
# ===============================

def ensure_log_directory():
    """Crée le dossier log/ s'il n'existe pas"""
    if not os.path.exists('log'):
        os.makedirs('log')

def get_log_file_path(bot_id):
    """Retourne le chemin du fichier de log pour un bot donné"""
    ensure_log_directory()
    return f'log/bot_{bot_id}_live.log'

def delete_log_file(bot_id):
    """Supprime le fichier de log d'un bot"""
    log_path = get_log_file_path(bot_id)
    if os.path.exists(log_path):
        try:
            os.remove(log_path)
            return True, f"Fichier de log '{log_path}' supprimé"
        except Exception as e:
            return False, f"Erreur lors de la suppression du log: {e}"
    return True, "Aucun fichier de log à supprimer"

def load_bots_config():
    """Charge la configuration des bots"""
    if os.path.exists('bots_config.json'):
        with open('bots_config.json', 'r') as f:
            return json.load(f)
    return {"bots": []}

def save_bots_config(bots_config):
    """Sauvegarde la configuration des bots"""
    with open('bots_config.json', 'w') as f:
        json.dump(bots_config, f, indent=4)

def add_bot(name, login, password, server, symbol, timeframe, config_name):
    """Ajoute un nouveau bot"""
    bots_config = load_bots_config()
    bot_id = str(uuid.uuid4())[:8]

    new_bot = {
        "id": bot_id,
        "name": name,
        "login": login,
        "password": password,
        "server": server,
        "symbol": symbol,
        "timeframe": timeframe,
        "config_name": config_name
    }

    bots_config["bots"].append(new_bot)
    save_bots_config(bots_config)
    return bot_id

def remove_bot(bot_id):
    """Supprime un bot, son modèle ML associé et son fichier de log"""
    bots_config = load_bots_config()

    # Récupérer le nom du bot avant de le supprimer
    bot_name = None
    for bot in bots_config["bots"]:
        if bot["id"] == bot_id:
            bot_name = bot["name"]
            break

    # Supprimer le bot de la config
    bots_config["bots"] = [b for b in bots_config["bots"] if b["id"] != bot_id]
    save_bots_config(bots_config)

    # Supprimer le modèle ML associé
    if bot_name:
        delete_ml_model(bot_name)

    # Supprimer le fichier de log associé
    delete_log_file(bot_id)

def update_bot(bot_id, name, login, password, server, symbol, timeframe, config_name):
    """Met à jour les informations d'un bot"""
    bots_config = load_bots_config()
    for bot in bots_config["bots"]:
        if bot["id"] == bot_id:
            bot["name"] = name
            bot["login"] = login
            bot["password"] = password
            bot["server"] = server
            bot["symbol"] = symbol
            bot["timeframe"] = timeframe
            bot["config_name"] = config_name
            break
    save_bots_config(bots_config)
    return True

def connect_mt5_bot(login, password, server):
    """Connexion a MT5 pour un bot specifique"""
    if not MT5_AVAILABLE:
        return False, "MT5 non disponible"

    # Fermer toute connexion existante
    mt5.shutdown()

    if mt5.initialize(login=int(login), password=password, server=server):
        return True, "Connexion reussie"
    else:
        error = mt5.last_error()
        return False, f"Erreur: {error}"

def get_mt5_account_info_bot(login, password, server):
    """Recupere les infos du compte MT5 pour un bot specifique"""
    if not MT5_AVAILABLE:
        return None

    # Se connecter au compte specifique
    success, msg = connect_mt5_bot(login, password, server)
    if not success:
        return None

    account = mt5.account_info()
    if account is None:
        return None

    info = {
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

    mt5.shutdown()
    return info

def get_open_positions_bot(login, password, server):
    """Recupere les positions ouvertes pour un bot specifique"""
    if not MT5_AVAILABLE:
        return []

    # Se connecter au compte specifique
    success, msg = connect_mt5_bot(login, password, server)
    if not success:
        return []

    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        mt5.shutdown()
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

    mt5.shutdown()
    return pos_list

def run_backtest_with_params(config_name, symbol, timeframe, bars):
    """Lance un backtest avec la configuration specifiee"""
    # Utiliser une liste d'arguments au lieu d'une string pour éviter les problèmes de parsing
    cmd = [
        'python',
        'ict_bot_all_in_one.py',
        '--mode', 'backtest',
        '--symbol', str(symbol),
        '--timeframe', str(timeframe),
        '--bars', str(bars),
        '--config-name', str(config_name)
    ]

    # Timeout adaptatif selon le nombre de barres
    # ~30 secondes par 100k barres + 5 minutes de marge
    timeout = max(1800, int(bars / 100000 * 30 + 300))

    # Ne PAS utiliser shell=True pour éviter les problèmes de parsing
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

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

# Initialisation de la session state pour multi-bots
if 'bots' not in st.session_state:
    st.session_state.bots = {}  # Dictionnaire: {bot_id: {process, log_file, running}}

if 'bots_config' not in st.session_state:
    st.session_state.bots_config = load_bots_config()

if 'editing_bot_id' not in st.session_state:
    st.session_state.editing_bot_id = None  # ID du bot en cours d'édition

# Verifier si les processus des bots sont toujours vivants
for bot_id in list(st.session_state.bots.keys()):
    bot_state = st.session_state.bots[bot_id]
    if bot_state['process'] is not None:
        if bot_state['process'].poll() is not None:
            # Le processus s'est termine
            bot_state['running'] = False
            bot_state['process'] = None
            if bot_state.get('log_file'):
                try:
                    bot_state['log_file'].close()
                except:
                    pass
                bot_state['log_file'] = None

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
        # v2.0 ICT Strategy Enhancements
        'USE_BOS_RECENCY_FILTER': True,
        'BOS_MAX_AGE': 20,
        'USE_FVG_MITIGATION_FILTER': True,
        'USE_MARKET_STRUCTURE_FILTER': True,
        'FVG_BOS_MAX_DISTANCE': 20,
        'USE_ORDER_BLOCK_SL': True,
        'USE_EXTREME_VOLATILITY_FILTER': True,
        'VOLATILITY_MULTIPLIER_MAX': 3.0,
        'SYMBOL': 'EURUSD',
        'TIMEFRAME': 'M5'
    }

# ===============================
# TITRE PRINCIPAL
# ===============================
st.title("🤖 ICT Trading Bot Manager v2.0")
st.markdown("### Centre de Controle Avance avec Suivi Temps Reel")

# ===============================
# V2.0 MIGRATION WARNING BANNER
# ===============================
with st.expander("⚠️ ICT Bot v2.0 - Breaking Change - LIRE AVANT UTILISATION", expanded=False):
    st.warning("""
**La stratégie a été mise à niveau vers v2.0 avec 12 features ML (vs 5 en v1.0).**

### Action Requise
Supprimez tous les fichiers `.pkl` dans le dossier `machineLearning/` avant de relancer les bots existants.

**Pourquoi ?** Les modèles ML v1.0 sont incompatibles avec v2.0 (5 features → 12 features).

### Nouvelles Fonctionnalités v2.0
- ✅ **Validation de récence des BOS** - Seuls les BOS récents (< 20 barres) sont utilisés
- ✅ **Tracking de mitigation des FVG** - Ignore les FVG déjà touchés par le prix
- ✅ **Détection de structure de marché** - Valide HH/HL (haussier) ou LL/LH (baissier)
- ✅ **Confluence temporelle stricte** - FVG et BOS doivent être < 20 barres de distance
- ✅ **Order Blocks pour Stop Loss** - Utilise les Order Blocks au lieu des swing points
- ✅ **Filtre de volatilité extrême** - Protection contre les news (ATR > 3× médiane)

### Résultats v2.0 (EURUSD M5, 14.5 mois)
- 📈 Win Rate: **59-63%** (+10% vs v1.0)
- 📉 Max Drawdown: **-8% à -10%** (-7% amélioration vs v1.0)
- 📊 Trades: **170-210** (-35% volume - qualité > quantité)
- 🎯 12 features ML pour meilleure détection de marché

### Migration
1. Arrêtez tous les bots
2. Supprimez `machineLearning/*.pkl` (Windows: `del machineLearning\\*.pkl` | Linux/Mac: `rm machineLearning/*.pkl`)
3. Redémarrez les bots (les modèles ML se recréeront automatiquement)
""")

    st.info("💡 **Astuce**: Les nouveaux paramètres v2.0 sont dans l'onglet 'Paramètres' → Section 'Filtres ICT v2.0'")

st.markdown("---")

# ===============================
# SIDEBAR - INFORMATIONS
# ===============================
with st.sidebar:
    st.header("📊 Informations")

    # Compter les bots actifs
    active_bots = sum(1 for bot_id in st.session_state.bots if st.session_state.bots[bot_id].get('running', False))
    total_bots = len(st.session_state.bots_config.get('bots', []))

    st.metric("Bots Configures", total_bots)
    st.metric("Bots Actifs", active_bots)

    st.markdown("---")

    st.info(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

    if st.button("🔄 Rafraichir", use_container_width=True):
        st.rerun()

# ===============================
# ONGLETS PRINCIPAUX
# ===============================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🤖 Gestion des Bots", "⚙️ Parametres", "🧪 Backtest", "📈 Historique", "🔬 Grid Testing"])

# ===============================
# TAB 1: GESTION DES BOTS
# ===============================
with tab1:
    st.header("🤖 Gestion des Bots")

    # ===============================
    # SECTION: AJOUTER UN BOT
    # ===============================
    with st.expander("➕ Ajouter un nouveau bot", expanded=len(st.session_state.bots_config.get('bots', [])) == 0):
        st.subheader("Configuration du nouveau bot")

        # Charger la liste des configs disponibles
        available_configs = load_configs_list()

        col_form1, col_form2 = st.columns(2)

        with col_form1:
            bot_name = st.text_input("Nom du bot", placeholder="Ex: Bot EURUSD", key="add_bot_name")
            bot_login = st.number_input("Login MT5", min_value=0, step=1, value=0, key="add_bot_login")
            bot_password = st.text_input("Password MT5", type="password", key="add_bot_password")
            bot_server = st.text_input("Server MT5", placeholder="Ex: FusionMarkets-Demo", key="add_bot_server")

        with col_form2:
            bot_symbol = st.selectbox(
                "Symbole",
                ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'ETHUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'],
                key="add_bot_symbol"
            )
            bot_timeframe = st.selectbox("Timeframe", ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'], index=1, key="add_bot_timeframe")
            bot_config = st.selectbox(
                "⚙️ Configuration",
                available_configs,
                index=0 if 'Default' in available_configs else 0,
                key="add_bot_config",
                help="Sélectionnez la stratégie de trading à utiliser"
            )

        col_btn1, col_btn2 = st.columns([1, 3])
        with col_btn1:
            if st.button("✅ Ajouter le Bot", type="primary", use_container_width=True, key="add_bot_button"):
                if not bot_name or not bot_password or not bot_server:
                    st.error("⚠️ Veuillez remplir tous les champs")
                elif bot_login == 0:
                    st.error("⚠️ Le login MT5 doit être valide")
                else:
                    # Tester la connexion MT5
                    success, msg = connect_mt5_bot(bot_login, bot_password, bot_server)
                    if success:
                        bot_id = add_bot(bot_name, bot_login, bot_password, bot_server, bot_symbol, bot_timeframe, bot_config)
                        st.session_state.bots_config = load_bots_config()
                        st.session_state.bots[bot_id] = {'process': None, 'log_file': None, 'running': False}
                        st.success(f"✅ Bot '{bot_name}' ajouté avec succès avec la config '{bot_config}' ! (ID: {bot_id})")
                        mt5.shutdown()
                        st.rerun()
                    else:
                        st.error(f"❌ Impossible de se connecter à MT5: {msg}")

    st.markdown("---")

    # ===============================
    # SECTION: LISTE DES BOTS
    # ===============================
    st.subheader("📋 Liste des Bots")

    bots_list = st.session_state.bots_config.get('bots', [])

    if len(bots_list) == 0:
        st.info("👆 Aucun bot configuré. Ajoutez-en un ci-dessus !")
    else:
        for bot in bots_list:
            bot_id = bot['id']

            # Initialiser l'état du bot si nécessaire
            if bot_id not in st.session_state.bots:
                st.session_state.bots[bot_id] = {'process': None, 'log_file': None, 'running': False}

            bot_state = st.session_state.bots[bot_id]
            is_running = bot_state.get('running', False)

            # Créer un expander pour chaque bot
            status_icon = "🟢" if is_running else "⚪"
            status_text = "EN COURS" if is_running else "ARRETE"

            with st.expander(f"{status_icon} {bot['name']} - {bot['symbol']} ({bot['timeframe']}) - {status_text}", expanded=True):
                # Vérifier si ce bot est en cours d'édition
                is_editing = st.session_state.editing_bot_id == bot_id

                if is_editing:
                    # ===== MODE ÉDITION =====
                    st.markdown("### ✏️ Modifier le Bot")

                    # Charger la liste des configs disponibles
                    available_configs_edit = load_configs_list()
                    current_config = bot.get('config_name', 'Default')

                    col_edit1, col_edit2 = st.columns(2)

                    with col_edit1:
                        edit_name = st.text_input("Nom du bot", value=bot['name'], key=f"edit_name_{bot_id}")
                        edit_login = st.number_input("Login MT5", value=int(bot['login']), step=1, key=f"edit_login_{bot_id}")
                        edit_password = st.text_input("Password MT5", value=bot['password'], type="password", key=f"edit_password_{bot_id}")
                        edit_server = st.text_input("Server MT5", value=bot['server'], key=f"edit_server_{bot_id}")

                    with col_edit2:
                        edit_symbol = st.selectbox(
                            "Symbole",
                            ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'ETHUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'],
                            index=['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'ETHUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'].index(bot['symbol']) if bot['symbol'] in ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'] else 0,
                            key=f"edit_symbol_{bot_id}"
                        )
                        edit_timeframe = st.selectbox(
                            "Timeframe",
                            ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
                            index=['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'].index(bot['timeframe']) if bot['timeframe'] in ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'] else 1,
                            key=f"edit_timeframe_{bot_id}"
                        )
                        edit_config = st.selectbox(
                            "⚙️ Configuration",
                            available_configs_edit,
                            index=available_configs_edit.index(current_config) if current_config in available_configs_edit else 0,
                            key=f"edit_config_{bot_id}",
                            help="Sélectionnez la stratégie de trading à utiliser"
                        )

                    col_save, col_cancel = st.columns(2)

                    with col_save:
                        if st.button("💾 Sauvegarder", type="primary", use_container_width=True, key=f"save_edit_{bot_id}"):
                            if not edit_name or not edit_password or not edit_server:
                                st.error("⚠️ Veuillez remplir tous les champs")
                            elif edit_login == 0:
                                st.error("⚠️ Le login MT5 doit être valide")
                            else:
                                # Tester la connexion MT5
                                success, msg = connect_mt5_bot(edit_login, edit_password, edit_server)
                                if success:
                                    update_bot(bot_id, edit_name, edit_login, edit_password, edit_server, edit_symbol, edit_timeframe, edit_config)
                                    st.session_state.bots_config = load_bots_config()
                                    st.session_state.editing_bot_id = None
                                    st.success(f"✅ Bot '{edit_name}' mis à jour avec la config '{edit_config}' !")
                                    mt5.shutdown()
                                    st.rerun()
                                else:
                                    st.error(f"❌ Impossible de se connecter à MT5: {msg}")

                    with col_cancel:
                        if st.button("❌ Annuler", type="secondary", use_container_width=True, key=f"cancel_edit_{bot_id}"):
                            st.session_state.editing_bot_id = None
                            st.rerun()

                    st.markdown("---")

                else:
                    # ===== MODE AFFICHAGE =====
                    # Informations du bot
                    col_info1, col_info2, col_info3, col_info4, col_info5 = st.columns(5)

                    with col_info1:
                        st.metric("Nom", bot['name'])
                        st.caption(f"ID: {bot_id}")

                    with col_info2:
                        st.metric("Compte MT5", bot['login'])
                        st.caption(f"Server: {bot['server']}")

                    with col_info3:
                        st.metric("Symbole", bot['symbol'])
                        st.caption(f"Timeframe: {bot['timeframe']}")

                    with col_info4:
                        config_name = bot.get('config_name', 'Default')
                        st.metric("⚙️ Config", config_name)
                        st.caption("Stratégie de trading")

                    with col_info5:
                        if is_running:
                            st.success("✅ Bot actif")
                        else:
                            st.error("⏸️ Bot arrêté")

                    st.markdown("---")

                # Boutons de contrôle (seulement si pas en édition)
                if not is_editing:
                    col_btn1, col_btn2, col_btn3, col_btn4, col_btn5 = st.columns(5)

                    with col_btn1:
                        if is_running:
                            if st.button(f"⏸️ Arrêter", key=f"stop_{bot_id}", type="secondary", use_container_width=True):
                                if bot_state['process']:
                                    bot_state['process'].terminate()
                                    bot_state['process'] = None
                                if bot_state.get('log_file'):
                                    try:
                                        bot_state['log_file'].close()
                                    except:
                                        pass
                                    bot_state['log_file'] = None
                                bot_state['running'] = False
                                st.success(f"✅ Bot '{bot['name']}' arrêté")
                                st.rerun()
                        else:
                            if st.button(f"▶️ Démarrer", key=f"start_{bot_id}", type="primary", use_container_width=True):
                                # Récupérer le nom de la configuration du bot
                                config_name = bot.get('config_name', 'Default')

                                # Créer un fichier de credentials temporaire pour ce bot
                                temp_creds = {
                                    "login": bot['login'],
                                    "password": bot['password'],
                                    "server": bot['server']
                                }
                                with open('mt5_credentials.json', 'w') as f:
                                    json.dump(temp_creds, f, indent=4)

                                # Lancer le bot
                                log_file_path = get_log_file_path(bot_id)
                                log_file = open(log_file_path, 'w', buffering=1)

                                # Préparer le chemin du modèle ML pour ce bot
                                ml_model_path = get_ml_model_path(bot['name'])

                                process = subprocess.Popen(
                                    ["python", "-u", "ict_bot_all_in_one.py",
                                     "--mode", "live",
                                     "--symbol", bot['symbol'],
                                     "--timeframe", bot['timeframe'],
                                     "--bot-name", bot['name'],
                                     "--ml-model-path", ml_model_path,
                                     "--config-name", config_name],
                                    stdout=log_file,
                                    stderr=subprocess.STDOUT,
                                    text=True,
                                    bufsize=1
                                )

                                bot_state['process'] = process
                                bot_state['log_file'] = log_file
                                bot_state['running'] = True

                                st.success(f"✅ Bot '{bot['name']}' démarré avec la config '{config_name}' !")
                                st.rerun()

                    with col_btn2:
                        # Bouton Modifier (seulement si le bot n'est pas en cours d'exécution)
                        if not is_running:
                            if st.button(f"✏️ Modifier", key=f"edit_{bot_id}", use_container_width=True):
                                st.session_state.editing_bot_id = bot_id
                                st.rerun()
                        else:
                            st.empty()  # Espace vide si le bot est en cours

                    with col_btn3:
                        if st.button(f"🗑️ Supprimer", key=f"delete_{bot_id}", type="secondary", use_container_width=True):
                            # Arrêter le bot si en cours
                            if is_running:
                                if bot_state['process']:
                                    bot_state['process'].terminate()
                                if bot_state.get('log_file'):
                                    try:
                                        bot_state['log_file'].close()
                                    except:
                                        pass

                            # Supprimer le bot
                            remove_bot(bot_id)
                            del st.session_state.bots[bot_id]
                            st.session_state.bots_config = load_bots_config()
                            st.success(f"✅ Bot '{bot['name']}' supprimé")
                            st.rerun()

                    with col_btn4:
                        if st.button(f"📊 Infos MT5", key=f"info_{bot_id}", use_container_width=True):
                            with st.spinner("Connexion à MT5..."):
                                account_info = get_mt5_account_info_bot(bot['login'], bot['password'], bot['server'])
                            if account_info:
                                st.success("✅ Connexion MT5 réussie")

                                # Afficher les informations sur plusieurs lignes pour une meilleure lisibilité
                                st.markdown("#### 💰 Informations du Compte")

                                col_mt5_1, col_mt5_2 = st.columns(2)
                                with col_mt5_1:
                                    st.markdown(f"**Balance:** `${account_info['balance']:,.2f} {account_info['currency']}`")
                                    st.markdown(f"**Equity:** `${account_info['equity']:,.2f} {account_info['currency']}`")
                                    st.markdown(f"**Profit:** `${account_info['profit']:,.2f} {account_info['currency']}`")

                                with col_mt5_2:
                                    st.markdown(f"**Marge Utilisée:** `${account_info['margin']:,.2f} {account_info['currency']}`")
                                    st.markdown(f"**Marge Libre:** `${account_info['free_margin']:,.2f} {account_info['currency']}`")
                                    st.markdown(f"**Levier:** `1:{account_info['leverage']}`")
                            else:
                                st.error("❌ Impossible de se connecter à MT5")

                    with col_btn5:
                        if st.button(f"📍 Positions", key=f"positions_{bot_id}", use_container_width=True):
                            positions = get_open_positions_bot(bot['login'], bot['password'], bot['server'])
                            if len(positions) > 0:
                                st.write(f"**{len(positions)} position(s) ouverte(s)**")
                                for pos in positions:
                                    st.write(f"- {pos['type']} {pos['symbol']} | Volume: {pos['volume']} | Profit: ${pos['profit']:,.2f}")
                            else:
                                st.info("Aucune position ouverte")

                # Afficher les logs du bot (seulement si pas en édition)
                if not is_editing:
                    log_file_path = get_log_file_path(bot_id)
                    if os.path.exists(log_file_path):
                        with st.expander("📋 Logs du Bot", expanded=False):
                            try:
                                # Forcer le flush du fichier de log si ouvert
                                if bot_state.get('log_file'):
                                    try:
                                        bot_state['log_file'].flush()
                                        os.fsync(bot_state['log_file'].fileno())
                                    except:
                                        pass

                                with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    logs = f.read()
                                    logs_stripped = logs.strip()
                                    if logs_stripped:
                                        # Afficher seulement les dernières 50 lignes
                                        lines = logs.split('\n')
                                        recent_logs = '\n'.join(lines[-50:])
                                        st.code(recent_logs, language='text')
                                    else:
                                        st.info("Aucun log disponible pour le moment...")
                            except Exception as e:
                                st.warning(f"Impossible de lire les logs: {e}")

# ===============================
# TAB 2: GESTIONNAIRE DE CONFIGURATIONS
# ===============================
with tab2:
    st.header("⚙️ Gestionnaire de Configurations")

    # State pour l'édition de config
    if 'editing_config_name' not in st.session_state:
        st.session_state.editing_config_name = None
    if 'creating_new_config' not in st.session_state:
        st.session_state.creating_new_config = False

    # Charger la liste des configurations
    available_configs = load_configs_list()

    # ===============================
    # SECTION: CRÉER UNE NOUVELLE CONFIG
    # ===============================
    with st.expander("➕ Créer une nouvelle configuration", expanded=st.session_state.creating_new_config):
        new_config_name = st.text_input("Nom de la configuration", placeholder="Ex: Aggressive, Conservative, Scalping...", key="new_config_name")

        if st.button("✅ Créer", type="primary", key="create_new_config_button"):
            if not new_config_name:
                st.error("⚠️ Veuillez entrer un nom de configuration")
            elif new_config_name in available_configs:
                st.error(f"⚠️ Une configuration '{new_config_name}' existe déjà")
            else:
                # Créer une copie de la config par défaut
                default_config = load_config_by_name('Default')
                save_config_by_name(new_config_name, default_config)
                st.success(f"✅ Configuration '{new_config_name}' créée avec succès !")
                st.session_state.creating_new_config = False
                st.rerun()

    st.markdown("---")

    # ===============================
    # SECTION: LISTE DES CONFIGURATIONS
    # ===============================
    st.subheader("📋 Liste des Configurations")

    for config_name in available_configs:
        bots_using = get_bots_using_config(config_name)
        is_editing_config = st.session_state.editing_config_name == config_name

        with st.expander(f"⚙️ {config_name} - {len(bots_using)} bot(s)", expanded=is_editing_config):
            if is_editing_config:
                # ===== MODE ÉDITION =====
                st.markdown(f"### ✏️ Modifier la configuration '{config_name}'")

                # Charger la config
                config = load_config_by_name(config_name)

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.subheader("🎯 Risque & MM")
                    config['RISK_PER_TRADE'] = st.slider(
                        "Risque par trade (%)", 0.001, 0.05, config.get('RISK_PER_TRADE', 0.01), 0.001, format="%.3f", key=f"risk_{config_name}"
                    )
                    config['RR_TAKE_PROFIT'] = st.slider(
                        "Risk/Reward", 1.0, 3.0, config.get('RR_TAKE_PROFIT', 2.0), 0.1, key=f"rr_{config_name}"
                    )
                    config['MAX_CONCURRENT_TRADES'] = st.slider(
                        "Max trades", 1, 5, config.get('MAX_CONCURRENT_TRADES', 1), key=f"max_trades_{config_name}"
                    )
                    config['COOLDOWN_BARS'] = st.slider(
                        "Cooldown", 1, 20, config.get('COOLDOWN_BARS', 5), key=f"cooldown_{config_name}"
                    )

                with col2:
                    st.subheader("🧠 ML & RR Adaptatif")
                    config['USE_ML_META_LABELLING'] = st.checkbox(
                        "ML Meta-Labelling", config.get('USE_ML_META_LABELLING', False), key=f"ml_use_{config_name}"
                    )
                    if config['USE_ML_META_LABELLING']:
                        config['ML_THRESHOLD'] = st.slider(
                            "Seuil ML", 0.0, 1.0, config.get('ML_THRESHOLD', 0.5), 0.05, key=f"ml_thresh_{config_name}"
                        )
                        config['MAX_ML_SAMPLES'] = st.slider(
                            "Max samples ML", 100, 1000, config.get('MAX_ML_SAMPLES', 500), 50, key=f"ml_samples_{config_name}"
                        )

                    config['USE_SESSION_ADAPTIVE_RR'] = st.checkbox(
                        "RR adaptatif", config.get('USE_SESSION_ADAPTIVE_RR', False), key=f"rr_adapt_{config_name}"
                    )
                    if config['USE_SESSION_ADAPTIVE_RR']:
                        config['RR_LONDON'] = st.slider(
                            "RR London", 1.0, 2.5, config.get('RR_LONDON', 1.2), 0.1, key=f"rr_london_{config_name}"
                        )
                        config['RR_NEWYORK'] = st.slider(
                            "RR NY", 1.0, 2.5, config.get('RR_NEWYORK', 1.5), 0.1, key=f"rr_ny_{config_name}"
                        )
                        config['RR_DEFAULT'] = st.slider(
                            "RR Default", 1.0, 2.5, config.get('RR_DEFAULT', 1.3), 0.1, key=f"rr_default_{config_name}"
                        )

                with col3:
                    st.subheader("🔧 Filtres")
                    config['USE_ATR_FILTER'] = st.checkbox(
                        "Filtre ATR", config.get('USE_ATR_FILTER', False), key=f"atr_use_{config_name}"
                    )
                    if config['USE_ATR_FILTER']:
                        config['ATR_FVG_MIN_RATIO'] = st.slider(
                            "ATR Min", 0.1, 1.0, config.get('ATR_FVG_MIN_RATIO', 0.3), 0.05, key=f"atr_min_{config_name}"
                        )
                        config['ATR_FVG_MAX_RATIO'] = st.slider(
                            "ATR Max", 1.0, 5.0, config.get('ATR_FVG_MAX_RATIO', 2.0), 0.1, key=f"atr_max_{config_name}"
                        )

                    config['USE_CIRCUIT_BREAKER'] = st.checkbox(
                        "Circuit Breaker", config.get('USE_CIRCUIT_BREAKER', False), key=f"cb_use_{config_name}"
                    )
                    if config['USE_CIRCUIT_BREAKER']:
                        config['DAILY_DD_LIMIT'] = st.slider(
                            "DD journalier", 0.01, 0.10, config.get('DAILY_DD_LIMIT', 0.05), 0.01, format="%.2f", key=f"dd_limit_{config_name}"
                        )

                    config['USE_ADAPTIVE_RISK'] = st.checkbox(
                        "Risque Adaptatif", config.get('USE_ADAPTIVE_RISK', False), key=f"adapt_risk_{config_name}"
                    )

                # ===============================
                # v2.0 ICT FILTERS SECTION
                # ===============================
                st.markdown("---")
                st.subheader("🎯 Filtres ICT v2.0 (Nouveaux)")

                col_v20_1, col_v20_2, col_v20_3 = st.columns(3)

                with col_v20_1:
                    st.markdown("**Filtrage BOS & FVG**")
                    config['USE_BOS_RECENCY_FILTER'] = st.checkbox(
                        "Filtre récence BOS",
                        config.get('USE_BOS_RECENCY_FILTER', True),
                        key=f"bos_recency_{config_name}",
                        help="N'utiliser que les BOS des N dernières barres"
                    )
                    if config['USE_BOS_RECENCY_FILTER']:
                        config['BOS_MAX_AGE'] = st.slider(
                            "Age max BOS (barres)",
                            10, 50,
                            config.get('BOS_MAX_AGE', 20),
                            key=f"bos_age_{config_name}",
                            help="Seuls les BOS des N dernières barres sont valides"
                        )

                    config['USE_FVG_MITIGATION_FILTER'] = st.checkbox(
                        "Mitigation FVG",
                        config.get('USE_FVG_MITIGATION_FILTER', True),
                        key=f"fvg_mitigation_{config_name}",
                        help="Ignorer les FVG déjà touchés par le prix"
                    )

                with col_v20_2:
                    st.markdown("**Structure & Confluence**")
                    config['USE_MARKET_STRUCTURE_FILTER'] = st.checkbox(
                        "Structure de marché",
                        config.get('USE_MARKET_STRUCTURE_FILTER', True),
                        key=f"market_struct_{config_name}",
                        help="Valider la structure HH/HL (haussier) ou LL/LH (baissier)"
                    )

                    config['FVG_BOS_MAX_DISTANCE'] = st.slider(
                        "Distance FVG-BOS max",
                        10, 50,
                        config.get('FVG_BOS_MAX_DISTANCE', 20),
                        key=f"fvg_bos_dist_{config_name}",
                        help="Distance maximale (barres) entre FVG et BOS pour confluence"
                    )

                    config['USE_ORDER_BLOCK_SL'] = st.checkbox(
                        "Order Block SL",
                        config.get('USE_ORDER_BLOCK_SL', True),
                        key=f"ob_sl_{config_name}",
                        help="Utiliser Order Blocks pour Stop Loss (vs swing points)"
                    )

                with col_v20_3:
                    st.markdown("**Protection Volatilité**")
                    config['USE_EXTREME_VOLATILITY_FILTER'] = st.checkbox(
                        "Filtre volatilité extrême",
                        config.get('USE_EXTREME_VOLATILITY_FILTER', True),
                        key=f"vol_filter_{config_name}",
                        help="Ignorer trades si ATR > N × médiane ATR (protection news)"
                    )
                    if config['USE_EXTREME_VOLATILITY_FILTER']:
                        config['VOLATILITY_MULTIPLIER_MAX'] = st.slider(
                            "Multiplicateur max ATR",
                            2.0, 5.0,
                            config.get('VOLATILITY_MULTIPLIER_MAX', 3.0),
                            0.5,
                            key=f"vol_mult_{config_name}",
                            help="Rejeter si ATR actuel > N × médiane ATR (défaut: 3.0)"
                        )

                st.markdown("---")
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 Sauvegarder", type="primary", use_container_width=True, key=f"save_config_{config_name}"):
                        save_config_by_name(config_name, config)
                        st.session_state.editing_config_name = None
                        st.success(f"✅ Configuration '{config_name}' sauvegardée ! Les bots utilisant cette config verront les changements au prochain redémarrage.")
                        st.rerun()

                with col_cancel:
                    if st.button("❌ Annuler", type="secondary", use_container_width=True, key=f"cancel_config_{config_name}"):
                        st.session_state.editing_config_name = None
                        st.rerun()

            else:
                # ===== MODE AFFICHAGE =====
                config = load_config_by_name(config_name)

                # Afficher les paramètres clés
                col_info1, col_info2, col_info3 = st.columns(3)
                with col_info1:
                    st.metric("Risque/Trade", f"{config.get('RISK_PER_TRADE', 0.01)*100:.1f}%")
                    st.metric("Risk/Reward", f"{config.get('RR_TAKE_PROFIT', 2.0):.1f}")
                with col_info2:
                    st.metric("Max Trades", config.get('MAX_CONCURRENT_TRADES', 1))
                    st.metric("ML Actif", "✅" if config.get('USE_ML_META_LABELLING', False) else "❌")
                with col_info3:
                    st.metric("ATR Filter", "✅" if config.get('USE_ATR_FILTER', False) else "❌")
                    st.metric("Circuit Breaker", "✅" if config.get('USE_CIRCUIT_BREAKER', False) else "❌")

                # Afficher les paramètres v2.0
                st.markdown("**🎯 Filtres ICT v2.0:**")
                col_v20_display1, col_v20_display2, col_v20_display3 = st.columns(3)
                with col_v20_display1:
                    st.caption(f"BOS Recency: {'✅' if config.get('USE_BOS_RECENCY_FILTER', True) else '❌'} (max {config.get('BOS_MAX_AGE', 20)} barres)")
                    st.caption(f"FVG Mitigation: {'✅' if config.get('USE_FVG_MITIGATION_FILTER', True) else '❌'}")
                with col_v20_display2:
                    st.caption(f"Market Structure: {'✅' if config.get('USE_MARKET_STRUCTURE_FILTER', True) else '❌'}")
                    st.caption(f"FVG-BOS Distance: max {config.get('FVG_BOS_MAX_DISTANCE', 20)} barres")
                with col_v20_display3:
                    st.caption(f"Order Block SL: {'✅' if config.get('USE_ORDER_BLOCK_SL', True) else '❌'}")
                    st.caption(f"Vol. Filter: {'✅' if config.get('USE_EXTREME_VOLATILITY_FILTER', True) else '❌'} (×{config.get('VOLATILITY_MULTIPLIER_MAX', 3.0)})")

                # Bots utilisant cette config
                if bots_using:
                    st.info(f"🤖 Utilisée par : {', '.join(bots_using)}")
                else:
                    st.caption("Aucun bot n'utilise cette configuration")

                # Boutons
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"✏️ Modifier", key=f"edit_config_{config_name}", use_container_width=True):
                        st.session_state.editing_config_name = config_name
                        st.rerun()

                with col_btn2:
                    if config_name != 'Default':
                        if st.button(f"🗑️ Supprimer", key=f"delete_config_{config_name}", type="secondary", use_container_width=True):
                            if bots_using:
                                st.error(f"⚠️ Impossible de supprimer: {len(bots_using)} bot(s) utilisent cette config")
                            else:
                                success, msg = delete_config(config_name)
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                    else:
                        st.caption("La config Default ne peut pas être supprimée")

# ===============================
# TAB 3: BACKTEST
# ===============================
with tab3:
    st.header("🧪 Backtest avec Configuration")

    col_bt1, col_bt2, col_bt3, col_bt4 = st.columns(4)

    with col_bt1:
        bt_symbol = st.selectbox(
            "Symbole",
            ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'ETHUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'],
            index=0,
            key="backtest_symbol"
        )

    with col_bt2:
        bt_timeframe = st.selectbox(
            "Timeframe",
            ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
            index=1,
            key="backtest_timeframe"
        )

    with col_bt3:
        bt_bars = st.number_input(
            "Nombre de barres",
            min_value=1000,
            max_value=1000000,
            value=100000,
            step=1000,
            key="backtest_bars"
        )

    with col_bt4:
        # Charger la liste des configurations disponibles
        available_configs_bt = load_configs_list()
        bt_config_name = st.selectbox(
            "⚙️ Configuration",
            available_configs_bt,
            index=0 if 'Default' in available_configs_bt else 0,
            key="backtest_config",
            help="Sélectionnez la configuration à tester"
        )

    st.info(f"ℹ️ Le backtest utilisera la configuration '{bt_config_name}' depuis le dossier config/")

    # Best practices guidance
    with st.expander("💡 Conseils pour des backtests réussis", expanded=False):
        st.markdown("""
**Recommandations par Timeframe:**
- **M5**: 10,000-20,000 barres (35-70 jours) - Utilise beaucoup de RAM
- **H1**: 3,000-5,000 barres (4-7 mois) ⭐ **Recommandé** - Bon équilibre
- **H4**: 1,500-2,000 barres (6-11 mois) ⭐ **Recommandé** - Rapide et stable

**Pourquoi autant de barres ?**
Le bot trade seulement 6h/jour (Kill Zones: London 8h-11h + NY 14h-17h Paris time).
Cela représente 25% du temps → il faut 4× plus de données pour avoir assez de trades.

**Si vous obtenez 0 trades:**
1. Augmentez le nombre de barres (essayez 100,000 pour M5)
2. Vérifiez que la période contient des Kill Zones
3. Regardez les statistiques de filtrage v2.1 pour identifier le problème

**Durée d'exécution:**
- M5 100,000 barres: ~2-5 minutes
- H1 5,000 barres: ~30-60 secondes
- H4 2,000 barres: ~20-40 secondes
        """)

    if st.button("🚀 Lancer le Backtest", type="primary", use_container_width=True, key="launch_backtest_button"):
        with st.spinner("Backtest en cours... Cela peut prendre quelques minutes..."):
            success, stdout, stderr = run_backtest_with_params(
                bt_config_name,
                bt_symbol,
                bt_timeframe,
                bt_bars
            )

            if success:
                st.success(f"✅ Backtest termine avec succes (config: {bt_config_name}) !")
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

            # Check for 0 trades and display helpful warning
            if trades == 0:
                st.error("⚠️ AUCUN TRADE GENERE")
                st.warning("""
**Causes possibles:**
1. **Pas assez de barres** - Le bot trade seulement 6h/jour (Kill Zones)
   - Recommandé: 10,000+ barres pour M5, 3,000+ pour H1, 1,500+ pour H4
2. **Filtres v2.1 trop stricts** - Consultez les statistiques de filtrage ci-dessous
   - Essayez d'augmenter `BOS_MAX_AGE` de 20 à 30 barres
   - Ou désactivez temporairement `USE_MARKET_STRUCTURE_FILTER`
3. **Période sans Kill Zones** - Bot ne trade que pendant London (8h-11h) et NY (14h-17h) Paris time

**Solutions:**
- Augmentez le nombre de barres (utilisez 100,000+ pour M5)
- Utilisez H1 ou H4 au lieu de M5 pour des backtests plus rapides
- Relâchez les filtres v2.1 dans l'onglet Paramètres
- Vérifiez que la période testée contient des sessions de trading

📊 Consultez les **Statistiques de Filtrage v2.1** ci-dessous pour identifier où les signaux sont bloqués.
                """)

            col_h1, col_h2, col_h3, col_h4 = st.columns(4)
            with col_h1:
                st.metric("Trades", trades, delta="⚠️ Trop peu" if trades < 10 else None)
            with col_h2:
                st.metric("Win Rate", f"{winrate:.2f}%")
            with col_h3:
                st.metric("PnL", f"${pnl:,.2f}")
            with col_h4:
                st.metric("Max DD", f"{max_dd:.2f}%")

            # Afficher les statistiques v2.0 si disponibles
            if 'statistics' in backtest_data:
                stats = backtest_data['statistics']

                # Vérifier si des stats v2.0 existent
                has_v20_stats = any(key in stats for key in [
                    'fvg_mitigated_filtered', 'bos_too_old_filtered',
                    'fvg_bos_too_far_filtered', 'market_structure_filtered',
                    'extreme_volatility_filtered'
                ])

                if has_v20_stats:
                    st.markdown("---")
                    st.subheader("📊 Statistiques de Filtrage v2.0")

                    col_v20_s1, col_v20_s2, col_v20_s3, col_v20_s4, col_v20_s5 = st.columns(5)

                    with col_v20_s1:
                        fvg_mitigated = stats.get('fvg_mitigated_filtered', 0)
                        st.metric(
                            "FVG Mitigés",
                            fvg_mitigated,
                            help="FVG déjà touchés par le prix (ignorés)"
                        )

                    with col_v20_s2:
                        bos_old = stats.get('bos_too_old_filtered', 0)
                        st.metric(
                            "BOS Trop Anciens",
                            bos_old,
                            help="BOS de plus de BOS_MAX_AGE barres (ignorés)"
                        )

                    with col_v20_s3:
                        fvg_bos_far = stats.get('fvg_bos_too_far_filtered', 0)
                        st.metric(
                            "FVG-BOS Éloignés",
                            fvg_bos_far,
                            help="Distance FVG-BOS > FVG_BOS_MAX_DISTANCE barres"
                        )

                    with col_v20_s4:
                        market_struct = stats.get('market_structure_filtered', 0)
                        st.metric(
                            "Structure Invalide",
                            market_struct,
                            help="Structure de marché non conforme (HH/HL ou LL/LH)"
                        )

                    with col_v20_s5:
                        extreme_vol = stats.get('extreme_volatility_filtered', 0)
                        st.metric(
                            "Volatilité Extrême",
                            extreme_vol,
                            help="ATR > VOLATILITY_MULTIPLIER_MAX × médiane"
                        )

                    # Calculer le total de filtres v2.0
                    total_v20_filtered = (fvg_mitigated + bos_old + fvg_bos_far +
                                         market_struct + extreme_vol)

                    if total_v20_filtered > 0:
                        st.info(f"🎯 Total filtrés par v2.0: **{total_v20_filtered}** signaux rejetés (amélioration qualité)")
                    else:
                        st.caption("Aucun signal filtré par les filtres v2.0 sur cette période")

                    st.markdown("---")
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

# ===============================
# TAB 5: GRID TESTING
# ===============================
with tab5:
    st.header("🔬 Grid Testing - Optimisation des Parametres")

    if not GRID_SEARCH_AVAILABLE:
        st.error("⚠️ Le module grid_search_engine_batch.py n'est pas disponible")
    else:
        st.success("🚀 Grid Search Optimisé (25-35x speedup)")

        st.info(
            "🎯 **Fonctionnement**: Score = 40% PnL + 30% Sharpe + 20% WinRate + 10% (1-DD)\n\n"
            "**v2.1**: Utilise 12 features ML (vs 5 en v1.0) pour meilleure analyse de marché"
        )

        # Section: Mode Selection
        st.subheader("🎯 Mode de Recherche")

        col_mode1, col_mode2 = st.columns(2)

        with col_mode1:
            grid_mode = st.radio(
                "Sélectionnez le mode",
                options=['standard', 'advanced'],
                index=0,
                key="grid_mode",
                help="Standard: 1,728 tests (~4-6 min) | Advanced: 46,656 tests (~2-3h)"
            )

        with col_mode2:
            if grid_mode == 'standard':
                st.metric("Combinaisons", "1,728")
                st.caption("✅ Mode rapide (recommandé pour débuter)")
                st.caption("Paramètres: Risk, RR, Max Trades, Cooldown, ML Threshold, Session RR, ATR Filter")
            else:
                st.metric("Combinaisons", "46,656")
                st.caption("⚡ Mode avancé (v2.1 ICT)")
                st.caption("Ajoute: BOS_MAX_AGE (3 valeurs), FVG_BOS_MAX_DISTANCE (3), VOLATILITY_MULTIPLIER_MAX (3)")

        st.markdown("---")

        # Section: Configuration du test
        st.subheader("⚙️ Configuration du Test")

        col_grid1, col_grid2, col_grid3 = st.columns(3)

        with col_grid1:
            grid_symbol = st.selectbox(
                "Symbole",
                ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD', 'BTCUSD', 'ETHUSD', 'XAUUSD', 'NAS100', 'US30', 'US500'],
                index=0,
                key="grid_symbol"
            )

        with col_grid2:
            grid_timeframe = st.selectbox(
                "Timeframe",
                ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'],
                index=1,
                key="grid_timeframe"
            )

        with col_grid3:
            grid_bars = st.number_input(
                "Nombre de barres",
                min_value=500,
                max_value=100000,
                value=100000,
                step=500,
                key="grid_bars",
                help="💡 M5: 10,000-20,000 | H1: 2,000-5,000 | H4: 1,000-2,000"
            )

            # Info sur la période selon le timeframe sélectionné
            if grid_timeframe == 'M5':
                days = (grid_bars * 5) / (60 * 24)
                st.caption(f"📅 ≈ {days:.0f} jours de données")
            elif grid_timeframe == 'M15':
                days = (grid_bars * 15) / (60 * 24)
                st.caption(f"📅 ≈ {days:.0f} jours de données")
            elif grid_timeframe == 'M30':
                days = (grid_bars * 30) / (60 * 24)
                st.caption(f"📅 ≈ {days:.0f} jours de données")
            elif grid_timeframe == 'H1':
                days = grid_bars / 24
                st.caption(f"📅 ≈ {days:.0f} jours ({days/30:.1f} mois)")
            elif grid_timeframe == 'H4':
                days = (grid_bars * 4) / 24
                st.caption(f"📅 ≈ {days:.0f} jours ({days/30:.1f} mois)")
            elif grid_timeframe == 'D1':
                days = grid_bars
                st.caption(f"📅 ≈ {days:.0f} jours ({days/30:.1f} mois)")

        # Afficher le nombre de combinaisons a tester (updated dynamically with mode)
        try:
            total_combinations = len(generate_all_combinations(mode=grid_mode))
            # Formatting with thousands separator
            st.metric("🔢 Nombre de combinaisons", f"{total_combinations:,}".replace(',', ' '))
        except Exception as e:
            # Fallback based on mode
            fallback = "1,728" if grid_mode == 'standard' else "46,656"
            st.metric("🔢 Nombre de combinaisons", fallback)

        # Section: Workers
        col_worker1, col_worker2 = st.columns(2)

        with col_worker1:
            import multiprocessing as mp
            # IMPORTANT: Limiter a 2 workers par defaut pour eviter crash memoire
            recommended_workers = min(2, max(1, mp.cpu_count() - 2))
            grid_workers = st.slider(
                "Nombre de workers paralleles",
                min_value=1,
                max_value=mp.cpu_count(),
                value=recommended_workers,
                key="grid_workers",
                help=f"⚠️ IMPORTANT: ne mettez ppas tout vos workers, cela peut faire planter votre pc. Votre système a {mp.cpu_count()} CPU mais chaque worker charge les données MT5 en RAM."
            )

            if grid_workers > 10:
                st.warning(f"⚠️ Attention: plus de {mp.cpu_count()-5} workers peut faire crasher votre pc si votre RAM insuffisante!")

        with col_worker2:
            # Estimation du temps basée sur le nombre de barres
            # Plus de barres = backtest plus long
            if grid_bars < 2000:
                sec_per_test = 5
            elif grid_bars < 10000:
                sec_per_test = 10
            else:
                sec_per_test = 15

            estimated_minutes = (total_combinations * sec_per_test) / grid_workers / 60

            if estimated_minutes < 60:
                st.metric("⏱️ Temps estimé", f"{estimated_minutes:.0f} min")
            else:
                hours = estimated_minutes / 60
                st.metric("⏱️ Temps estimé", f"{hours:.1f} heures")

            if grid_workers == 1:
                st.caption("✅ Mode séquentiel (le plus stable)")
            else:
                st.caption(f"⚡ {grid_workers} tests simultanés")

        st.markdown("---")

        # Best practices for grid search
        with st.expander("💡 Conseils pour Grid Search", expanded=False):
            st.markdown(f"""
**Mode sélectionné: {grid_mode.upper()}**
- **Standard**: 1,728 tests (~4-6 min avec 2 workers)
- **Advanced**: 46,656 tests (~2-3 heures avec 2 workers)

**Recommandations:**
1. **Commencez par Standard** pour tester rapidement
2. **Utilisez H1 ou H4** pour des résultats plus rapides que M5
3. **Limitez à 2-4 workers** pour éviter les crashs mémoire
4. **Bars recommandées**:
   - M5: 10,000-20,000 (mais tests lents)
   - H1: 2,000-5,000 ⭐ Recommandé
   - H4: 1,000-2,000 ⭐ Recommandé

**Durée estimée (Mode {grid_mode.upper()}):**
- 2 workers: {estimated_minutes:.0f} min
- 4 workers: {estimated_minutes/2:.0f} min (risque crash si RAM < 16 GB)

**Après les tests:**
Vous pouvez sauvegarder les meilleures configs comme nouvelles configurations réutilisables.
            """)

        st.markdown("---")

        # Bouton de lancement
        col_btn1, col_btn2 = st.columns([1, 3])

        with col_btn1:
            start_grid = st.button(
                "🚀 Lancer Grid Testing",
                type="primary",
                use_container_width=True,
                key="start_grid_button"
            )

        # Lancer le grid search
        if start_grid:
            st.info(f"🚀 Lancement du Grid Testing avec {grid_workers} workers...")

            # Creer le dossier Grid/ s'il n'existe pas
            os.makedirs('Grid', exist_ok=True)

            # Barre de progression
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Callback de progression
            def update_progress(completed, total):
                progress = completed / total
                progress_bar.progress(progress)
                status_text.text(f"Progression: {completed}/{total} tests completes ({progress*100:.1f}%)")

            try:
                # Lancer le grid search
                with st.spinner(f"Execution des tests en cours (Mode: {grid_mode.upper()})..."):
                    # Lancer le grid search optimisé avec le mode sélectionné
                    results = run_grid_search(
                        symbol=grid_symbol,
                        timeframe=grid_timeframe,
                        bars=grid_bars,
                        max_workers=grid_workers,
                        batch_size=10,  # Optimal pour la plupart des cas
                        mode=grid_mode,  # CRITICAL: Pass the mode parameter!
                        callback=update_progress
                    )

                # Sauvegarder les resultats
                report_path = save_top_results(
                    results=results,
                    symbol=grid_symbol,
                    timeframe=grid_timeframe,
                    bars=grid_bars,
                    top_n=5
                )

                st.success(f"✅ Grid Testing termine! Rapport sauvegarde: {report_path}")

                # Afficher les top 5 resultats
                st.subheader("🏆 Top 5 Configurations")

                for i, result in enumerate(results[:5], 1):
                    with st.expander(f"#{i} - Score: {result['composite_score']:.4f}", expanded=(i==1)):
                        # Metriques principales
                        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)

                        with col_m1:
                            st.metric("PnL", f"{result['pnl_pct']:.2f}%")

                        with col_m2:
                            st.metric("Win Rate", f"{result['win_rate']:.2f}%")

                        with col_m3:
                            st.metric("Sharpe", f"{result['sharpe_ratio']:.3f}")

                        with col_m4:
                            st.metric("Max DD", f"{result['max_drawdown_pct']:.2f}%")

                        with col_m5:
                            st.metric("Trades", result['total_trades'])

                        # Parametres
                        st.markdown("**Parametres:**")
                        params_df = pd.DataFrame([result['params']]).T
                        params_df.columns = ['Valeur']
                        st.dataframe(params_df, use_container_width=True)

                        # Bouton pour sauvegarder cette config
                        col_save1, col_save2 = st.columns([1, 3])
                        with col_save1:
                            config_name = st.text_input(
                                "Nom de la config",
                                value=f"GridOptim_{i}",
                                key=f"config_name_{i}"
                            )
                        with col_save2:
                            if st.button(f"💾 Sauvegarder comme nouvelle config", key=f"save_config_{i}"):
                                # Sauvegarder dans config/
                                config_path = f"config/{config_name}.json"
                                try:
                                    with open(config_path, 'w', encoding='utf-8') as f:
                                        json.dump(result['params'], f, indent=4)
                                    st.success(f"✅ Configuration sauvegardee: {config_path}")
                                except Exception as e:
                                    st.error(f"❌ Erreur: {e}")

            except Exception as e:
                st.error(f"❌ Erreur lors du Grid Testing: {e}")
                st.exception(e)

        st.markdown("---")

        # Section: Historique des Grid Tests
        st.subheader("📊 Historique des Grid Tests")

        grid_dir = 'Grid'
        if os.path.exists(grid_dir):
            grid_files = sorted(
                [os.path.join(grid_dir, f) for f in os.listdir(grid_dir)
                 if f.startswith('grid_results_') and f.endswith('.json')],
                reverse=True
            )

            if grid_files:
                selected_grid = st.selectbox(
                    "Selectionner un rapport",
                    grid_files,
                    format_func=lambda x: os.path.basename(x),
                    key="select_grid_report"
                )

                try:
                    with open(selected_grid, 'r', encoding='utf-8') as f:
                        grid_report = json.load(f)

                    # Afficher les metadonnees
                    metadata = grid_report.get('metadata', {})
                    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)

                    with col_meta1:
                        st.metric("Symbole", metadata.get('symbol', 'N/A'))

                    with col_meta2:
                        st.metric("Timeframe", metadata.get('timeframe', 'N/A'))

                    with col_meta3:
                        st.metric("Barres", metadata.get('bars', 'N/A'))

                    with col_meta4:
                        st.metric("Tests", metadata.get('total_tests', 'N/A'))

                    st.caption(f"Date: {metadata.get('date', 'N/A')}")

                    st.markdown("---")

                    # Afficher le top 5 sauvegarde
                    st.markdown("**🏆 Top 5 Configurations:**")

                    top_configs = grid_report.get('top_configs', [])

                    # Creer un tableau resume
                    summary_data = []
                    for i, config in enumerate(top_configs, 1):
                        summary_data.append({
                            'Rang': f"#{i}",
                            'Score': f"{config['composite_score']:.4f}",
                            'PnL (%)': f"{config['pnl_pct']:.2f}",
                            'Win Rate (%)': f"{config['win_rate']:.2f}",
                            'Sharpe': f"{config['sharpe_ratio']:.3f}",
                            'Max DD (%)': f"{config['max_drawdown_pct']:.2f}",
                            'Trades': config['total_trades']
                        })

                    summary_df = pd.DataFrame(summary_data)
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)

                    # Details de chaque config
                    for i, config in enumerate(top_configs, 1):
                        with st.expander(f"Details #{i}"):
                            params_df = pd.DataFrame([config['params']]).T
                            params_df.columns = ['Valeur']
                            st.dataframe(params_df, use_container_width=True)

                except Exception as e:
                    st.error(f"❌ Erreur lors du chargement: {e}")
            else:
                st.info("Aucun rapport de Grid Testing disponible")
        else:
            st.info("Aucun rapport de Grid Testing disponible")

# Footer
st.markdown("---")
st.markdown("🤖 **ICT Trading Bot Manager v2.0** - Interface Avancee avec Suivi Temps Reel")
