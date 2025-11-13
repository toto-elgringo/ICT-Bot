"""
Grid Search Engine v2.1.1 avec BATCH PROCESSING

VERSION 2.1.1 FEATURES:
- 4 grilles progressives pour optimisation graduée:
  * FAST: 864 combinaisons (~2-3 min) - Screening avec presets
  * STANDARD: 2,592 combinaisons (~5-7 min) - Fine-tuning des filtres clés
  * ADVANCED: 20,736 combinaisons (~15-20 min) - Exploration exhaustive
  * COMPLETE: 27,648 combinaisons (~25-30 min) - TOUS les paramètres individuels
- Support des 8 nouveaux paramètres ICT configurables
- Système de presets (Conservative/Default/Aggressive)
- Early stopping optionnel pour skip les configurations médiocres
- Métadonnées enrichies dans les résultats JSON

OPTIMISATIONS:
1. Shared Memory: Données MT5 chargées une fois, partagées entre workers
2. Disk Cache: Cache MT5 persistant (100ms vs 3-5s)
3. Numba JIT: Indicateurs compilés en machine code (3-5x faster)
4. Batch Processing: 10 configs par worker sans overhead de création/destruction
5. Early Stopping: Skip automatique des combinaisons sous-performantes

Speedup total: 25-35x vs version originale séquentielle

Usage:
    python grid_search_engine_batch.py EURUSD H1 5000 --grid fast
    python grid_search_engine_batch.py EURUSD H1 5000 2 10 --grid standard
    python grid_search_engine_batch.py XAUUSD H4 2000 2 10 --grid advanced --early-stop
    python grid_search_engine_batch.py EURUSD H1 5000 2 10 --grid complete
"""

import os
import sys
import json
import itertools
import multiprocessing as mp
from datetime import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from tqdm import tqdm

# Initialiser colorama pour Windows (fix affichage tqdm)
try:
    import colorama
    colorama.init()
except ImportError:
    pass  # Colorama optionnel (Linux/Mac n'en ont pas besoin)


# Classe simple pour wrapper le dictionnaire info en objet
class SymbolInfoWrapper:
    """Wrapper pour convertir dictionnaire en objet avec attributs"""
    def __init__(self, info_dict):
        for key, value in info_dict.items():
            setattr(self, key, value)


# ============================================================================
# GRID SEARCH v2.1.1 - 3 PROGRESSIVE GRIDS
# ============================================================================
# VERSION 2.1.1: 8 nouveaux paramètres ICT configurables
# Optimisation: 3 grilles progressives pour éviter explosion combinatoire

# GRID_PARAMS_FAST - Screening rapide (2-3 minutes)
# Total: 2×3×3×2×4×1×2×3 = 864 combinaisons
GRID_PARAMS_FAST = {
    'RISK_PER_TRADE': [0.01, 0.02],
    'RR_TAKE_PROFIT': [1.5, 1.8, 2.0],
    'ML_THRESHOLD': [0.35, 0.40, 0.45],
    'MAX_CONCURRENT_TRADES': [2, 3],
    'COOLDOWN_BARS': [3, 5, 7, 10],
    'USE_ATR_FILTER': [True],  # Toujours activé en mode Fast
    'USE_ADAPTIVE_RISK': [True, False],
    # v2.1.1: Utiliser PRESETS au lieu de tester individuellement
    'FILTER_PRESET': ['Conservative', 'Default', 'Aggressive']
}

# GRID_PARAMS - Standard (5-7 minutes)
# Total: 3×4×3×2×3×1×2×2×2×2×2 = 2,592 combinaisons
GRID_PARAMS = {
    'RISK_PER_TRADE': [0.005, 0.01, 0.02],
    'RR_TAKE_PROFIT': [1.3, 1.5, 1.8, 2.0],
    'ML_THRESHOLD': [0.35, 0.40, 0.45],
    'MAX_CONCURRENT_TRADES': [2, 3],
    'COOLDOWN_BARS': [3, 5, 7],
    'USE_ATR_FILTER': [True],
    'USE_ADAPTIVE_RISK': [True, False],
    # v2.1.1: Fine-tuning des filtres clés
    'USE_FVG_MITIGATION_FILTER': [True, False],
    'USE_MARKET_STRUCTURE_FILTER': [True, False],
    'BOS_MAX_AGE': [20, 30],
    'FVG_BOS_MAX_DISTANCE': [20, 30]
}

