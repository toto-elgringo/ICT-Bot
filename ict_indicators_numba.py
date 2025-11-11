"""
Indicateurs ICT optimisés avec Numba JIT
Speedup attendu: 3-5x sur les calculs d'indicateurs
"""

import numpy as np
import pandas as pd
from numba import jit, prange


@jit(nopython=True, cache=True, fastmath=True)
def calculate_atr_numba(highs, lows, closes, period=14):
    """
    Calcule l'ATR (Average True Range) avec Numba JIT

    Args:
        highs: Numpy array des highs
        lows: Numpy array des lows
        closes: Numpy array des closes
        period: Période ATR (défaut: 14)

    Returns:
        Numpy array des valeurs ATR
    """
    n = len(highs)
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

    return atr


@jit(nopython=True, cache=True, parallel=True)
def swing_points_numba(highs, lows, left=2, right=2):
    """
    Détecte les swing high/low (fractals) avec Numba JIT

    Args:
        highs: Numpy array des highs
        lows: Numpy array des lows
        left: Nombre de barres à gauche (défaut: 2)
        right: Nombre de barres à droite (défaut: 2)

    Returns:
        Tuple (swing_high, swing_low) - boolean arrays
    """
    n = len(highs)
    swing_high = np.zeros(n, dtype=np.bool_)
    swing_low = np.zeros(n, dtype=np.bool_)

    for i in prange(left, n-right):
        # Swing High
        is_swing_high = True
        count_equal = 0
        for j in range(i-left, i+right+1):
            if highs[j] > highs[i]:
                is_swing_high = False
                break
            if highs[j] == highs[i]:
                count_equal += 1

        if is_swing_high and count_equal == 1:
            swing_high[i] = True

        # Swing Low
        is_swing_low = True
        count_equal = 0
        for j in range(i-left, i+right+1):
            if lows[j] < lows[i]:
                is_swing_low = False
                break
            if lows[j] == lows[i]:
                count_equal += 1

        if is_swing_low and count_equal == 1:
            swing_low[i] = True

    return swing_high, swing_low


@jit(nopython=True, cache=True)
def detect_bos_numba(swing_high, swing_low, highs, lows, closes):
    """
    Détecte les Break of Structure (BOS) avec Numba JIT

    Args:
        swing_high: Boolean array des swing highs
        swing_low: Boolean array des swing lows
        highs: Numpy array des highs
        lows: Numpy array des lows
        closes: Numpy array des closes

    Returns:
        Tuple (bos_up, bos_down) - boolean arrays
    """
    n = len(swing_high)
    bos_up = np.zeros(n, dtype=np.bool_)
    bos_down = np.zeros(n, dtype=np.bool_)
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
            bos_down[i] = True

    return bos_up, bos_down


@jit(nopython=True, cache=True, parallel=True)
def detect_fvg_numba(highs, lows):
    """
    Détecte les Fair Value Gaps (FVG) avec Numba JIT

    Args:
        highs: Numpy array des highs
        lows: Numpy array des lows

    Returns:
        Tuple (bull_fvg_top, bull_fvg_bot, bear_fvg_top, bear_fvg_bot, fvg_side_code)
        fvg_side_code: 0=none, 1=bull, 2=bear
    """
    n = len(highs)
    bull_fvg_top = np.full(n, np.nan)
    bull_fvg_bot = np.full(n, np.nan)
    bear_fvg_top = np.full(n, np.nan)
    bear_fvg_bot = np.full(n, np.nan)
    fvg_side_code = np.zeros(n, dtype=np.int8)  # 0=none, 1=bull, 2=bear

    for i in prange(2, n):
        # Bullish FVG: lows[i] > highs[i-2]
        if lows[i] > highs[i-2]:
            bull_fvg_bot[i] = highs[i-2]
            bull_fvg_top[i] = lows[i]
            fvg_side_code[i] = 1

        # Bearish FVG: highs[i] < lows[i-2]
        elif highs[i] < lows[i-2]:
            bear_fvg_top[i] = lows[i-2]
            bear_fvg_bot[i] = highs[i]
            fvg_side_code[i] = 2

    return bull_fvg_top, bull_fvg_bot, bear_fvg_top, bear_fvg_bot, fvg_side_code


