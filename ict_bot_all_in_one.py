# -*- coding: utf-8 -*-
"""
ICT Bot All-in-One — Backtest + Live MT5 + Dashboard + ML
Stratégie ICT : FVG (Fair Value Gaps), BOS (Break of Structure), Kill Zones
ML Meta-Labelling avec Rolling Window anti-over-training
"""

import os, time, argparse, json
from datetime import datetime
import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
    MT5_OK = True
except Exception:
    MT5_OK = False

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.exceptions import ConvergenceWarning
    import warnings as _warnings
    _warnings.simplefilter("ignore", ConvergenceWarning)
    import joblib
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False

try:
    import matplotlib.pyplot as plt
    MPL_OK = True
except Exception:
    MPL_OK = False

try:
    import pytz
    TZ_PARIS = pytz.timezone("Europe/Paris")
    TZ_OK = True
except Exception:
    TZ_OK = False
    TZ_PARIS = None

try:
    import requests
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False

# ===============================
# CREDENTIALS LOADERS
# ===============================

def load_mt5_credentials():
    """Charge les identifiants MT5 depuis le fichier mt5_credentials.json"""
    if os.path.exists('mt5_credentials.json'):
        with open('mt5_credentials.json', 'r') as f:
            return json.load(f)
    # Fichier non trouvé - retourner valeurs vides
    print("⚠️ ERREUR: Fichier mt5_credentials.json introuvable!")
    print("Veuillez créer le fichier à partir de mt5_credentials.json.example")
    return {"login": None, "password": None, "server": None}

def load_telegram_credentials():
    """Charge les identifiants Telegram depuis le fichier telegram_credentials.json"""
    if os.path.exists('telegram_credentials.json'):
        with open('telegram_credentials.json', 'r') as f:
            return json.load(f)
    # Valeurs par défaut si le fichier n'existe pas
    return {"enabled": True, "bot_token": "", "chat_id": ""}

# Chargement des credentials
_mt5_creds = load_mt5_credentials()
_telegram_creds = load_telegram_credentials()

# ===============================
# CONFIG
# ===============================

LOGIN = _mt5_creds.get("login")
PASSWORD = _mt5_creds.get("password")
SERVER = _mt5_creds.get("server")

SYMBOL_DEFAULT = "EURUSD"
TIMEFRAME_DEFAULT = "M5"
BACKTEST_MONTHS = 6

BARS_PER_TIMEFRAME = {
    "M1": 43200,
    "M5": 100000,
    "M15": 2880,
    "M30": 1440,
    "H1": 720,
    "H4": 1080,
    "D1": 180,
}
BARS_DEFAULT = 100000

RISK_PER_TRADE = 0.01
RR_TAKE_PROFIT = 1.8
MAX_CONCURRENT_TRADES = 2
COOLDOWN_BARS = 5
ML_THRESHOLD = 0.40

# RR Adaptatif par Session
USE_SESSION_ADAPTIVE_RR = True
RR_LONDON = 1.2
RR_NEWYORK = 1.5
RR_DEFAULT = 1.3

# ML Meta-Labelling avec Rolling Window
USE_ML_META_LABELLING = True
MAX_ML_SAMPLES = 500

# Kill Zones (heures Paris)
KZ_LONDON = (8, 11)
KZ_NEWYORK = (14, 17)

# Filtres actifs
USE_ATR_FILTER = True
ATR_FVG_MIN_RATIO = 0.2
ATR_FVG_MAX_RATIO = 2.5
USE_CIRCUIT_BREAKER = True
DAILY_DD_LIMIT = 0.03
USE_ADAPTIVE_RISK = True
RISK_REDUCTION_FACTOR = 0.5

MAGIC_NUMBER = 161803
COMMENT = "ICTv2"

# === v2.0 STRATEGY ENHANCEMENTS ===
# BOS Recency & Strength Validation
USE_BOS_RECENCY_FILTER = True
BOS_MAX_AGE = 20  # Only use BOS from last N bars

# FVG Mitigation Tracking
USE_FVG_MITIGATION_FILTER = True

# Market Structure Detection
USE_MARKET_STRUCTURE_FILTER = True

# Temporal Confluence
FVG_BOS_MAX_DISTANCE = 20  # FVG and BOS must be within N bars

# Order Block Enhancement
USE_ORDER_BLOCK_SL = True  # Use Order Blocks for SL placement

# Extreme Volatility Filter
USE_EXTREME_VOLATILITY_FILTER = True
VOLATILITY_MULTIPLIER_MAX = 3.0  # Skip trades if ATR > N × median ATR

# Telegram Notifications (chargé depuis telegram_credentials.json)
TELEGRAM_ENABLED = _telegram_creds.get("enabled", True)
TELEGRAM_BOT_TOKEN = _telegram_creds.get("bot_token", "")
TELEGRAM_CHAT_ID = _telegram_creds.get("chat_id", "")

# ===============================
# UTILS
# ===============================

MT5_TF_MAP = {
    "M1":  mt5.TIMEFRAME_M1 if MT5_OK else 1,
    "M5":  mt5.TIMEFRAME_M5 if MT5_OK else 5,
    "M15": mt5.TIMEFRAME_M15 if MT5_OK else 15,
    "M30": mt5.TIMEFRAME_M30 if MT5_OK else 30,
    "H1":  mt5.TIMEFRAME_H1 if MT5_OK else 60,
    "H4":  mt5.TIMEFRAME_H4 if MT5_OK else 240,
    "D1":  mt5.TIMEFRAME_D1 if MT5_OK else 1440,
}

def now_paris():
    if TZ_OK:
        return datetime.now(TZ_PARIS)
    return datetime.now()

def in_kill_zone(dt_local_paris: datetime) -> bool:
    h = dt_local_paris.hour
    return (KZ_LONDON[0] <= h < KZ_LONDON[1]) or (KZ_NEWYORK[0] <= h < KZ_NEWYORK[1])

def get_session_rr(dt_local_paris: datetime) -> float:
    """Retourne le RR adaptatif selon la session de trading"""
    if not USE_SESSION_ADAPTIVE_RR:
        return RR_TAKE_PROFIT
    h = dt_local_paris.hour
    if KZ_LONDON[0] <= h < KZ_LONDON[1]:
        return RR_LONDON
    elif KZ_NEWYORK[0] <= h < KZ_NEWYORK[1]:
        return RR_NEWYORK
    else:
        return RR_DEFAULT

def get_pip_size_from_info(info):
    if info is None:
        return 0.0001
    return info.point * 10.0

def pip_value_per_lot(info):
    if info is None:
        return 10.0
    if getattr(info, "trade_tick_value", 0) and getattr(info, "trade_tick_size", 0):
        pip_sz = get_pip_size_from_info(info)
        return (pip_sz / info.trade_tick_size) * info.trade_tick_value
    return 10.0

def load_config_from_file(config_name='Default'):
    """Charge la configuration depuis config/{config_name}.json et met a jour les variables globales"""
    global RISK_PER_TRADE, RR_TAKE_PROFIT, MAX_CONCURRENT_TRADES, COOLDOWN_BARS, ML_THRESHOLD
    global USE_SESSION_ADAPTIVE_RR, RR_LONDON, RR_NEWYORK, RR_DEFAULT
    global USE_ML_META_LABELLING, MAX_ML_SAMPLES
    global USE_ATR_FILTER, ATR_FVG_MIN_RATIO, ATR_FVG_MAX_RATIO
    global USE_CIRCUIT_BREAKER, DAILY_DD_LIMIT
    global USE_ADAPTIVE_RISK
    # v2.0 parameters
    global USE_BOS_RECENCY_FILTER, BOS_MAX_AGE
    global USE_FVG_MITIGATION_FILTER
    global USE_MARKET_STRUCTURE_FILTER
    global FVG_BOS_MAX_DISTANCE
    global USE_ORDER_BLOCK_SL
    global USE_EXTREME_VOLATILITY_FILTER, VOLATILITY_MULTIPLIER_MAX

    # Construire le chemin vers le fichier de config
    filepath = f'config/{config_name}.json'

    if not os.path.exists(filepath):
        print(f"[CONFIG] Fichier {filepath} introuvable, utilisation des valeurs par defaut")
        return

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Charger tous les parametres depuis le JSON
        RISK_PER_TRADE = config.get('RISK_PER_TRADE', RISK_PER_TRADE)
        RR_TAKE_PROFIT = config.get('RR_TAKE_PROFIT', RR_TAKE_PROFIT)
        MAX_CONCURRENT_TRADES = config.get('MAX_CONCURRENT_TRADES', MAX_CONCURRENT_TRADES)
        COOLDOWN_BARS = config.get('COOLDOWN_BARS', COOLDOWN_BARS)
        ML_THRESHOLD = config.get('ML_THRESHOLD', ML_THRESHOLD)

        USE_SESSION_ADAPTIVE_RR = config.get('USE_SESSION_ADAPTIVE_RR', USE_SESSION_ADAPTIVE_RR)
        RR_LONDON = config.get('RR_LONDON', RR_LONDON)
        RR_NEWYORK = config.get('RR_NEWYORK', RR_NEWYORK)
        RR_DEFAULT = config.get('RR_DEFAULT', RR_DEFAULT)

        USE_ML_META_LABELLING = config.get('USE_ML_META_LABELLING', USE_ML_META_LABELLING)
        MAX_ML_SAMPLES = config.get('MAX_ML_SAMPLES', MAX_ML_SAMPLES)

        USE_ATR_FILTER = config.get('USE_ATR_FILTER', USE_ATR_FILTER)
        ATR_FVG_MIN_RATIO = config.get('ATR_FVG_MIN_RATIO', ATR_FVG_MIN_RATIO)
        ATR_FVG_MAX_RATIO = config.get('ATR_FVG_MAX_RATIO', ATR_FVG_MAX_RATIO)

        USE_CIRCUIT_BREAKER = config.get('USE_CIRCUIT_BREAKER', USE_CIRCUIT_BREAKER)
        DAILY_DD_LIMIT = config.get('DAILY_DD_LIMIT', DAILY_DD_LIMIT)

        USE_ADAPTIVE_RISK = config.get('USE_ADAPTIVE_RISK', USE_ADAPTIVE_RISK)

        # v2.0 Strategy Enhancements
        USE_BOS_RECENCY_FILTER = config.get('USE_BOS_RECENCY_FILTER', USE_BOS_RECENCY_FILTER)
        BOS_MAX_AGE = config.get('BOS_MAX_AGE', BOS_MAX_AGE)
        USE_FVG_MITIGATION_FILTER = config.get('USE_FVG_MITIGATION_FILTER', USE_FVG_MITIGATION_FILTER)
        USE_MARKET_STRUCTURE_FILTER = config.get('USE_MARKET_STRUCTURE_FILTER', USE_MARKET_STRUCTURE_FILTER)
        FVG_BOS_MAX_DISTANCE = config.get('FVG_BOS_MAX_DISTANCE', FVG_BOS_MAX_DISTANCE)
        USE_ORDER_BLOCK_SL = config.get('USE_ORDER_BLOCK_SL', USE_ORDER_BLOCK_SL)
        USE_EXTREME_VOLATILITY_FILTER = config.get('USE_EXTREME_VOLATILITY_FILTER', USE_EXTREME_VOLATILITY_FILTER)
        VOLATILITY_MULTIPLIER_MAX = config.get('VOLATILITY_MULTIPLIER_MAX', VOLATILITY_MULTIPLIER_MAX)

        print(f"[CONFIG] Configuration chargee depuis {filepath}")
        print(f"[CONFIG] RISK_PER_TRADE = {RISK_PER_TRADE}")
        print(f"[CONFIG] RR_TAKE_PROFIT = {RR_TAKE_PROFIT}")
        print(f"[CONFIG] MAX_CONCURRENT_TRADES = {MAX_CONCURRENT_TRADES}")
        print(f"[CONFIG] ML_THRESHOLD = {ML_THRESHOLD}")
        print(f"[CONFIG] v2.0 Filters: BOS_Recency={USE_BOS_RECENCY_FILTER}, FVG_Mitigation={USE_FVG_MITIGATION_FILTER}, Market_Structure={USE_MARKET_STRUCTURE_FILTER}")

    except Exception as e:
        print(f"[CONFIG] Erreur lors du chargement de {filepath}: {e}")
        print(f"[CONFIG] Utilisation des valeurs par defaut")