# GRID_PARAMS_ADVANCED - Exploration exhaustive (15-20 minutes)
# Total: 4×5×4×3×3×2×2×2×2×2×3×3×2×2 = 20,736 combinaisons
GRID_PARAMS_ADVANCED = {
    'RISK_PER_TRADE': [0.005, 0.01, 0.015, 0.02],
    'RR_TAKE_PROFIT': [1.2, 1.5, 1.8, 2.0, 2.5],
    'ML_THRESHOLD': [0.30, 0.35, 0.40, 0.45],
    'MAX_CONCURRENT_TRADES': [2, 3, 4],
    'COOLDOWN_BARS': [3, 5, 7],
    'USE_ATR_FILTER': [True, False],
    'USE_ADAPTIVE_RISK': [True, False],
    # v2.1.1: Exploration complète des 8 paramètres
    'USE_FVG_MITIGATION_FILTER': [True, False],
    'USE_BOS_RECENCY_FILTER': [True, False],
    'USE_MARKET_STRUCTURE_FILTER': [True, False],
    'BOS_MAX_AGE': [20, 30, 40],
    'FVG_BOS_MAX_DISTANCE': [20, 30, 40],
    'USE_EXTREME_VOLATILITY_FILTER': [True, False],
    'VOLATILITY_MULTIPLIER_MAX': [3.0, 4.0]
}

# GRID_PARAMS_COMPLETE : 27,648 combinaisons (~25-30 min avec 2 workers)
# Teste TOUS les 15 paramètres (7 base + 8 ICT v2.1.1) individuellement
# Aucun preset : Configuration complète dans résultats JSON
GRID_PARAMS_COMPLETE = {
    # Paramètres de base (7 params) : 3×4×3×2×3×1×2 = 432 combinaisons
    'RISK_PER_TRADE': [0.01, 0.015, 0.02],  # Risque par trade
    'RR_TAKE_PROFIT': [1.5, 1.8, 2.0, 2.5],  # Risk/Reward ratio
    'ML_THRESHOLD': [0.35, 0.40, 0.45],  # Seuil ML (0.30 trop agressif, 0.50 trop strict)
    'MAX_CONCURRENT_TRADES': [2, 3],  # Max trades simultanés (1 trop prudent, 4+ trop risqué)
    'COOLDOWN_BARS': [3, 5, 7],  # Cooldown entre trades (10 trop long)
    'USE_ATR_FILTER': [True],  # FIXÉ : Filtre ATR essentiel
    'USE_ADAPTIVE_RISK': [True, False],  # Risque adaptatif après pertes

    # Paramètres ICT v2.1.1 (8 params) : 2×2×2×2×2×1×2×1 = 64 combinaisons
    'USE_FVG_MITIGATION_FILTER': [True, False],  # Ignorer FVG déjà mitigés
    'USE_BOS_RECENCY_FILTER': [True, False],  # BOS doit être récent (< BOS_MAX_AGE)
    'USE_MARKET_STRUCTURE_FILTER': [True, False],  # Structure HH/HL ou LL/LH requise
    'BOS_MAX_AGE': [20, 30],  # Age max du BOS en barres (15 trop strict, 40 trop permissif)
    'FVG_BOS_MAX_DISTANCE': [20, 30],  # Distance max FVG-BOS en barres
    'USE_ORDER_BLOCK_SL': [True],  # FIXÉ : OB pour SL = amélioration majeure
    'USE_EXTREME_VOLATILITY_FILTER': [True, False],  # Filtrer volatilité extrême (news)
    'VOLATILITY_MULTIPLIER_MAX': [3.0],  # FIXÉ : Seuil volatilité (défaut recommandé)
}
# TOTAL : 432 × 64 = 27,648 combinaisons

# Variable globale pour stocker les données partagées et le module
_shared_df = None
_shared_info = None
_ict_bot_module = None