@jit(nopython=True, cache=True)
def detect_order_block_numba(bos_up, bos_down, opens, closes, highs, lows, lookback=10):
    """
    Détecte les Order Blocks (OB) avec Numba JIT

    Args:
        bos_up: Boolean array des BOS up
        bos_down: Boolean array des BOS down
        opens: Numpy array des opens
        closes: Numpy array des closes
        highs: Numpy array des highs
        lows: Numpy array des lows
        lookback: Nombre de barres à regarder en arrière (défaut: 10)

    Returns:
        Tuple (ob_low, ob_high, ob_side_code)
        ob_side_code: 0=none, 1=bull, 2=bear
    """
    n = len(bos_up)
    ob_low = np.full(n, np.nan)
    ob_high = np.full(n, np.nan)
    ob_side_code = np.zeros(n, dtype=np.int8)  # 0=none, 1=bull, 2=bear

    for i in range(n):
        if bos_up[i]:
            # Chercher le dernier down candle (bearish)
            start = max(0, i - lookback)
            last_down_idx = -1
            for j in range(i-1, start-1, -1):
                if closes[j] < opens[j]:
                    last_down_idx = j
                    break

            if last_down_idx >= 0:
                ob_low[i] = lows[last_down_idx]
                ob_high[i] = opens[last_down_idx]
                ob_side_code[i] = 1  # bull

        elif bos_down[i]:
            # Chercher le dernier up candle (bullish)
            start = max(0, i - lookback)
            last_up_idx = -1
            for j in range(i-1, start-1, -1):
                if closes[j] > opens[j]:
                    last_up_idx = j
                    break

            if last_up_idx >= 0:
                ob_low[i] = opens[last_up_idx]
                ob_high[i] = highs[last_up_idx]
                ob_side_code[i] = 2  # bear

    return ob_low, ob_high, ob_side_code


# Fonctions wrapper pour compatibilité DataFrame
def calculate_atr(df: pd.DataFrame, period=14):
    """Wrapper pour calculate_atr_numba avec DataFrame"""
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values

    df['atr'] = calculate_atr_numba(highs, lows, closes, period)
    return df


def swing_points(df: pd.DataFrame, left=2, right=2):
    """Wrapper pour swing_points_numba avec DataFrame"""
    highs = df['high'].values
    lows = df['low'].values

    swing_high, swing_low = swing_points_numba(highs, lows, left, right)

    df['swing_high'] = swing_high
    df['swing_low'] = swing_low
    return df