# ===============================
# DATA / STRUCTURE ICT
# ===============================

def df_from_rates(rates):
    df = pd.DataFrame(rates)
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], unit='s')
    df.rename(columns={'real_volume': 'real_volume_ticks'}, inplace=True)
    return df[['time','open','high','low','close','tick_volume','real_volume_ticks','spread']]

def load_rates_mt5(symbol, tf_code, count):
    """
    Charge les barres depuis MT5, par chunks si necessaire (limite ~100k barres)
    """
    MAX_BARS_PER_CHUNK = 99000  # Limite MT5 ~100k, on prend 99k pour la securite

    if count <= MAX_BARS_PER_CHUNK:
        # Chargement simple si moins de 99k barres
        rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError("Aucune donnée MT5 reçue.")
        return df_from_rates(rates)

    # Chargement par chunks pour plus de 99k barres
    print(f"[*] Chargement de {count} barres par chunks de {MAX_BARS_PER_CHUNK}...")
    all_rates = []
    position = 0
    chunks_loaded = 0

    while position < count:
        remaining = count - position
        chunk_size = min(remaining, MAX_BARS_PER_CHUNK)

        print(f"    Chunk {chunks_loaded + 1}: position {position}, taille {chunk_size}")
        rates = mt5.copy_rates_from_pos(symbol, tf_code, position, chunk_size)

        if rates is None or len(rates) == 0:
            if chunks_loaded == 0:
                raise RuntimeError("Aucune donnée MT5 reçue.")
            else:
                print(f"    [!] Fin des donnees disponibles apres {position} barres")
                break

        all_rates.append(rates)
        position += len(rates)
        chunks_loaded += 1

        # Si on a recu moins que demande, on a atteint la fin
        if len(rates) < chunk_size:
            print(f"    [!] Fin des donnees disponibles ({len(rates)} < {chunk_size})")
            break

    if not all_rates:
        raise RuntimeError("Aucune donnée MT5 reçue.")

    # Concatener tous les chunks
    # Note: copy_rates_from_pos retourne les barres de la plus recente a la plus ancienne
    # Donc le chunk 0 contient les barres les plus recentes
    # On concatene dans l'ordre inverse pour avoir chronologique (ancien -> recent)
    combined_rates = np.concatenate(all_rates[::-1])
    print(f"[OK] {len(combined_rates)} barres chargees au total ({chunks_loaded} chunks)")

    return df_from_rates(combined_rates)

def swing_points(df: pd.DataFrame, left=2, right=2):
    """Détecte les swing high/low (fractals)"""
    highs = df['high'].values
    lows  = df['low'].values
    n = len(df)
    swing_high = np.zeros(n, dtype=bool)
    swing_low  = np.zeros(n, dtype=bool)

    for i in range(left, n-right):
        window_highs = highs[i-left:i+right+1]
        window_lows = lows[i-left:i+right+1]
        if highs[i] >= window_highs.max() and np.sum(window_highs == highs[i]) == 1:
            swing_high[i] = True
        if lows[i] <= window_lows.min() and np.sum(window_lows == lows[i]) == 1:
            swing_low[i] = True

    df['swing_high'] = swing_high
    df['swing_low']  = swing_low
    return df

def detect_bos(df: pd.DataFrame):
    """Détecte les Break of Structure (BOS)"""
    n = len(df)
    swing_high = df['swing_high'].values
    swing_low = df['swing_low'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values

    bos_up = np.zeros(n, dtype=bool)
    bos_dn = np.zeros(n, dtype=bool)
    last_sh = np.nan
    last_sl = np.nan

    for i in range(n):
        if swing_high[i]:
            last_sh = highs[i]
        if swing_low[i]:
            last_sl = lows[i]
        if not np.isnan(last_sh) and closes[i] > last_sh:
            bos_up[i] = True
        if not np.isnan(last_sl) and closes[i] < last_sl:
            bos_dn[i] = True

    df['bos_up'] = bos_up
    df['bos_down'] = bos_dn
    return df

def detect_fvg(df: pd.DataFrame):
    """Détecte les Fair Value Gaps (FVG)"""
    n = len(df)
    highs = df['high'].values
    lows = df['low'].values

    bull_fvg_top = np.full(n, np.nan)
    bull_fvg_bot = np.full(n, np.nan)
    bear_fvg_top = np.full(n, np.nan)
    bear_fvg_bot = np.full(n, np.nan)
    fvg_side = np.array(['none'] * n, dtype=object)

    bull_mask = lows[2:] > highs[:-2]
    bull_indices = np.where(bull_mask)[0] + 2
    for i in bull_indices:
        bull_fvg_bot[i] = highs[i-2]
        bull_fvg_top[i] = lows[i]
        fvg_side[i] = 'bull'

    bear_mask = highs[2:] < lows[:-2]
    bear_indices = np.where(bear_mask)[0] + 2
    for i in bear_indices:
        bear_fvg_top[i] = lows[i-2]
        bear_fvg_bot[i] = highs[i]
        fvg_side[i] = 'bear'

    df['fvg_side'] = fvg_side
    df['fvg_bull_top'] = bull_fvg_top
    df['fvg_bull_bot'] = bull_fvg_bot
    df['fvg_bear_top'] = bear_fvg_top
    df['fvg_bear_bot'] = bear_fvg_bot
    return df

def detect_order_block(df: pd.DataFrame, lookback=10):
    """Détecte les Order Blocks (OB)"""
    n = len(df)
    bos_up = df['bos_up'].values
    bos_down = df['bos_down'].values
    opens = df['open'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values

    ob_low = np.full(n, np.nan)
    ob_high = np.full(n, np.nan)
    ob_side = np.array(['none'] * n, dtype=object)

    down_candles = closes < opens
    up_candles = closes > opens

    for i in range(n):
        if bos_up[i]:
            start = max(0, i - lookback)
            window = down_candles[start:i]
            if np.any(window):
                idx = start + np.where(window)[0][-1]
                ob_low[i] = lows[idx]
                ob_high[i] = opens[idx]
                ob_side[i] = 'bull'
        elif bos_down[i]:
            start = max(0, i - lookback)
            window = up_candles[start:i]
            if np.any(window):
                idx = start + np.where(window)[0][-1]
                ob_low[i] = opens[idx]
                ob_high[i] = highs[idx]
                ob_side[i] = 'bear'

    df['ob_side'] = ob_side
    df['ob_low'] = ob_low
    df['ob_high'] = ob_high
    return df

def calculate_atr(df: pd.DataFrame, period=14):
    """Calcule l'ATR (Average True Range)"""
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)

    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]

    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        tr[i] = max(hl, hc, lc)

    atr = np.zeros(n)
    atr[period-1] = np.mean(tr[:period])

    for i in range(period, n):
        atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period

    df['atr'] = atr
    return df