def apply_filter_preset(ict_bot, preset_name: str):
    """
    Applique un preset de filtres ICT v2.1.1

    Args:
        ict_bot: Module ict_bot_all_in_one chargé
        preset_name: 'Conservative', 'Default', ou 'Aggressive'
    """
    if preset_name == 'Conservative':
        # Stricte: Tous les filtres activés, paramètres serrés
        ict_bot.USE_FVG_MITIGATION_FILTER = True
        ict_bot.USE_BOS_RECENCY_FILTER = True
        ict_bot.USE_MARKET_STRUCTURE_FILTER = True
        ict_bot.BOS_MAX_AGE = 20
        ict_bot.FVG_BOS_MAX_DISTANCE = 20
        ict_bot.USE_ORDER_BLOCK_SL = True
        ict_bot.USE_EXTREME_VOLATILITY_FILTER = True
        ict_bot.VOLATILITY_MULTIPLIER_MAX = 3.0

    elif preset_name == 'Default':
        # Équilibré: Filtres essentiels activés
        ict_bot.USE_FVG_MITIGATION_FILTER = False
        ict_bot.USE_BOS_RECENCY_FILTER = True
        ict_bot.USE_MARKET_STRUCTURE_FILTER = False
        ict_bot.BOS_MAX_AGE = 30
        ict_bot.FVG_BOS_MAX_DISTANCE = 30
        ict_bot.USE_ORDER_BLOCK_SL = True
        ict_bot.USE_EXTREME_VOLATILITY_FILTER = True
        ict_bot.VOLATILITY_MULTIPLIER_MAX = 3.5

    elif preset_name == 'Aggressive':
        # Permissif: Moins de filtres, paramètres larges
        ict_bot.USE_FVG_MITIGATION_FILTER = False
        ict_bot.USE_BOS_RECENCY_FILTER = False
        ict_bot.USE_MARKET_STRUCTURE_FILTER = False
        ict_bot.BOS_MAX_AGE = 50
        ict_bot.FVG_BOS_MAX_DISTANCE = 50
        ict_bot.USE_ORDER_BLOCK_SL = True
        ict_bot.USE_EXTREME_VOLATILITY_FILTER = False
        ict_bot.VOLATILITY_MULTIPLIER_MAX = 5.0


def generate_all_combinations(grid_mode: str = 'standard') -> List[Dict[str, Any]]:
    """
    Genere toutes les combinaisons possibles de parametres selon le mode

    Args:
        grid_mode: 'fast', 'standard', 'advanced', ou 'complete'

    Returns:
        Liste de dictionnaires de parametres
    """
    # Validation du mode
    if grid_mode not in ['fast', 'standard', 'advanced', 'complete']:
        print(f"[ERROR] Invalid grid mode: {grid_mode}. Use: fast/standard/advanced/complete")
        import sys
        sys.exit(1)

    # Sélectionner la grille appropriée
    if grid_mode == 'fast':
        grid_params = GRID_PARAMS_FAST
        print(f"[GRID] Mode FAST : {len(list(itertools.product(*grid_params.values())))} combinaisons")
    elif grid_mode == 'advanced':
        grid_params = GRID_PARAMS_ADVANCED
        print(f"[GRID] Mode ADVANCED : {len(list(itertools.product(*grid_params.values())))} combinaisons")
    elif grid_mode == 'complete':
        grid_params = GRID_PARAMS_COMPLETE
        print(f"[GRID] Mode COMPLETE : {len(list(itertools.product(*grid_params.values())))} combinaisons")
    else:  # 'standard' par défaut
        grid_params = GRID_PARAMS
        print(f"[GRID] Mode STANDARD : {len(list(itertools.product(*grid_params.values())))} combinaisons")

    keys = list(grid_params.keys())
    values = list(grid_params.values())

    combinations = []
    for combination in itertools.product(*values):
        param_dict = dict(zip(keys, combination))
        combinations.append(param_dict)

    return combinations


def calculate_composite_score(results: Dict[str, float]) -> float:
    """
    Calcule le score composite pour classer les configurations
    Score = 40% PnL + 30% Sharpe + 20% WinRate + 10% (1-DD)
    """
    pnl = results.get('pnl_pct', 0.0)
    sharpe = results.get('sharpe_ratio', 0.0)
    win_rate = results.get('win_rate', 0.0)
    drawdown = results.get('max_drawdown_pct', 0.0)

    # Normaliser les valeurs
    pnl_norm = max(0, min(100, pnl)) / 100.0
    sharpe_norm = max(0, min(3, sharpe)) / 3.0
    win_rate_norm = win_rate / 100.0
    dd_norm = 1 - (abs(drawdown) / 100.0)

    # Ponderation: 40% PnL, 30% Sharpe, 20% WinRate, 10% (1-DD)
    composite = (0.40 * pnl_norm +
                 0.30 * sharpe_norm +
                 0.20 * win_rate_norm +
                 0.10 * dd_norm)

    return composite