def detect_bos(df: pd.DataFrame):
    """Wrapper pour detect_bos_numba avec DataFrame"""
    swing_high = df['swing_high'].values
    swing_low = df['swing_low'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values

    bos_up, bos_down = detect_bos_numba(swing_high, swing_low, highs, lows, closes)

    df['bos_up'] = bos_up
    df['bos_down'] = bos_down
    return df


def detect_fvg(df: pd.DataFrame):
    """Wrapper pour detect_fvg_numba avec DataFrame"""
    highs = df['high'].values
    lows = df['low'].values

    bull_fvg_top, bull_fvg_bot, bear_fvg_top, bear_fvg_bot, fvg_side_code = detect_fvg_numba(highs, lows)

    # Convertir les codes en labels
    fvg_side = np.array(['none'] * len(df), dtype=object)
    fvg_side[fvg_side_code == 1] = 'bull'
    fvg_side[fvg_side_code == 2] = 'bear'

    df['fvg_side'] = fvg_side
    df['fvg_bull_top'] = bull_fvg_top
    df['fvg_bull_bot'] = bull_fvg_bot
    df['fvg_bear_top'] = bear_fvg_top
    df['fvg_bear_bot'] = bear_fvg_bot
    return df


def detect_order_block(df: pd.DataFrame, lookback=10):
    """Wrapper pour detect_order_block_numba avec DataFrame"""
    bos_up = df['bos_up'].values
    bos_down = df['bos_down'].values
    opens = df['open'].values
    closes = df['close'].values
    highs = df['high'].values
    lows = df['low'].values

    ob_low, ob_high, ob_side_code = detect_order_block_numba(
        bos_up, bos_down, opens, closes, highs, lows, lookback
    )

    # Convertir les codes en labels
    ob_side = np.array(['none'] * len(df), dtype=object)
    ob_side[ob_side_code == 1] = 'bull'
    ob_side[ob_side_code == 2] = 'bear'

    df['ob_side'] = ob_side
    df['ob_low'] = ob_low
    df['ob_high'] = ob_high
    return df


def enrich_numba(df: pd.DataFrame):
    """
    Enrichit le DataFrame avec tous les indicateurs ICT (version Numba optimisée)
    Speedup attendu: 3-5x vs version non-optimisée
    """
    df = swing_points(df, left=2, right=2)
    df = detect_bos(df)
    df = detect_fvg(df)
    df = detect_order_block(df, lookback=10)
    df = calculate_atr(df, period=14)
    return df


# Test de performance
if __name__ == '__main__':
    import time

    print("Test de Performance: Indicateurs ICT Numba vs Standard")
    print("=" * 80)

    # Créer des données de test
    n = 10000
    np.random.seed(42)

    # Générer des données réalistes OHLC
    closes = np.cumsum(np.random.randn(n) * 0.01) + 100
    opens = closes + np.random.randn(n) * 0.02
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 0.05)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 0.05)

    df = pd.DataFrame({
        'time': pd.date_range('2024-01-01', periods=n, freq='1H'),
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'tick_volume': np.random.randint(100, 1000, n),
        'spread': np.random.randint(1, 10, n),
        'real_volume': np.random.randint(1000, 10000, n)
    })

    # Test version Numba
    print(f"\nTest version NUMBA sur {n} barres:")
    df_numba = df.copy()
    start = time.time()
    df_numba = enrich_numba(df_numba)
    elapsed_numba = time.time() - start
    print(f"✅ Temps: {elapsed_numba:.3f}s")

    # Test version standard (si disponible)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("ict_bot", "ict_bot_all_in_one.py")
        ict_bot = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ict_bot)

        print(f"\nTest version STANDARD sur {n} barres:")
        df_standard = df.copy()
        start = time.time()
        df_standard = ict_bot.enrich(df_standard)
        elapsed_standard = time.time() - start
        print(f"✅ Temps: {elapsed_standard:.3f}s")

        # Comparaison
        speedup = elapsed_standard / elapsed_numba
        print(f"\n🚀 SPEEDUP: {speedup:.2f}x plus rapide avec Numba!")
        print(f"⏱️  Temps gagné: {(elapsed_standard - elapsed_numba)*1000:.0f}ms par enrichissement")

        # Extrapolation pour Grid Search (1728 tests)
        print(f"\n📊 Extrapolation pour Grid Search (1,728 tests):")
        print(f"  Version STANDARD: {elapsed_standard * 1728 / 60:.1f} minutes")
        print(f"  Version NUMBA:    {elapsed_numba * 1728 / 60:.1f} minutes")
        print(f"  Temps gagné:      {(elapsed_standard - elapsed_numba) * 1728 / 60:.1f} minutes")

    except Exception as e:
        print(f"\n⚠️ Version standard non disponible pour comparaison: {e}")

    print("\n" + "=" * 80)
    print("Indicateurs calculés avec succès:")
    print(f"  - Swing Points: {df_numba['swing_high'].sum()} highs, {df_numba['swing_low'].sum()} lows")
    print(f"  - BOS: {df_numba['bos_up'].sum()} up, {df_numba['bos_down'].sum()} down")
    print(f"  - FVG: {np.sum(df_numba['fvg_side'] == 'bull')} bull, {np.sum(df_numba['fvg_side'] == 'bear')} bear")
    print(f"  - OB: {np.sum(df_numba['ob_side'] == 'bull')} bull, {np.sum(df_numba['ob_side'] == 'bear')} bear")
    print(f"  - ATR moyen: {df_numba['atr'].mean():.5f}")