def calculate_bos_strength(df: pd.DataFrame):
    """
    v2.0: Calcule la force (strength) de chaque BOS

    La force du BOS est la magnitude de la cassure relative a l'ATR.
    Un BOS fort indique un mouvement institutionnel significatif.

    Returns:
        df avec colonnes 'bos_strength' et 'bos_age' ajoutées
    """
    n = len(df)
    bos_up = df['bos_up'].values
    bos_down = df['bos_down'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    atrs = df['atr'].values
    swing_high = df['swing_high'].values
    swing_low = df['swing_low'].values

    bos_strength = np.zeros(n)
    bos_age = np.full(n, np.nan)

    # Track last swing high/low levels and indices
    last_sh_level = np.nan
    last_sl_level = np.nan
    last_sh_idx = -1
    last_sl_idx = -1

    for i in range(n):
        # Update swing levels
        if swing_high[i]:
            last_sh_level = highs[i]
            last_sh_idx = i
        if swing_low[i]:
            last_sl_level = lows[i]
            last_sl_idx = i

        # Calculate BOS strength when BOS occurs
        if bos_up[i] and not np.isnan(last_sh_level):
            # Bullish BOS - price broke above last swing high
            break_magnitude = closes[i] - last_sh_level
            if atrs[i] > 0:
                bos_strength[i] = break_magnitude / atrs[i]
            else:
                bos_strength[i] = 0.0
            bos_age[i] = i - last_sh_idx

        elif bos_down[i] and not np.isnan(last_sl_level):
            # Bearish BOS - price broke below last swing low
            break_magnitude = last_sl_level - closes[i]
            if atrs[i] > 0:
                bos_strength[i] = break_magnitude / atrs[i]
            else:
                bos_strength[i] = 0.0
            bos_age[i] = i - last_sl_idx

    df['bos_strength'] = bos_strength
    df['bos_age'] = bos_age
    return df

def detect_market_structure(df: pd.DataFrame, lookback=20):
    """
    v2.0: Detecte la structure de marche (HH/HL pour bullish, LL/LH pour bearish)

    Market structure is fundamental to ICT - we only trade when structure confirms direction:
    - Bullish structure: Series of Higher Highs (HH) and Higher Lows (HL)
    - Bearish structure: Series of Lower Lows (LL) and Lower Highs (LH)
    - Ranging: No clear structure

    Args:
        df: DataFrame with swing_high and swing_low columns
        lookback: Number of bars to analyze for structure

    Returns:
        df with 'market_structure' column ('bullish', 'bearish', 'ranging')
        and 'structure_score' column (numeric strength: +1 to -1)
    """
    n = len(df)
    swing_high = df['swing_high'].values
    swing_low = df['swing_low'].values
    highs = df['high'].values
    lows = df['low'].values

    market_structure = np.array(['ranging'] * n, dtype=object)
    structure_score = np.zeros(n)

    for i in range(lookback, n):
        # Get swing points in lookback window
        window_start = max(0, i - lookback)

        # Find swing highs in window
        sh_indices = [j for j in range(window_start, i) if swing_high[j]]
        sl_indices = [j for j in range(window_start, i) if swing_low[j]]

        if len(sh_indices) < 2 or len(sl_indices) < 2:
            # Not enough swings to determine structure
            market_structure[i] = 'ranging'
            structure_score[i] = 0.0
            continue

        # Get last 3 swing highs and lows
        recent_sh = sh_indices[-min(3, len(sh_indices)):]
        recent_sl = sl_indices[-min(3, len(sl_indices)):]

        sh_levels = [highs[j] for j in recent_sh]
        sl_levels = [lows[j] for j in recent_sl]

        # Check for Higher Highs (bullish)
        hh_count = sum(1 for k in range(1, len(sh_levels)) if sh_levels[k] > sh_levels[k-1])
        # Check for Higher Lows (bullish)
        hl_count = sum(1 for k in range(1, len(sl_levels)) if sl_levels[k] > sl_levels[k-1])

        # Check for Lower Lows (bearish)
        ll_count = sum(1 for k in range(1, len(sl_levels)) if sl_levels[k] < sl_levels[k-1])
        # Check for Lower Highs (bearish)
        lh_count = sum(1 for k in range(1, len(sh_levels)) if sh_levels[k] < sh_levels[k-1])

        # Calculate bullish and bearish signals
        bullish_signals = hh_count + hl_count
        bearish_signals = ll_count + lh_count
        total_signals = len(sh_levels) - 1 + len(sl_levels) - 1

        if total_signals == 0:
            market_structure[i] = 'ranging'
            structure_score[i] = 0.0
        elif bullish_signals > bearish_signals:
            market_structure[i] = 'bullish'
            # Score from 0 to 1
            structure_score[i] = bullish_signals / total_signals
        elif bearish_signals > bullish_signals:
            market_structure[i] = 'bearish'
            # Score from 0 to -1
            structure_score[i] = -bearish_signals / total_signals
        else:
            market_structure[i] = 'ranging'
            structure_score[i] = 0.0

    df['market_structure'] = market_structure
    df['structure_score'] = structure_score
    return df

def mark_fvg_mitigation(df: pd.DataFrame):
    """
    v2.0: Marque les FVGs comme "mitigated" quand le prix les touche

    An FVG is mitigated when price re-enters the gap zone. Mitigated FVGs
    lose their significance and should not be used for new trade signals.

    This prevents the strategy from repeatedly entering on the same exhausted gap.

    Returns:
        df with 'fvg_mitigated' column (boolean)
    """
    n = len(df)
    fvg_side = df['fvg_side'].values
    bull_top = df['fvg_bull_top'].values
    bull_bot = df['fvg_bull_bot'].values
    bear_top = df['fvg_bear_top'].values
    bear_bot = df['fvg_bear_bot'].values
    highs = df['high'].values
    lows = df['low'].values

    fvg_mitigated = np.zeros(n, dtype=bool)

    # Track active FVGs (index -> FVG data)
    active_fvgs = {}

    for i in range(n):
        # Register new FVG
        if fvg_side[i] == 'bull':
            active_fvgs[i] = {
                'side': 'bull',
                'top': bull_top[i],
                'bot': bull_bot[i],
                'mitigated': False
            }
        elif fvg_side[i] == 'bear':
            active_fvgs[i] = {
                'side': 'bear',
                'top': bear_top[i],
                'bot': bear_bot[i],
                'mitigated': False
            }

        # Check if current price mitigates any active FVG
        current_high = highs[i]
        current_low = lows[i]

        for fvg_idx, fvg_data in active_fvgs.items():
            if fvg_data['mitigated']:
                continue

            # Check if price entered the FVG zone
            if fvg_data['side'] == 'bull':
                # Bullish FVG is mitigated if price comes back down into it
                if current_low <= fvg_data['top'] and current_high >= fvg_data['bot']:
                    fvg_data['mitigated'] = True
                    fvg_mitigated[fvg_idx] = True

            elif fvg_data['side'] == 'bear':
                # Bearish FVG is mitigated if price comes back up into it
                if current_high >= fvg_data['bot'] and current_low <= fvg_data['top']:
                    fvg_data['mitigated'] = True
                    fvg_mitigated[fvg_idx] = True

    df['fvg_mitigated'] = fvg_mitigated
    return df

def enrich(df: pd.DataFrame):
    """
    Enrichit le DataFrame avec tous les indicateurs ICT

    v2.0: Pipeline enrichi avec validation BOS, mitigation FVG, et structure de marché
    """
    # Core ICT indicators (v1.0)
    df = swing_points(df, left=2, right=2)
    df = detect_bos(df)
    df = detect_fvg(df)
    df = detect_order_block(df, lookback=12)
    df = calculate_atr(df, period=14)

    # v2.0 Enhancements
    df = calculate_bos_strength(df)  # BOS strength and age
    df = detect_market_structure(df, lookback=20)  # HH/HL or LL/LH patterns
    df = mark_fvg_mitigation(df)  # Track if FVG was already used

    return df

def infer_bias(row) -> str:
    """Détermine le biais de marché (bull/bear/neutral)"""
    if row['bos_up'] and not row['bos_down']:
        return 'bull'
    if row['bos_down'] and not row['bos_up']:
        return 'bear'
    return 'neutral'

# ===============================
# SIGNALS + ENTRIES
# ===============================

def latest_fvg_confluence_row(df: pd.DataFrame, idx: int, max_lookback=50):
    """
    v2.0: Cherche le FVG le plus récent où le prix actuel est à l'intérieur
    avec validation stricte de confluence temporelle, mitigation, et structure de marché

    Filters applied (v2.0):
    - FVG mitigation: Ignore FVGs already touched by price
    - BOS recency: Only use BOS within last BOS_MAX_AGE bars
    - Temporal confluence: FVG and BOS must be within FVG_BOS_MAX_DISTANCE bars
    - Market structure: Confirm directional bias matches structure (HH/HL or LL/LH)
    """
    fvg_side = df['fvg_side'].values
    bull_top = df['fvg_bull_top'].values
    bull_bot = df['fvg_bull_bot'].values
    bear_top = df['fvg_bear_top'].values
    bear_bot = df['fvg_bear_bot'].values
    closes = df['close'].values

    # v2.0: FVG mitigation tracking
    fvg_mitigated = df['fvg_mitigated'].values if 'fvg_mitigated' in df.columns else np.zeros(len(df), dtype=bool)

    # v2.0: BOS recency tracking
    bos_up = df['bos_up'].values
    bos_down = df['bos_down'].values
    bos_age = df['bos_age'].values if 'bos_age' in df.columns else np.full(len(df), np.nan)

    # v2.0: Market structure
    market_structure = df['market_structure'].values if 'market_structure' in df.columns else np.array(['ranging'] * len(df))

    px = closes[idx]
    start = max(idx - max_lookback, 2)

    # Search backwards for valid FVG
    for j in range(idx - 1, start - 1, -1):
        side = fvg_side[j]

        # Skip if not an FVG
        if side == 'none':
            continue

        # v2.0: Skip if FVG was already mitigated
        if USE_FVG_MITIGATION_FILTER and fvg_mitigated[j]:
            continue

        # Check if price is inside FVG
        if side == 'bull':
            top = bull_top[j]
            bot = bull_bot[j]
            if np.isnan(top) or np.isnan(bot):
                continue
            if not (bot <= px <= top):
                continue

            # v2.0: Find nearest bullish BOS (search backwards from current idx)
            nearest_bos_idx = None
            search_start = max(0, idx - BOS_MAX_AGE if USE_BOS_RECENCY_FILTER else idx - 60)
            for bos_idx in range(idx, search_start - 1, -1):
                if bos_up[bos_idx]:
                    nearest_bos_idx = bos_idx
                    break

            if nearest_bos_idx is None:
                continue

            # v2.0: BOS recency filter
            if USE_BOS_RECENCY_FILTER:
                bos_distance_from_current = idx - nearest_bos_idx
                if bos_distance_from_current > BOS_MAX_AGE:
                    continue

            # v2.0: Temporal confluence - FVG and BOS should be reasonably close
            # Allow FVG to occur before or after BOS within the distance window
            fvg_bos_distance = abs(nearest_bos_idx - j)
            if fvg_bos_distance > FVG_BOS_MAX_DISTANCE:
                continue

            # v2.0: Market structure filter (allow ranging for more flexibility)
            if USE_MARKET_STRUCTURE_FILTER:
                current_structure = market_structure[idx]
                # Allow bullish or ranging for bullish FVG
                if current_structure == 'bearish':
                    continue

            # All filters passed
            mid = (top + bot) / 2.0
            return dict(side='bull', top=top, bot=bot, mid=mid, idx_fvg=j, idx_bos=nearest_bos_idx)

        elif side == 'bear':
            top = bear_top[j]
            bot = bear_bot[j]
            if np.isnan(top) or np.isnan(bot):
                continue
            if not (bot <= px <= top):
                continue

            # v2.0: Find nearest bearish BOS (search backwards from current idx)
            nearest_bos_idx = None
            search_start = max(0, idx - BOS_MAX_AGE if USE_BOS_RECENCY_FILTER else idx - 60)
            for bos_idx in range(idx, search_start - 1, -1):
                if bos_down[bos_idx]:
                    nearest_bos_idx = bos_idx
                    break

            if nearest_bos_idx is None:
                continue

            # v2.0: BOS recency filter
            if USE_BOS_RECENCY_FILTER:
                bos_distance_from_current = idx - nearest_bos_idx
                if bos_distance_from_current > BOS_MAX_AGE:
                    continue

            # v2.0: Temporal confluence - FVG and BOS should be reasonably close
            # Allow FVG to occur before or after BOS within the distance window
            fvg_bos_distance = abs(nearest_bos_idx - j)
            if fvg_bos_distance > FVG_BOS_MAX_DISTANCE:
                continue

            # v2.0: Market structure filter (allow ranging for more flexibility)
            if USE_MARKET_STRUCTURE_FILTER:
                current_structure = market_structure[idx]
                # Allow bearish or ranging for bearish FVG
                if current_structure == 'bullish':
                    continue

            # All filters passed
            mid = (top + bot) / 2.0
            return dict(side='bear', top=top, bot=bot, mid=mid, idx_fvg=j, idx_bos=nearest_bos_idx)

    return None

def make_features_for_ml(df, idx, fvg):
    """
    v2.0: Extrait 12 features pour le ML (vs 5 en v1.0)

    Features v1.0 (5):
    - gap: FVG size
    - range: Price range in last 50 bars
    - vol: Average volume
    - bias: Market bias (bull/bear/neutral)
    - kz: Kill zone (1/0)

    NEW Features v2.0 (7 additional):
    - atr_norm: ATR normalized by price (volatility context)
    - fvg_atr_ratio: FVG size / ATR (quality metric)
    - bos_proximity: Distance from current bar to BOS (recency)
    - momentum: Rate of change over 10 bars
    - structure_score: Market structure strength (-1 to +1)
    - bos_strength_norm: BOS break magnitude / ATR
    - position_in_fvg: Where price is within FVG (0-1)

    Total: 12 features
    """
    window = df.iloc[max(0, idx-50):idx]
    current_row = df.iloc[idx]

    # === v1.0 FEATURES (5) ===
    if len(window) < 10:
        rng = 1e-6
        vol = 0.0
    else:
        rng = (window['high'].max() - window['low'].min())
        vol = window['tick_volume'].mean()

    gap = abs(fvg['top'] - fvg['bot'])
    bias = 1 if infer_bias(current_row) == 'bull' else (-1 if infer_bias(current_row) == 'bear' else 0)
    kz = 1 if in_kill_zone(now_paris()) else 0

    # === v2.0 NEW FEATURES (7) ===

    # 1. atr_norm: ATR normalized by price (measures volatility context)
    atr_val = current_row.get('atr', 0.0)
    current_price = current_row['close']
    atr_norm = (atr_val / current_price) if current_price > 0 else 0.0

    # 2. fvg_atr_ratio: FVG size relative to ATR (quality of the gap)
    fvg_atr_ratio = (gap / atr_val) if atr_val > 0 else 0.0

    # 3. bos_proximity: How recent is the BOS (0 = very recent, 1 = old)
    idx_bos = fvg.get('idx_bos', idx)
    bos_distance = idx - idx_bos
    bos_proximity = min(bos_distance / 50.0, 1.0)  # Normalize to 0-1

    # 4. momentum: Rate of change over last 10 bars
    if len(window) >= 10:
        momentum = (current_row['close'] - window.iloc[-10]['close']) / window.iloc[-10]['close']
    else:
        momentum = 0.0

    # 5. structure_score: Market structure strength from detect_market_structure()
    structure_score = current_row.get('structure_score', 0.0)

    # 6. bos_strength_norm: BOS strength (from calculate_bos_strength)
    # Get BOS strength at idx_bos
    if 'bos_strength' in df.columns and idx_bos < len(df):
        bos_strength_norm = df.iloc[idx_bos].get('bos_strength', 0.0)
    else:
        bos_strength_norm = 0.0

    # 7. position_in_fvg: Where is price within the FVG (0=bottom, 1=top)
    fvg_top = fvg['top']
    fvg_bot = fvg['bot']
    fvg_range = fvg_top - fvg_bot
    if fvg_range > 0:
        position_in_fvg = (current_price - fvg_bot) / fvg_range
        position_in_fvg = max(0.0, min(1.0, position_in_fvg))  # Clamp to 0-1
    else:
        position_in_fvg = 0.5

    # === COMBINE ALL 12 FEATURES ===
    x = np.array([
        # v1.0 features (5)
        gap,
        rng,
        vol,
        bias,
        kz,
        # v2.0 new features (7)
        atr_norm,
        fvg_atr_ratio,
        bos_proximity,
        momentum,
        structure_score,
        bos_strength_norm,
        position_in_fvg
    ], dtype=float).reshape(1, -1)

    return x

class MLFilter:
    """Filtre ML avec meta-labelling et rolling window"""
    def __init__(self, model_path=None, use_meta_labelling=False):
        self.enabled = SKLEARN_OK
        self.use_meta_labelling = use_meta_labelling and SKLEARN_OK
        self.model_path = model_path
        self.X = []
        self.y = []
        self.min_samples = 40
        self.is_trained = False
        self.loaded_from_file = False

        if self.enabled:
            self.model = LogisticRegression(max_iter=500, class_weight='balanced')
            if self.use_meta_labelling and model_path and os.path.exists(model_path):
                self.load_model()
        else:
            self.model = None

    def load_model(self):
        """Charge le modèle ML avec rolling window"""
        if not self.enabled or not self.model_path:
            return False
        try:
            if os.path.exists(self.model_path):
                saved_data = joblib.load(self.model_path)
                self.model = saved_data['model']
                self.X = saved_data.get('X', [])
                self.y = saved_data.get('y', [])

                original_size = len(self.X)
                if len(self.X) > MAX_ML_SAMPLES:
                    self.X = self.X[-MAX_ML_SAMPLES:]
                    self.y = self.y[-MAX_ML_SAMPLES:]
                    self.model.fit(np.array(self.X), np.array(self.y))
                    print(f"[ML] Rolling window appliqué: {len(self.X)}/{MAX_ML_SAMPLES} samples conservés")

                self.is_trained = True
                self.loaded_from_file = True
                print(f"[ML] Modele charge depuis {self.model_path} ({len(self.X)} samples)")
                return True
        except Exception as e:
            print(f"[ML] Erreur chargement modele: {e}")
        return False

    def save_model(self):
        """Sauvegarde le modèle ML"""
        if not self.enabled or not self.model_path or not self.is_trained:
            return False
        try:
            # Créer le dossier parent si nécessaire
            model_dir = os.path.dirname(self.model_path)
            if model_dir and not os.path.exists(model_dir):
                os.makedirs(model_dir)

            saved_data = {
                'model': self.model,
                'X': self.X,
                'y': self.y,
                'timestamp': datetime.now().isoformat(),
                'samples': len(self.X)
            }
            joblib.dump(saved_data, self.model_path)
            print(f"[ML] Modele sauvegarde dans {self.model_path} ({len(self.X)} samples)")
            return True
        except Exception as e:
            print(f"[ML] Erreur sauvegarde modele: {e}")
        return False

    def fit_partial(self, X, y):
        """Entraîne le modèle avec rolling window"""
        if not self.enabled:
            return
        self.X.extend(X)
        self.y.extend(y)

        if len(self.X) > MAX_ML_SAMPLES:
            self.X = self.X[-MAX_ML_SAMPLES:]
            self.y = self.y[-MAX_ML_SAMPLES:]
            print(f"[ML] Rolling window appliqué: {len(self.X)}/{MAX_ML_SAMPLES} samples conservés")

        if len(self.X) >= self.min_samples:
            self.model.fit(np.array(self.X), np.array(self.y))
            self.is_trained = True
            if self.use_meta_labelling:
                self.save_model()

    def predict_proba(self, x):
        """
        v2.0: Prédit la probabilité de succès avec 12 features

        Fallback heuristic updated for v2.0 features
        """
        if self.use_meta_labelling and not self.loaded_from_file:
            return 0.99

        if not self.enabled or self.model is None or len(self.X) < self.min_samples:
            # Fallback heuristic using v2.0 features
            features = x.flatten()
            if len(features) >= 12:
                # v2.0: 12 features
                gap, rng, vol, bias, kz, atr_norm, fvg_atr_ratio, bos_proximity, momentum, structure_score, bos_strength_norm, position_in_fvg = features
            else:
                # v1.0: 5 features (backward compatibility)
                gap, rng, vol, bias, kz = features[:5]
                fvg_atr_ratio = 1.0
                bos_proximity = 0.5
                structure_score = 0.0

            if rng <= 0:
                return 0.5

            rel = gap / rng
            # Enhanced heuristic with v2.0 features
            base = 0.50
            base += 0.15 * rel  # FVG size relative to range
            base += 0.05 * kz  # Kill zone bonus
            base += 0.05 * (1 if bias != 0 else 0)  # Directional bias
            base += 0.10 * max(0, fvg_atr_ratio - 0.5)  # Quality gap bonus
            base += 0.05 * (1.0 - bos_proximity)  # Recent BOS bonus
            base += 0.05 * abs(structure_score)  # Structure strength bonus

            return float(max(0.0, min(0.95, base)))

        p = self.model.predict_proba(x)[0, 1]
        return float(p)

# ===============================
# BACKTEST
# ===============================

def backtest(df: pd.DataFrame, symbol="EURUSD", risk=RISK_PER_TRADE, rr=RR_TAKE_PROFIT,
             cooldown=COOLDOWN_BARS, use_killzones=True, ml: MLFilter=None, info=None):
    """Exécute un backtest complet"""
    pip = get_pip_size_from_info(info)
    pv_lot = pip_value_per_lot(info)

    equity0 = 10_000.0
    equity = equity0
    last_entry_bar = -cooldown
    open_trades = []
    history = []

    stats = {
        'cooldown_filtered': 0,
        'killzone_filtered': 0,
        'no_fvg': 0,
        'neutral_bias': 0,
        'fvg_bias_mismatch': 0,
        'ml_filtered': 0,
        'sl_too_close': 0,
        'max_trades_reached': 0,
        'atr_filtered': 0,
        'circuit_breaker_hit': 0,
        # v2.0 new stats
        'fvg_mitigated_filtered': 0,
        'bos_too_old_filtered': 0,
        'fvg_bos_too_far_filtered': 0,
        'market_structure_filtered': 0,
        'extreme_volatility_filtered': 0,
        'entries': 0
    }

    current_risk = risk
    last_3_results = []
    equity_day_start = equity0
    current_day = None
    circuit_breaker_active_today = False

    n = len(df)
    times = df['time'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values
    swing_high = df['swing_high'].values
    swing_low = df['swing_low'].values
    bos_up = df['bos_up'].values
    bos_down = df['bos_down'].values
    atrs = df['atr'].values if USE_ATR_FILTER else None

    for i in range(50, n):
        t = times[i]
        px = closes[i]
        hi = highs[i]
        lo = lows[i]

        # Circuit breaker
        if USE_CIRCUIT_BREAKER:
            t_day = pd.Timestamp(t).date()
            if current_day is None or t_day != current_day:
                current_day = t_day
                equity_day_start = equity
                circuit_breaker_active_today = False

            if equity != equity_day_start:
                daily_dd = (equity - equity_day_start) / equity_day_start
                if daily_dd < -DAILY_DD_LIMIT:
                    if not circuit_breaker_active_today:
                        stats['circuit_breaker_hit'] += 1
                        circuit_breaker_active_today = True
                        print(f"[!] Circuit breaker active le {t_day} : DD journalier {daily_dd*100:.2f}%")
                    continue

        # Gérer les trades ouverts
        still_open = []
        for tr in open_trades:
            hit_sl = (lo <= tr['sl']) if tr['side']=='buy' else (hi >= tr['sl'])
            hit_tp = (hi >= tr['tp']) if tr['side']=='buy' else (lo <= tr['tp'])
            res = None
            if hit_sl and hit_tp:
                res = ('SL', tr['sl'])
            elif hit_sl:
                res = ('SL', tr['sl'])
            elif hit_tp:
                res = ('TP', tr['tp'])
            if res:
                kind, price = res
                R = abs(tr['entry']-tr['sl'])
                gain = (rr * R) if kind=='TP' else (-R)
                pnl_money = (gain / pip) * pv_lot
                equity += pnl_money
                history.append(dict(time=t, action=kind, side=tr['side'],
                                    entry=tr['entry'], exit=price, equity=equity))

                if ml is not None and ml.use_meta_labelling and 'features' in tr and tr['features'] is not None:
                    label = 1 if kind == 'TP' else 0
                    ml.fit_partial([tr['features'].flatten().tolist()], [label])

                if USE_ADAPTIVE_RISK:
                    last_3_results.append(1 if kind == 'TP' else 0)
                    if len(last_3_results) > 2:
                        last_3_results.pop(0)
                    if len(last_3_results) == 2 and sum(last_3_results) == 0:
                        current_risk *= RISK_REDUCTION_FACTOR
                    elif kind == 'TP' and current_risk < risk * 0.9:
                        current_risk = min(risk, current_risk / RISK_REDUCTION_FACTOR)
            else:
                still_open.append(tr)
        open_trades = still_open

        # Filtres d'entrée
        if (i - last_entry_bar) < cooldown:
            stats['cooldown_filtered'] += 1
            continue

        if use_killzones:
            if TZ_OK:
                t_pd = pd.Timestamp(t)
                if t_pd.tzinfo is None:
                    t_local = t_pd.tz_localize("UTC").astimezone(TZ_PARIS)
                else:
                    t_local = t_pd.astimezone(TZ_PARIS)
            else:
                t_local = pd.Timestamp(t)
            if not in_kill_zone(t_local):
                stats['killzone_filtered'] += 1
                continue
            session_rr = get_session_rr(t_local)
        else:
            session_rr = rr

        # Calculer le biais
        if bos_up[i] and not bos_down[i]:
            bias = 'bull'
        elif bos_down[i] and not bos_up[i]:
            bias = 'bear'
        else:
            bias = 'neutral'

        fvg = latest_fvg_confluence_row(df, i, max_lookback=60)
        if fvg is None:
            stats['no_fvg'] += 1
            continue
        if bias == 'neutral':
            stats['neutral_bias'] += 1
            continue

        # Filtrage ATR
        if USE_ATR_FILTER and atrs is not None:
            fvg_size = abs(fvg['top'] - fvg['bot'])
            atr_val = atrs[i]
            if atr_val > 0 and fvg_size < atr_val * ATR_FVG_MIN_RATIO:
                stats['atr_filtered'] += 1
                continue

        side = None
        if bias == 'bull' and fvg['side']=='bull':
            side = 'buy'
        elif bias == 'bear' and fvg['side']=='bear':
            side = 'sell'
        if side is None:
            stats['fvg_bias_mismatch'] += 1
            continue

        # v2.0: Extreme volatility filter (skip trades during news events)
        if USE_EXTREME_VOLATILITY_FILTER and atrs is not None:
            atr_val = atrs[i]
            # Calculate median ATR over last 100 bars
            window_start = max(0, i - 100)
            atr_window = atrs[window_start:i]
            median_atr = np.median(atr_window[atr_window > 0]) if len(atr_window[atr_window > 0]) > 0 else atr_val
            if median_atr > 0 and atr_val > median_atr * VOLATILITY_MULTIPLIER_MAX:
                stats['extreme_volatility_filtered'] += 1
                continue

        # ML filter
        if ml is not None:
            x = make_features_for_ml(df, i, fvg)
            p = ml.predict_proba(x)
            if p < ML_THRESHOLD:
                stats['ml_filtered'] += 1
                continue
        else:
            p = 0.5

        # v2.0: SL/TP calculation with Order Block priority
        entry = px
        ob_low = df['ob_low'].values if 'ob_low' in df.columns else None
        ob_high = df['ob_high'].values if 'ob_high' in df.columns else None
        ob_side = df['ob_side'].values if 'ob_side' in df.columns else None

        if side == 'buy':
            # v2.0: Try to use Order Block for SL first
            sl = None
            if USE_ORDER_BLOCK_SL and ob_low is not None and ob_side is not None:
                # Find nearest bullish Order Block
                for j in range(i-1, max(0, i-60), -1):
                    if ob_side[j] == 'bull' and not np.isnan(ob_low[j]):
                        sl = float(ob_low[j])
                        break

            # Fallback to swing lows if no Order Block found
            if sl is None:
                start = max(0, i - 60)
                window_swing = swing_low[start:i]
                window_lows = lows[start:i]
                swing_indices = np.where(window_swing)[0]
                if len(swing_indices) > 0:
                    sl = float(window_lows[swing_indices].min())
                else:
                    sl = float(lo - 8*pip)

            dist = entry - sl
            if dist <= 2*pip:
                stats['sl_too_close'] += 1
                continue
            tp = entry + session_rr * dist

        else:  # side == 'sell'
            # v2.0: Try to use Order Block for SL first
            sl = None
            if USE_ORDER_BLOCK_SL and ob_high is not None and ob_side is not None:
                # Find nearest bearish Order Block
                for j in range(i-1, max(0, i-60), -1):
                    if ob_side[j] == 'bear' and not np.isnan(ob_high[j]):
                        sl = float(ob_high[j])
                        break

            # Fallback to swing highs if no Order Block found
            if sl is None:
                start = max(0, i - 60)
                window_swing = swing_high[start:i]
                window_highs = highs[start:i]
                swing_indices = np.where(window_swing)[0]
                if len(swing_indices) > 0:
                    sl = float(window_highs[swing_indices].max())
                else:
                    sl = float(hi + 8*pip)

            dist = sl - entry
            if dist <= 2*pip:
                stats['sl_too_close'] += 1
                continue
            tp = entry - session_rr * dist

        if len(open_trades) >= MAX_CONCURRENT_TRADES:
            stats['max_trades_reached'] += 1
            continue

        stats['entries'] += 1
        trade_features = x if ml is not None else None
        open_trades.append(dict(side=side, entry=entry, sl=sl, tp=tp, idx_entry=i, prob=p, features=trade_features))
        last_entry_bar = i
        history.append(dict(time=t, action='ENTRY', side=side, entry=entry, sl=sl, tp=tp, equity=equity, prob=p))

    # Fermer les trades ouverts
    if open_trades:
        last_px = df.iloc[-1]['close']
        for tr in open_trades:
            gain = (last_px - tr['entry']) if tr['side']=='buy' else (tr['entry'] - last_px)
            pnl_money = (gain / pip) * pip_value_per_lot(info)
            history.append(dict(time=df.iloc[-1]['time'], action='CLOSE', side=tr['side'],
                                entry=tr['entry'], exit=last_px, equity=np.nan))

    # Métriques
    hist_df = pd.DataFrame(history)
    if len(hist_df)==0:
        metrics = dict(trades=0, winrate=0.0, pnl=0.0, dd=0.0, eq_final=equity0, stats=stats)
        return metrics, hist_df

    eq_series = hist_df.dropna(subset=['equity'])['equity'].values
    if len(eq_series)==0:
        eq_series = np.array([equity0])
    eq_final = eq_series[-1]
    pnl = eq_final - equity0

    n_tp = (hist_df['action']=='TP').sum()
    n_sl = (hist_df['action']=='SL').sum()
    trades = n_tp + n_sl
    winrate = (n_tp / trades)*100.0 if trades>0 else 0.0

    peak = -1e18
    mdd = 0.0
    for v in eq_series:
        peak = max(peak, v)
        if peak>0:
            mdd = min(mdd, (v-peak)/peak)
    dd_pct = mdd*100.0

    metrics = dict(trades=int(trades), winrate=winrate, pnl=pnl, dd=dd_pct, eq_final=eq_final, stats=stats)
    return metrics, hist_df

def plot_backtest(df: pd.DataFrame, hist_df: pd.DataFrame, title="Backtest ICT"):
    """Affiche les résultats du backtest"""
    if not MPL_OK:
        print("Matplotlib indisponible. Aucun graphique.")
        return

    plt.figure(figsize=(12,7))
    plt.plot(df['time'], df['close'], label='Close', linewidth=0.8, alpha=0.9)

    fvg_mask = df['fvg_side'].values != 'none'
    fvg_indices = np.where(fvg_mask)[0]
    show_idx = fvg_indices[-min(50, len(fvg_indices)):] if len(fvg_indices) > 0 else []

    fvg_side = df['fvg_side'].values
    bull_top = df['fvg_bull_top'].values
    bull_bot = df['fvg_bull_bot'].values
    bear_top = df['fvg_bear_top'].values
    bear_bot = df['fvg_bear_bot'].values
    times = df['time'].values

    for i in show_idx:
        side = fvg_side[i]
        if side == 'bull':
            top = bull_top[i]
            bot = bull_bot[i]
            color = 'green'
        else:
            top = bear_top[i]
            bot = bear_bot[i]
            color = 'red'

        if not (np.isnan(top) or np.isnan(bot)):
            t0 = times[i]
            t1 = times[min(i+10, len(df)-1)]
            plt.fill_between([t0, t1], [top, top], [bot, bot],
                           alpha=0.15, color=color, step='post')

    if len(hist_df) > 0:
        e = hist_df[hist_df['action']=='ENTRY']
        tp = hist_df[hist_df['action']=='TP']
        sl = hist_df[hist_df['action']=='SL']
        if len(e) > 0:
            plt.scatter(e['time'], e['entry'], marker='o', s=50, label='Entry', c='blue', zorder=5)
        if len(tp) > 0:
            plt.scatter(tp['time'], tp.get('exit', tp.get('tp', np.nan)),
                       marker='^', s=60, label='TP (Win)', c='green', zorder=5)
        if len(sl) > 0:
            plt.scatter(sl['time'], sl.get('exit', sl.get('sl', np.nan)),
                       marker='v', s=60, label='SL (Loss)', c='red', zorder=5)

    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel('Time', fontsize=10)
    plt.ylabel('Price', fontsize=10)
    plt.legend(loc='upper left', fontsize=9)
    plt.grid(alpha=0.3, linestyle='--', linewidth=0.5)
    plt.tight_layout()
    plt.show()

# ===============================
# LIVE MT5
# ===============================

def ensure_mt5_and_symbol(symbol):
    if not MT5_OK:
        raise RuntimeError("MetaTrader5 non disponible.")
    if not mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
        raise RuntimeError("Connexion MT5 échouée.")
    if not mt5.symbol_select(symbol, True):
        mt5.shutdown()
        raise RuntimeError(f"Symbole {symbol} indisponible.")
    info = mt5.symbol_info(symbol)
    if info is None or not info.visible:
        mt5.shutdown()
        raise RuntimeError(f"Infos symbole invalides pour {symbol}.")
    return info

def send_telegram_notification(symbol, side, entry, sl, tp, volume=None):
    """
    Envoie une notification Telegram quand une position est ouverte
    Args:
        symbol: Symbole trade (ex: EURUSD)
        side: Direction (buy/sell)
        entry: Prix d'entree
        sl: Stop Loss
        tp: Take Profit
        volume: Volume du trade (optionnel)
    """
    if not TELEGRAM_ENABLED or not REQUESTS_OK:
        return

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] Token ou Chat ID manquant - notification non envoyee")
        return

    # Direction emoji
    direction_emoji = "📈" if side.lower() == "buy" else "📉"

    # Calculer le risque en pips
    pip_risk = abs(entry - sl)

    # Formatage du message
    message = f"""
🔔 *Nouvelle Position Ouverte*

{direction_emoji} *{side.upper()}* {symbol}

📍 *Entree*: {entry:.5f}
🎯 *Take Profit*: {tp:.5f}
🛑 *Stop Loss*: {sl:.5f}

📊 *Risque*: {pip_risk:.5f}
⏰ *Heure*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    if volume is not None:
        message += f"💰 *Volume*: {volume:.2f} lots\n"

    # Envoyer le message
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[TELEGRAM] Notification envoyee avec succes")
        else:
            print(f"[TELEGRAM] Erreur {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[TELEGRAM] Erreur d'envoi: {e}")

def place_market_order(symbol, side, sl, tp, info, df=None):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return False, "NoTick"

    price = tick.ask if side=='buy' else tick.bid
    tf = mt5.ORDER_TYPE_BUY if side=='buy' else mt5.ORDER_TYPE_SELL

    acc = mt5.account_info()
    balance = acc.balance if acc else 10_000.0
    pip = get_pip_size_from_info(info)
    pv_lot = pip_value_per_lot(info)
    dist_pips = abs(price - sl) / pip
    if dist_pips < 0.5:
        vol = max(info.volume_min, info.volume_min)
    else:
        risk_money = balance * RISK_PER_TRADE
        vol = (risk_money / (dist_pips * pv_lot))
        vol = max(info.volume_min, min(info.volume_max, round(vol / info.volume_step) * info.volume_step))

    if df is not None and len(df) >= 100:
        median_spread = np.median(df['spread'].values[-100:])
        current_spread = info.spread
        if current_spread > median_spread * 1.5:
            filling = mt5.ORDER_FILLING_IOC
        else:
            # Vérifie si le symbole supporte FOK (bit 0 du masque filling_mode)
            filling = mt5.ORDER_FILLING_FOK if (info.filling_mode & 1) else mt5.ORDER_FILLING_IOC
    else:
        # Vérifie si le symbole supporte FOK (bit 0 du masque filling_mode)
        filling = mt5.ORDER_FILLING_FOK if (info.filling_mode & 1) else mt5.ORDER_FILLING_IOC

    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(vol),
        "type": tf,
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": COMMENT[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }
    res = mt5.order_send(req)
    if res is None:
        err = mt5.last_error()
        return False, f"order_send(None) err={err}"
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        return False, f"retcode={res.retcode}"

    # Envoyer notification Telegram si l'ordre a reussi
    send_telegram_notification(symbol, side, price, sl, tp, vol)

    return True, f"ticket={res.order or res.deal}"

def live_loop(symbol=SYMBOL_DEFAULT, timeframe="M1", ml_model_path=None):
    info = ensure_mt5_and_symbol(symbol)
    tf_code = MT5_TF_MAP.get(timeframe, mt5.TIMEFRAME_M1)
    pip = get_pip_size_from_info(info)

    print(f"[LIVE] Demarre - {symbol} {timeframe}")
    print(f"[LIVE] Chargement de 100,000 barres d'historique pour entrainer le modele ML...")

    # Charger 100k barres au demarrage pour le ML (avec chunking)
    try:
        df_initial = load_rates_mt5(symbol, tf_code, 100000)
        print(f"[LIVE] {len(df_initial)} barres chargees avec succes")
    except Exception as e:
        print(f"[!] Erreur chargement initial: {e}")
        print(f"[LIVE] Chargement de 10,000 barres de secours...")
        rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, 10000)
        if rates is None:
            print("[!] Impossible de charger les donnees. Arret.")
            return
        df_initial = df_from_rates(rates)

    # NOUVEAU: Backtest automatique au démarrage pour entraîner le ML
    print(f"[LIVE] Enrichissement des donnees historiques...")
    df_initial = enrich(df_initial)

    print(f"[LIVE] Lancement du backtest initial pour entrainer le modele ML...")
    ml = MLFilter(model_path=ml_model_path, use_meta_labelling=USE_ML_META_LABELLING)

    if USE_ML_META_LABELLING:
        # Faire un backtest rapide pour entraîner le ML
        metrics, _ = backtest(df_initial, symbol=symbol, risk=RISK_PER_TRADE,
                              rr=RR_TAKE_PROFIT, cooldown=COOLDOWN_BARS,
                              use_killzones=True, ml=ml, info=info)

        print(f"[LIVE] Backtest initial termine:")
        print(f"       - Trades: {metrics['trades']}")
        print(f"       - Winrate: {metrics['winrate']:.1f}%")
        print(f"       - Samples ML: {len(ml.X)}")
        print(f"       - Modele entraine: {ml.is_trained}")

        if ml.is_trained:
            print(f"[LIVE] Modele ML pret et sauvegarde dans {ml_model_path}")
        else:
            print(f"[LIVE] ATTENTION: Pas assez de trades pour entrainer le ML (min {ml.min_samples})")
    else:
        print(f"[LIVE] ML Meta-labelling desactive dans la config")

    cooldown = 0
    last_bar_time = None

    print(f"[LIVE] Bot pret - Surveillance active des signaux ICT...")

    while True:
        # Dans la boucle, charger moins de barres pour la performance
        rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, 5000)
        if rates is None:
            time.sleep(1)
            continue
        df = enrich(df_from_rates(rates))
        cur_time = df.iloc[-1]['time']
        if last_bar_time is not None and cur_time == last_bar_time:
            time.sleep(0.5)
            continue
        last_bar_time = cur_time

        i = len(df)-1
        if cooldown>0:
            cooldown -= 1
            continue

        t_local = cur_time.tz_localize("UTC").astimezone(TZ_PARIS) if TZ_OK else cur_time
        if not in_kill_zone(t_local):
            continue

        bias = infer_bias(df.iloc[i])
        fvg = latest_fvg_confluence_row(df, i, max_lookback=60)
        if fvg is None or bias=='neutral':
            continue

        if USE_ATR_FILTER:
            fvg_size = abs(fvg['top'] - fvg['bot'])
            atr_val = df.at[i, 'atr']
            if atr_val > 0 and fvg_size < atr_val * ATR_FVG_MIN_RATIO:
                continue

        # v2.0: Extreme volatility filter
        if USE_EXTREME_VOLATILITY_FILTER:
            atr_val = df.at[i, 'atr']
            window_start = max(0, i - 100)
            atr_window = df.iloc[window_start:i]['atr'].values
            median_atr = np.median(atr_window[atr_window > 0]) if len(atr_window[atr_window > 0]) > 0 else atr_val
            if median_atr > 0 and atr_val > median_atr * VOLATILITY_MULTIPLIER_MAX:
                print(f"[LIVE] Volatilite extreme detectee (ATR={atr_val:.5f} > {median_atr*VOLATILITY_MULTIPLIER_MAX:.5f}), trade ignore")
                continue

        side = 'buy' if (bias=='bull' and fvg['side']=='bull') else ('sell' if (bias=='bear' and fvg['side']=='bear') else None)
        if side is None:
            continue

        # v2.0: SL/TP with Order Block priority
        entry = df.at[i, 'close']
        if side=='buy':
            # v2.0: Try Order Block first
            sl = None
            if USE_ORDER_BLOCK_SL and 'ob_low' in df.columns and 'ob_side' in df.columns:
                for j in range(i-1, max(0, i-60), -1):
                    if df.at[j, 'ob_side'] == 'bull' and not pd.isna(df.at[j, 'ob_low']):
                        sl = float(df.at[j, 'ob_low'])
                        break

            # Fallback to swing lows
            if sl is None:
                slice_df = df.iloc[max(0,i-60):i]
                cands = slice_df[slice_df['swing_low']]
                sl = float(cands['low'].min()) if len(cands) else float(df.at[i,'low'] - 8*pip)

            dist = entry - sl
            if dist <= 2*pip:
                continue
            tp = entry + RR_TAKE_PROFIT * dist

        else:  # sell
            # v2.0: Try Order Block first
            sl = None
            if USE_ORDER_BLOCK_SL and 'ob_high' in df.columns and 'ob_side' in df.columns:
                for j in range(i-1, max(0, i-60), -1):
                    if df.at[j, 'ob_side'] == 'bear' and not pd.isna(df.at[j, 'ob_high']):
                        sl = float(df.at[j, 'ob_high'])
                        break

            # Fallback to swing highs
            if sl is None:
                slice_df = df.iloc[max(0,i-60):i]
                cands = slice_df[slice_df['swing_high']]
                sl = float(cands['high'].max()) if len(cands) else float(df.at[i,'high'] + 8*pip)

            dist = sl - entry
            if dist <= 2*pip:
                continue
            tp = entry - RR_TAKE_PROFIT * dist

        x = make_features_for_ml(df, i, fvg)
        prob = ml.predict_proba(x)
        if prob < ML_THRESHOLD:
            continue

        ok, msg = place_market_order(symbol, side, sl, tp, info, df=df)
        print(f"{datetime.now()} -> {side.upper()} entry={entry:.5f} SL={sl:.5f} TP={tp:.5f} | {msg}")
        if ok:
            cooldown = COOLDOWN_BARS
        time.sleep(0.5)

# ===============================
# DASHBOARD
# ===============================

def launch_tk_dashboard(symbol=SYMBOL_DEFAULT, timeframe="M1"):
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        print("Tkinter indisponible.")
        return

    root = tk.Tk()
    root.title("ICT Bot Dashboard")

    lbl = ttk.Label(root, text=f"Symbole: {symbol} | TF: {timeframe}", font=("Segoe UI", 12))
    lbl.pack(pady=4)

    bias_var = tk.StringVar(value="Neutral")
    prob_var = tk.StringVar(value="—")
    kz_var = tk.StringVar(value="—")

    frame = ttk.Frame(root)
    frame.pack(padx=8, pady=8, fill="x")

    ttk.Label(frame, text="Biais").grid(row=0, column=0, sticky="w")
    ttk.Label(frame, textvariable=bias_var).grid(row=0, column=1, sticky="w")
    ttk.Label(frame, text="Prob(ML)").grid(row=1, column=0, sticky="w")
    ttk.Label(frame, textvariable=prob_var).grid(row=1, column=1, sticky="w")
    ttk.Label(frame, text="Kill Zone").grid(row=2, column=0, sticky="w")
    ttk.Label(frame, textvariable=kz_var).grid(row=2, column=1, sticky="w")

    run_var = tk.BooleanVar(value=False)

    def updater():
        if not run_var.get():
            root.after(1000, updater)
            return
        try:
            if MT5_OK and mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
                tf_code = MT5_TF_MAP.get(timeframe, mt5.TIMEFRAME_M1)
                rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, 10000)
                if rates is not None:
                    df = enrich(df_from_rates(rates))
                    i = len(df)-1
                    bias = infer_bias(df.iloc[i]).capitalize()
                    fvg = latest_fvg_confluence_row(df, i, 60)
                    prob = "—"
                    if fvg:
                        x = make_features_for_ml(df, i, fvg)
                        prob = f"{MLFilter().predict_proba(x)*100:.1f}%"
                    bias_var.set(bias)
                    kz_var.set("Oui" if in_kill_zone(now_paris()) else "Non")
                    prob_var.set(prob)
                mt5.shutdown()
        except Exception:
            pass
        root.after(1500, updater)

    def toggle():
        run_var.set(not run_var.get())
        btn.configure(text="Stop" if run_var.get() else "Start")

    btn = ttk.Button(root, text="Start", command=toggle)
    btn.pack(pady=8)

    root.after(500, updater)
    root.mainloop()

def run_streamlit(symbol=SYMBOL_DEFAULT, timeframe="M1"):
    try:
        import streamlit as st
    except Exception:
        print("Streamlit non disponible.")
        return

    st.set_page_config(page_title="ICT Bot", layout="wide")
    st.title("ICT Bot Dashboard")

    col1, col2, col3 = st.columns(3)
    with col1: st.write(f"**Symbole**: {symbol}")
    with col2: st.write(f"**TF**: {timeframe}")
    with col3: st.write(f"**Kill Zone**: {'Oui' if in_kill_zone(now_paris()) else 'Non'}")

    if MT5_OK and st.button("Rafraîchir"):
        if mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
            tf_code = MT5_TF_MAP.get(timeframe, mt5.TIMEFRAME_M1)
            rates = mt5.copy_rates_from_pos(symbol, tf_code, 0, 500)
            if rates is not None:
                df = enrich(df_from_rates(rates))
                st.line_chart(df.set_index('time')['close'])
                i = len(df)-1
                bias = infer_bias(df.iloc[i])
                st.write(f"**Biais**: {bias}")
                fvg = latest_fvg_confluence_row(df, i, 60)
                if fvg:
                    x = make_features_for_ml(df, i, fvg)
                    p = MLFilter().predict_proba(x)
                    st.write(f"**Prob(ML)**: {p*100:.1f}%")
            mt5.shutdown()
    else:
        st.info("Clique sur Rafraîchir pour mettre à jour.")

# ===============================
# MAIN
# ===============================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, default="backtest",
                        help="backtest | live | dashboard | streamlit")
    parser.add_argument("--symbol", type=str, default=SYMBOL_DEFAULT)
    parser.add_argument("--timeframe", type=str, default=TIMEFRAME_DEFAULT)
    parser.add_argument("--bars", type=int, default=None,
                        help="Nombre de barres")
    parser.add_argument("--no-plot", action="store_true",
                        help="Désactiver l'affichage des graphiques")
    parser.add_argument("--no-ml", action="store_true",
                        help="Désactiver le ML meta-labelling (pour grid search rapide)")
    parser.add_argument("--bot-name", type=str, default=None,
                        help="Nom du bot (pour le modèle ML)")
    parser.add_argument("--ml-model-path", type=str, default=None,
                        help="Chemin du fichier modèle ML (doit être dans machineLearning/)")
    parser.add_argument("--config-name", type=str, default="Default",
                        help="Nom de la configuration à utiliser (depuis config/)")
    args = parser.parse_args()

    # Charger la configuration depuis config/{config_name}.json AVANT tout le reste
    load_config_from_file(args.config_name)

    symbol = args.symbol
    timeframe = args.timeframe.upper()
    ml_model_path = args.ml_model_path

    if args.bars is None:
        bars = BARS_PER_TIMEFRAME.get(timeframe, BARS_DEFAULT)
    else:
        bars = args.bars

    if args.mode == "backtest":
        print(f"[*] Utilisation de {bars} barres pour {timeframe} (~{BACKTEST_MONTHS} mois)")
        if not MT5_OK:
            print("MetaTrader5 non disponible.")
            return
        info = None
        if mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
            if mt5.symbol_select(symbol, True):
                info = mt5.symbol_info(symbol)

                tf_code = MT5_TF_MAP.get(timeframe, mt5.TIMEFRAME_M5)
                print(f"[*] Chargement de {bars} barres depuis MT5...")
                df = enrich(load_rates_mt5(symbol, tf_code, bars))

                if len(df) > 0:
                    start_date = df['time'].iloc[0]
                    end_date = df['time'].iloc[-1]
                    period_days = (end_date - start_date).days
                    period_months = period_days / 30.0
                    print(f"[OK] {len(df)} barres chargees")
                    print(f"[*] Periode : {start_date.strftime('%Y-%m-%d')} -> {end_date.strftime('%Y-%m-%d')}")
                    print(f"[*] Duree : {period_days} jours ({period_months:.1f} mois)")
                else:
                    print("[ERREUR] Aucune barre chargee !")
                    return

                # CORRECTION: Le --no-plot ne doit PAS désactiver le ML
                # Mais le --no-ml le désactive pour grid search rapide
                ml_enabled = USE_ML_META_LABELLING and not args.no_ml
                ml_filter = MLFilter(
                    model_path=ml_model_path if ml_enabled else None,
                    use_meta_labelling=ml_enabled
                )

                if USE_ML_META_LABELLING:
                    print(f"[ML] Meta-labelling: {ml_filter.use_meta_labelling}")
                    print(f"[ML] Modele entraine: {ml_filter.is_trained}")
                    print(f"[ML] Samples: {len(ml_filter.X)}")

                metrics, hist = backtest(df, symbol=symbol, risk=RISK_PER_TRADE,
                                         rr=RR_TAKE_PROFIT, cooldown=COOLDOWN_BARS,
                                         use_killzones=True, ml=ml_filter, info=info)

                st = metrics['stats']
                total_bars = len(df) - 50
                print(f"\n=== STATISTIQUES DE FILTRAGE v2.0 ===")
                print(f"Barres analysees: {total_bars}")
                print(f"|- Cooldown: {st['cooldown_filtered']}")
                print(f"|- Kill zones: {st['killzone_filtered']}")
                print(f"|- Pas de FVG: {st['no_fvg']}")
                print(f"|- Biais neutre: {st['neutral_bias']}")
                print(f"|- FVG/Biais incompatibles: {st['fvg_bias_mismatch']}")
                print(f"|- Filtrees par ATR: {st['atr_filtered']}")
                print(f"[v2.0 FILTERS]")
                print(f"|- FVG deja mitiges: {st.get('fvg_mitigated_filtered', 0)}")
                print(f"|- BOS trop ancien: {st.get('bos_too_old_filtered', 0)}")
                print(f"|- FVG-BOS trop eloignes: {st.get('fvg_bos_too_far_filtered', 0)}")
                print(f"|- Structure de marche: {st.get('market_structure_filtered', 0)}")
                print(f"|- Volatilite extreme: {st.get('extreme_volatility_filtered', 0)}")
                print(f"[FINAL FILTERS]")
                print(f"|- Filtrees par ML: {st['ml_filtered']}")
                print(f"|- SL trop proche: {st['sl_too_close']}")
                print(f"|- Max trades atteint: {st['max_trades_reached']}")
                print(f"|- Circuit breaker: {st['circuit_breaker_hit']}")
                print(f"'- Entrees validees: {st['entries']}\n")

                print(f"=== METRICS ({symbol} {timeframe}) ===")
                print(f"Trades: {metrics['trades']} | Winrate: {metrics['winrate']:.1f}% | "
                      f"PnL: {metrics['pnl']:.2f} | MaxDD: {metrics['dd']:.2f}% | "
                      f"Equity finale: {metrics['eq_final']:.2f}")

                if USE_ML_META_LABELLING and ml_filter.is_trained:
                    print(f"\n=== ML META-LABELLING ===")
                    print(f"Samples: {len(ml_filter.X)}")
                    print(f"Wins: {sum(ml_filter.y)} ({sum(ml_filter.y)/len(ml_filter.y)*100:.1f}%)")
                    print(f"Losses: {len(ml_filter.y) - sum(ml_filter.y)}")

                try:
                    # Creer le dossier backtest s'il n'existe pas
                    os.makedirs("backtest", exist_ok=True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"backtest/backtest_{symbol}_{timeframe}_{timestamp}.json"
                    json_data = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "bars": bars,
                        "period_days": period_days,
                        "period_months": period_months,
                        "timestamp": timestamp,
                        "metrics": {
                            "trades": int(metrics['trades']),
                            "winrate": float(metrics['winrate']),
                            "pnl": float(metrics['pnl']),
                            "max_dd": float(metrics['dd']),
                            "equity_final": float(metrics['eq_final'])
                        },
                        "statistics": {k: int(v) for k, v in st.items()},
                        "config": {
                            "RISK_PER_TRADE": RISK_PER_TRADE,
                            "RR_TAKE_PROFIT": RR_TAKE_PROFIT,
                            "MAX_CONCURRENT_TRADES": MAX_CONCURRENT_TRADES,
                            "COOLDOWN_BARS": COOLDOWN_BARS,
                            "ML_THRESHOLD": ML_THRESHOLD,
                            "USE_SESSION_ADAPTIVE_RR": USE_SESSION_ADAPTIVE_RR,
                            "RR_LONDON": RR_LONDON,
                            "RR_NEWYORK": RR_NEWYORK,
                            "RR_DEFAULT": RR_DEFAULT,
                            "USE_ML_META_LABELLING": USE_ML_META_LABELLING,
                            "MAX_ML_SAMPLES": MAX_ML_SAMPLES,
                            "USE_ATR_FILTER": USE_ATR_FILTER,
                            "ATR_FVG_MIN_RATIO": ATR_FVG_MIN_RATIO,
                            "ATR_FVG_MAX_RATIO": ATR_FVG_MAX_RATIO,
                            "USE_CIRCUIT_BREAKER": USE_CIRCUIT_BREAKER,
                            "DAILY_DD_LIMIT": DAILY_DD_LIMIT,
                            "USE_ADAPTIVE_RISK": USE_ADAPTIVE_RISK
                        }
                    }
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(json_data, f, indent=2)
                    print(f"[SAVE] Resultats: {filename}")
                except Exception as e:
                    print(f"[!] Erreur sauvegarde JSON: {e}")

                if MPL_OK and not args.no_plot:
                    plot_backtest(df, hist, title=f"Backtest ICT — {symbol} {timeframe}")
            mt5.shutdown()
        else:
            print("Connexion MT5 échouée.")
    elif args.mode == "live":
        live_loop(symbol=symbol, timeframe=timeframe, ml_model_path=ml_model_path)
    elif args.mode == "dashboard":
        launch_tk_dashboard(symbol=symbol, timeframe=timeframe)
    elif args.mode == "streamlit":
        run_streamlit(symbol=symbol, timeframe=timeframe)
    else:
        print("Mode inconnu. Utilise --mode backtest|live|dashboard|streamlit")

if __name__ == "__main__":
    main()