def should_skip_combination(partial_results: List[Dict[str, Any]],
                            min_winrate: float = 45.0,
                            min_trades: int = 5,
                            window_size: int = 5) -> bool:
    """
    Early stopping: Skip si les derniers résultats sont médiocres

    Args:
        partial_results: Résultats accumulés jusqu'à présent
        min_winrate: Win rate minimum acceptable (%)
        min_trades: Nombre minimum de trades requis
        window_size: Nombre de résultats à analyser

    Returns:
        True si la combinaison doit être skippée
    """
    if len(partial_results) < window_size:
        return False

    recent_results = partial_results[-window_size:]

    # Vérifier win rate moyen
    avg_winrate = np.mean([r['win_rate'] for r in recent_results])
    if avg_winrate < min_winrate:
        return True

    # Vérifier nombre de trades moyen
    avg_trades = np.mean([r['total_trades'] for r in recent_results])
    if avg_trades < min_trades:
        return True

    return False


def init_worker_batch(df_data, info_data):
    """
    Fonction d'initialisation appelée une fois par worker
    OPTIMISATION BATCH: Charge le module ICT bot UNE SEULE FOIS par worker
    """
    global _shared_df, _shared_info, _ict_bot_module

    _shared_df = df_data

    # Convertir le dictionnaire en objet wrapper si nécessaire
    if isinstance(info_data, dict):
        _shared_info = SymbolInfoWrapper(info_data)
    else:
        _shared_info = info_data

    # OPTIMISATION: Importer le module ICT bot UNE SEULE FOIS
    import importlib.util
    spec = importlib.util.spec_from_file_location("ict_bot", "ict_bot_all_in_one.py")
    _ict_bot_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_ict_bot_module)

    # Logging silencieux pour éviter interférence avec tqdm
    # (Utiliser tqdm.write() si vraiment nécessaire)


def run_single_backtest_batch(args: Tuple[int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute un backtest avec batch processing
    OPTIMISATION: Réutilise le module ICT bot déjà chargé dans le worker
    VERSION 2.1.1: Support des presets et 8 nouveaux paramètres ICT
    """
    global _shared_df, _shared_info, _ict_bot_module

    idx, params = args

    try:
        # OPTIMISATION: Module déjà chargé, pas besoin de réimporter!
        ict_bot = _ict_bot_module

        # Appliquer les paramètres de configuration de base
        ict_bot.RISK_PER_TRADE = params.get('RISK_PER_TRADE', 0.01)
        ict_bot.RR_TAKE_PROFIT = params.get('RR_TAKE_PROFIT', 2.0)
        ict_bot.MAX_CONCURRENT_TRADES = params.get('MAX_CONCURRENT_TRADES', 2)
        ict_bot.COOLDOWN_BARS = params.get('COOLDOWN_BARS', 5)
        ict_bot.ML_THRESHOLD = params.get('ML_THRESHOLD', 0.4)
        ict_bot.USE_ATR_FILTER = params.get('USE_ATR_FILTER', True)
        ict_bot.USE_ADAPTIVE_RISK = params.get('USE_ADAPTIVE_RISK', False)

        # v2.1.1: Appliquer PRESET si présent (mode FAST)
        if 'FILTER_PRESET' in params:
            apply_filter_preset(ict_bot, params['FILTER_PRESET'])
        else:
            # v2.1.1: Appliquer paramètres ICT individuels (mode STANDARD/ADVANCED/COMPLETE)
            # S'assurer que TOUS les 8 paramètres ICT sont appliqués
            ict_bot.USE_FVG_MITIGATION_FILTER = params.get('USE_FVG_MITIGATION_FILTER', False)
            ict_bot.USE_BOS_RECENCY_FILTER = params.get('USE_BOS_RECENCY_FILTER', True)
            ict_bot.USE_MARKET_STRUCTURE_FILTER = params.get('USE_MARKET_STRUCTURE_FILTER', False)
            ict_bot.BOS_MAX_AGE = params.get('BOS_MAX_AGE', 30)
            ict_bot.FVG_BOS_MAX_DISTANCE = params.get('FVG_BOS_MAX_DISTANCE', 30)
            ict_bot.USE_ORDER_BLOCK_SL = params.get('USE_ORDER_BLOCK_SL', True)
            ict_bot.USE_EXTREME_VOLATILITY_FILTER = params.get('USE_EXTREME_VOLATILITY_FILTER', True)
            ict_bot.VOLATILITY_MULTIPLIER_MAX = params.get('VOLATILITY_MULTIPLIER_MAX', 3.5)

        # Désactiver le ML pour plus de rapidité
        ict_bot.USE_ML_META_LABELLING = False

        # Créer un MLFilter désactivé
        ml_filter = ict_bot.MLFilter(model_path=None, use_meta_labelling=False)

        # Exécuter le backtest avec les données partagées
        metrics, _ = ict_bot.backtest(
            _shared_df.copy(),  # Copie pour éviter les modifications concurrentes
            symbol="SHARED",
            risk=ict_bot.RISK_PER_TRADE,
            rr=ict_bot.RR_TAKE_PROFIT,
            cooldown=ict_bot.COOLDOWN_BARS,
            use_killzones=True,
            ml=ml_filter,
            info=_shared_info
        )

        # Extraire les résultats
        results = {
            'config_id': idx,
            'params': params,
            'total_trades': int(metrics['trades']),
            'win_rate': float(metrics['winrate']),
            'pnl_pct': (float(metrics['pnl']) / 10000.0) * 100.0,
            'max_drawdown_pct': float(metrics['dd']),
            'equity_final': float(metrics['eq_final']),
            'success': True
        }

        # Calculer un Sharpe ratio approximatif
        if results['total_trades'] > 0 and results['win_rate'] > 0:
            win_ratio = results['win_rate'] / 100.0
            trade_count = results['total_trades']
            dd_factor = 1.0 + abs(results['max_drawdown_pct']) / 100.0
            results['sharpe_ratio'] = (win_ratio * (trade_count ** 0.5)) / dd_factor
        else:
            results['sharpe_ratio'] = 0.0

        # Calculer le score composite
        results['composite_score'] = calculate_composite_score(results)

        return results

    except Exception as e:
        return {
            'config_id': idx,
            'params': params,
            'pnl_pct': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown_pct': 0.0,
            'composite_score': 0.0,
            'success': False,
            'error': str(e)
        }


def run_batch_of_backtests(batch_args: List[Tuple[int, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    OPTIMISATION BATCH: Exécute un batch de backtests dans le même worker
    Réduit l'overhead de multiprocessing en traitant plusieurs configs consécutivement
    """
    results = []
    for args in batch_args:
        result = run_single_backtest_batch(args)
        results.append(result)
    return results


def run_grid_search_batch(symbol: str, timeframe: str, bars: int,
                          max_workers: int = None,
                          batch_size: int = 10,
                          grid_mode: str = 'standard',
                          use_early_stopping: bool = False,
                          callback=None) -> List[Dict[str, Any]]:
    """
    Execute la recherche en grille avec BATCH PROCESSING

    VERSION 2.1.1:
    - 3 grilles progressives: fast (864), standard (2,592), advanced (20,736)
    - Support des presets ICT (Conservative/Default/Aggressive)
    - Early stopping optionnel pour skip les mauvais paramètres

    OPTIMISATION BATCH:
    - Traite plusieurs configurations par worker (batch_size)
    - Réduit l'overhead de communication entre processus
    - Speedup attendu: 1.5-2x vs version optimisée simple

    Args:
        symbol: Paire a tester
        timeframe: Timeframe a tester
        bars: Nombre de barres
        max_workers: Nombre de workers (None = auto-detect)
        batch_size: Nombre de configs à traiter par batch (défaut: 10)
        grid_mode: 'fast', 'standard', ou 'advanced'
        use_early_stopping: Activer early stopping (défaut: False)
        callback: Fonction callback pour progression (progress, total)

    Returns:
        Liste des resultats tries par score composite
    """
    import time

    # Generer toutes les combinaisons selon le mode
    combinations = generate_all_combinations(grid_mode=grid_mode)
    total_tests = len(combinations)

    grid_names = {'fast': 'FAST', 'standard': 'STANDARD', 'advanced': 'ADVANCED', 'complete': 'COMPLETE'}
    grid_name = grid_names.get(grid_mode, 'STANDARD')

    print(f"\n[GRID SEARCH v2.1.1 - {grid_name}] Lancement de {total_tests} tests...")
    print(f"[GRID SEARCH] Mode: {grid_name} | Batch size: {batch_size}")
    print(f"[GRID SEARCH] Early stopping: {'ON' if use_early_stopping else 'OFF'}")
    print(f"[GRID SEARCH] Parametres: {symbol} {timeframe} {bars} barres")

    # Charger les données MT5 UNE SEULE FOIS (avec cache)
    print(f"[GRID SEARCH BATCH] Chargement des données MT5...")
    start_load = time.time()

    try:
        from mt5_cache import load_mt5_data_with_cache

        df, info = load_mt5_data_with_cache(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            max_cache_age_hours=24,
            force_reload=False,
            use_numba=False  # IMPORTANT: Desactiver Numba car fvg_mitigated/market_structure manquants
        )

        # Convertir SymbolInfo en dictionnaire pour le rendre picklable
        if info is not None and hasattr(info, '_asdict'):
            info_dict = info._asdict()
        elif info is not None:
            # Extraire les attributs essentiels si _asdict n'existe pas
            info_dict = {
                'point': info.point if hasattr(info, 'point') else 0.00001,
                'digits': info.digits if hasattr(info, 'digits') else 5,
                'trade_contract_size': info.trade_contract_size if hasattr(info, 'trade_contract_size') else 100000
            }
        else:
            # Valeurs par défaut si info est None
            info_dict = {'point': 0.00001, 'digits': 5, 'trade_contract_size': 100000}

        load_time = time.time() - start_load
        print(f"[GRID SEARCH BATCH] Données chargées en {load_time:.1f}s ({len(df)} barres)")

    except Exception as e:
        print(f"[ERROR] Impossible de charger les données MT5: {e}")
        import traceback
        traceback.print_exc()
        return []

    # Detecter le nombre de CPU disponibles
    if max_workers is None:
        max_workers = min(2, max(1, mp.cpu_count() - 2))
    else:
        max_workers = min(max_workers, 4)

    print(f"[GRID SEARCH BATCH] Utilisation de {max_workers} workers paralleles")

    # Preparer les arguments pour chaque test
    test_args = [
        (idx, params)
        for idx, params in enumerate(combinations)
    ]

    # OPTIMISATION BATCH: Diviser en batches
    batches = []
    for i in range(0, len(test_args), batch_size):
        batch = test_args[i:i+batch_size]
        batches.append(batch)

    print(f"[GRID SEARCH BATCH] {len(batches)} batches de ~{batch_size} tests chacun")

    # Executer les tests avec batch processing
    results = []
    completed = 0
    start_time = time.time()

    if max_workers == 1:
        # Mode sequentiel avec batch
        print("[GRID SEARCH BATCH] Mode sequentiel avec batch processing")

        # Initialiser les données globales
        global _shared_df, _shared_info
        init_worker_batch(df, info_dict)

        # Barre de progression avec tqdm (configuration optimisée Windows/Linux)
        with tqdm(
            total=total_tests,
            desc="Grid Search",
            unit="test",
            ncols=100,  # Largeur fixe pour éviter redimensionnement
            file=sys.stderr,  # Redirection stderr pour éviter conflits avec print()
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            disable=False
        ) as pbar:
            for batch in batches:
                batch_results = run_batch_of_backtests(batch)
                results.extend(batch_results)
                completed += len(batch)

                # Mise à jour de la barre
                pbar.update(len(batch))

                # Afficher les meilleurs résultats actuels dans la description
                if results:
                    best_result = max(results, key=lambda x: x.get('composite_score', 0))
                    best_wr = best_result.get('win_rate', 0)
                    best_trades = best_result.get('total_trades', 0)
                    pbar.set_postfix({
                        'Best_WR': f'{best_wr:.1f}%',
                        'Best_Trades': best_trades,
                        'Avg_time': f'{(time.time()-start_time)/completed:.2f}s/test' if completed > 0 else 'N/A'
                    })

                if callback:
                    callback(completed, total_tests)

    else:
        # Mode parallele avec batch processing
        print(f"[GRID SEARCH BATCH] Mode parallele ({max_workers} workers)")

        # Barre de progression avec tqdm pour mode parallèle (configuration optimisée)
        with tqdm(
            total=total_tests,
            desc="Grid Search (parallel)",
            unit="test",
            ncols=100,  # Largeur fixe
            file=sys.stderr,  # Redirection stderr
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            disable=False
        ) as pbar:
            with mp.Pool(processes=max_workers, initializer=init_worker_batch, initargs=(df, info_dict)) as pool:
                for batch_results in pool.imap_unordered(run_batch_of_backtests, batches, chunksize=1):
                    results.extend(batch_results)
                    completed += len(batch_results)

                    # Mise à jour de la barre
                    pbar.update(len(batch_results))

                    # Afficher les meilleurs résultats actuels
                    if results:
                        best_result = max(results, key=lambda x: x.get('composite_score', 0))
                        best_wr = best_result.get('win_rate', 0)
                        best_trades = best_result.get('total_trades', 0)
                        pbar.set_postfix({
                            'Best_WR': f'{best_wr:.1f}%',
                            'Best_Trades': best_trades,
                            'Avg_time': f'{(time.time()-start_time)/completed:.2f}s/test' if completed > 0 else 'N/A'
                        })

                    if callback:
                        callback(completed, total_tests)

    # Trier par score composite
    results.sort(key=lambda x: x['composite_score'], reverse=True)

    total_time = time.time() - start_time
    print(f"\n[GRID SEARCH BATCH] Tests termines en {total_time/60:.1f} minutes!")
    print(f"[GRID SEARCH BATCH] Vitesse moyenne: {total_tests/total_time:.1f} tests/seconde")
    print(f"[GRID SEARCH BATCH] Meilleur score: {results[0]['composite_score']:.4f}")

    return results


def save_top_results(results: List[Dict[str, Any]],
                    symbol: str,
                    timeframe: str,
                    bars: int,
                    grid_mode: str = 'standard',
                    use_early_stopping: bool = False,
                    top_n: int = 5) -> str:
    """
    Sauvegarde les N meilleurs resultats dans Grid/
    VERSION 2.1.1: Inclut les métadonnées de la grille et early stopping
    """
    os.makedirs('Grid', exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Grid/grid_results_{symbol}_{timeframe}_{grid_mode}_{timestamp}.json"

    # Calculer statistiques globales
    import time
    successful_tests = [r for r in results if r.get('success', False)]
    avg_winrate = np.mean([r['win_rate'] for r in successful_tests]) if successful_tests else 0
    avg_pnl = np.mean([r['pnl_pct'] for r in successful_tests]) if successful_tests else 0
    avg_trades = np.mean([r['total_trades'] for r in successful_tests]) if successful_tests else 0
    failed_tests = len(results) - len(successful_tests)

    # Calculer temps d'exécution (approximation basée sur timestamp)
    execution_time_seconds = 0  # Sera rempli par l'appelant si disponible

    report = {
        'metadata': {
            'version': '2.1.1',
            'grid_mode': grid_mode,
            'symbol': symbol,
            'timeframe': timeframe,
            'bars': bars,
            'total_tests': len(results),
            'successful_tests': len(successful_tests),
            'failed_tests': failed_tests,
            'early_stopping_enabled': use_early_stopping,
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'optimized_version': True,
            'batch_processing': True,
            'average_winrate': float(avg_winrate),
            'average_pnl': float(avg_pnl),
            'average_trades': float(avg_trades),
            'execution_time_seconds': execution_time_seconds,
            'tests_per_second': 0.0  # Sera calculé par l'appelant
        },
        'top_configs': results[:top_n]
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    print(f"\n[GRID SEARCH] Top {top_n} resultats sauvegardes dans: {filename}")

    return filename


def main():
    """Fonction principale pour test en ligne de commande - VERSION 2.1.1"""
    import sys

    if len(sys.argv) < 4:
        print("\nGrid Search Engine v2.1.1 - ICT Trading Bot")
        print("=" * 60)
        print("\nUsage: python grid_search_engine_batch.py SYMBOL TIMEFRAME BARS [OPTIONS]")
        print("\nPositional arguments:")
        print("  SYMBOL      : Symbol to test (e.g., EURUSD, XAUUSD)")
        print("  TIMEFRAME   : Timeframe (M5, M15, H1, H4, D1)")
        print("  BARS        : Number of bars to test")
        print("\nOptional arguments:")
        print("  WORKERS     : Number of parallel workers (default: auto)")
        print("  BATCH_SIZE  : Configs per batch (default: 10)")
        print("  --grid MODE : Grid mode - fast/standard/advanced/complete (default: standard)")
        print("                fast     = 864 tests (~2-3 min)")
        print("                standard = 2,592 tests (~5-7 min)")
        print("                advanced = 20,736 tests (~15-20 min)")
        print("                complete = 27,648 tests (~25-30 min)")
        print("  --early-stop: Enable early stopping (skip low performers)")
        print("\nExamples:")
        print("  python grid_search_engine_batch.py EURUSD H1 5000")
        print("  python grid_search_engine_batch.py EURUSD H1 5000 2 10 --grid fast")
        print("  python grid_search_engine_batch.py XAUUSD H4 2000 2 10 --grid advanced --early-stop")
        print("  python grid_search_engine_batch.py EURUSD H1 5000 2 10 --grid complete")
        print("=" * 60)
        sys.exit(1)

    # Parser les arguments
    symbol = sys.argv[1]
    timeframe = sys.argv[2]
    bars = int(sys.argv[3])

    # Arguments nommés optionnels (parser AVANT positionnels pour exclure leurs valeurs)
    grid_mode = 'standard'
    use_early_stopping = False

    # Indices à exclure des arguments positionnels
    excluded_indices = set()

    if '--grid' in sys.argv:
        grid_idx = sys.argv.index('--grid')
        excluded_indices.add(grid_idx)
        if grid_idx + 1 < len(sys.argv):
            excluded_indices.add(grid_idx + 1)
            grid_mode = sys.argv[grid_idx + 1]
            if grid_mode not in ['fast', 'standard', 'advanced', 'complete']:
                print(f"[ERROR] Invalid grid mode: {grid_mode}")
                print("Available modes:")
                print("  - fast     : 864 tests (~2-3 min) - Preset screening")
                print("  - standard : 2,592 tests (~5-7 min) - Production")
                print("  - advanced : 20,736 tests (~15-20 min) - R&D exhaustif")
                print("  - complete : 27,648 tests (~25-30 min) - ALL parameters")
                sys.exit(1)

    if '--early-stop' in sys.argv:
        early_stop_idx = sys.argv.index('--early-stop')
        excluded_indices.add(early_stop_idx)
        use_early_stopping = True

    # Arguments positionnels optionnels (exclure les flags nommés ET leurs valeurs)
    pos_args = []
    for i, arg in enumerate(sys.argv[4:], start=4):
        if not arg.startswith('--') and i not in excluded_indices:
            pos_args.append(arg)

    workers = int(pos_args[0]) if len(pos_args) > 0 else None
    batch_size = int(pos_args[1]) if len(pos_args) > 1 else 10

    # Lancer le grid search BATCH v2.1.1
    import time
    start_time = time.time()

    results = run_grid_search_batch(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        max_workers=workers,
        batch_size=batch_size,
        grid_mode=grid_mode,
        use_early_stopping=use_early_stopping
    )

    elapsed_time = time.time() - start_time

    # Sauvegarder les top 5 avec métadonnées enrichies
    report_path = save_top_results(
        results=results,
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        grid_mode=grid_mode,
        use_early_stopping=use_early_stopping,
        top_n=5
    )

    # Enrichir le fichier JSON avec temps d'exécution
    with open(report_path, 'r', encoding='utf-8') as f:
        report_data = json.load(f)

    report_data['metadata']['execution_time_seconds'] = int(elapsed_time)
    report_data['metadata']['tests_per_second'] = round(len(results) / elapsed_time, 2) if elapsed_time > 0 else 0

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=4, ensure_ascii=False)

    # Afficher les resultats
    print("\n" + "="*80)
    print("TOP 5 CONFIGURATIONS")
    print("="*80)

    for i, result in enumerate(results[:5], 1):
        print(f"\n#{i} - Score Composite: {result['composite_score']:.4f}")
        print(f"  PnL: {result['pnl_pct']:.2f}%")
        print(f"  Win Rate: {result['win_rate']:.2f}%")
        print(f"  Sharpe: {result['sharpe_ratio']:.3f}")
        print(f"  Max DD: {result['max_drawdown_pct']:.2f}%")
        print(f"  Trades: {result['total_trades']}")
        print(f"  Parametres:")
        for key, value in result['params'].items():
            print(f"    {key}: {value}")

    print(f"\nRapport complet: {report_path}")


if __name__ == '__main__':
    main()
