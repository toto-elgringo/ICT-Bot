"""
Grid Search Engine avec BATCH PROCESSING
Optimisation: Traite plusieurs configurations par worker sans overhead de création/destruction
Speedup attendu: 1.5-2x vs version optimisée simple
"""

import os
import json
import itertools
import multiprocessing as mp
from datetime import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np


# Classe simple pour wrapper le dictionnaire info en objet
class SymbolInfoWrapper:
    """Wrapper pour convertir dictionnaire en objet avec attributs"""
    def __init__(self, info_dict):
        for key, value in info_dict.items():
            setattr(self, key, value)


# Parametres a tester - VERSION 2.0 avec nouveaux filtres ICT
# Total: 3×4×3×3×4×2×2 = 1,728 combinaisons (nouveaux filtres ICT fixés à True)
GRID_PARAMS = {
    'RISK_PER_TRADE': [0.005, 0.01, 0.02],
    'RR_TAKE_PROFIT': [1.5, 1.8, 2.0, 2.5],
    'MAX_CONCURRENT_TRADES': [1, 2, 3],
    'COOLDOWN_BARS': [3, 5, 8],
    'ML_THRESHOLD': [0.3, 0.4, 0.5, 0.6],
    'USE_ATR_FILTER': [True, False],
    'USE_CIRCUIT_BREAKER': [True, False]
}

# Nouveaux filtres ICT v2.0 - TOUJOURS ACTIVÉS (valeurs recommandées)
# Créer une variable séparée pour tests avancés si besoin
GRID_PARAMS_ADVANCED = {
    **GRID_PARAMS,
    'USE_FVG_MITIGATION_FILTER': [True, False],
    'USE_MARKET_STRUCTURE_FILTER': [True, False],
    'USE_ORDER_BLOCK_SL': [True, False]
    # Total: 1,728 × 2 × 2 × 2 = 13,824 combinaisons (optionnel, utiliser avec --advanced)
}

# Variable globale pour stocker les données partagées et le module
_shared_df = None
_shared_info = None
_ict_bot_module = None


def generate_all_combinations() -> List[Dict[str, Any]]:
    """
    Genere toutes les combinaisons possibles de parametres
    Returns: Liste de dictionnaires de parametres
    """
    keys = list(GRID_PARAMS.keys())
    values = list(GRID_PARAMS.values())

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

    print(f"[WORKER {mp.current_process().name}] Initialisé avec données partagées")


def run_single_backtest_batch(args: Tuple[int, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute un backtest avec batch processing
    OPTIMISATION: Réutilise le module ICT bot déjà chargé dans le worker
    """
    global _shared_df, _shared_info, _ict_bot_module

    idx, params = args

    try:
        # OPTIMISATION: Module déjà chargé, pas besoin de réimporter!
        ict_bot = _ict_bot_module

        # Appliquer les paramètres de configuration
        ict_bot.RISK_PER_TRADE = params.get('RISK_PER_TRADE', 0.01)
        ict_bot.RR_TAKE_PROFIT = params.get('RR_TAKE_PROFIT', 2.0)
        ict_bot.MAX_CONCURRENT_TRADES = params.get('MAX_CONCURRENT_TRADES', 1)
        ict_bot.COOLDOWN_BARS = params.get('COOLDOWN_BARS', 5)
        ict_bot.ML_THRESHOLD = params.get('ML_THRESHOLD', 0.5)
        ict_bot.USE_ATR_FILTER = params.get('USE_ATR_FILTER', False)
        ict_bot.USE_CIRCUIT_BREAKER = params.get('USE_CIRCUIT_BREAKER', False)

        # NOUVEAUX : Appliquer les paramètres ICT v2.0
        ict_bot.USE_FVG_MITIGATION_FILTER = params.get('USE_FVG_MITIGATION_FILTER', True)
        ict_bot.USE_BOS_RECENCY_FILTER = True  # Toujours activé (pas dans grid search)
        ict_bot.USE_MARKET_STRUCTURE_FILTER = params.get('USE_MARKET_STRUCTURE_FILTER', True)
        ict_bot.BOS_MAX_AGE = 20  # Valeur fixe recommandée
        ict_bot.FVG_BOS_MAX_DISTANCE = 20  # Valeur fixe recommandée
        ict_bot.USE_ORDER_BLOCK_SL = params.get('USE_ORDER_BLOCK_SL', True)

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
                          callback=None) -> List[Dict[str, Any]]:
    """
    Execute la recherche en grille avec BATCH PROCESSING

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
        callback: Fonction callback pour progression (progress, total)

    Returns:
        Liste des resultats tries par score composite
    """
    import time

    # Generer toutes les combinaisons
    combinations = generate_all_combinations()
    total_tests = len(combinations)

    print(f"\n[GRID SEARCH BATCH] Lancement de {total_tests} tests...")
    print(f"[GRID SEARCH BATCH] Batch size: {batch_size} configs par worker")
    print(f"[GRID SEARCH BATCH] Parametres: {symbol} {timeframe} {bars} barres")

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
            use_numba=True  # Utiliser Numba si disponible
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
        print("[GRID SEARCH BATCH] Mode séquentiel avec batch processing")

        # Initialiser les données globales
        global _shared_df, _shared_info
        init_worker_batch(df, info_dict)

        for batch in batches:
            batch_results = run_batch_of_backtests(batch)
            results.extend(batch_results)
            completed += len(batch)

            if callback:
                callback(completed, total_tests)

            if completed % 50 == 0 or completed == total_tests:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                remaining = (total_tests - completed) / rate if rate > 0 else 0
                print(f"[GRID SEARCH BATCH] Progression: {completed}/{total_tests} "
                      f"({rate:.1f} tests/s, reste ~{remaining/60:.1f} min)")

    else:
        # Mode parallele avec batch processing
        print(f"[GRID SEARCH BATCH] Mode parallèle ({max_workers} workers)")

        with mp.Pool(processes=max_workers, initializer=init_worker_batch, initargs=(df, info_dict)) as pool:
            for batch_results in pool.imap_unordered(run_batch_of_backtests, batches, chunksize=1):
                results.extend(batch_results)
                completed += len(batch_results)

                if callback:
                    callback(completed, total_tests)

                if completed % 50 == 0 or completed == total_tests:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (total_tests - completed) / rate if rate > 0 else 0
                    print(f"[GRID SEARCH BATCH] Progression: {completed}/{total_tests} "
                          f"({rate:.1f} tests/s, reste ~{remaining/60:.1f} min)")

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
                    top_n: int = 5) -> str:
    """
    Sauvegarde les N meilleurs resultats dans Grid/
    """
    os.makedirs('Grid', exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Grid/grid_results_{symbol}_{timeframe}_{timestamp}_batch.json"

    report = {
        'metadata': {
            'symbol': symbol,
            'timeframe': timeframe,
            'bars': bars,
            'total_tests': len(results),
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'optimized_version': True,
            'batch_processing': True
        },
        'top_configs': results[:top_n]
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    print(f"\n[GRID SEARCH BATCH] Top {top_n} resultats sauvegardes dans: {filename}")

    return filename


def main():
    """Fonction principale pour test en ligne de commande"""
    import sys

    if len(sys.argv) < 4:
        print("Usage: python grid_search_engine_batch.py SYMBOL TIMEFRAME BARS [WORKERS] [BATCH_SIZE]")
        print("Example: python grid_search_engine_batch.py EURUSD H1 2000 2 10")
        sys.exit(1)

    symbol = sys.argv[1]
    timeframe = sys.argv[2]
    bars = int(sys.argv[3])
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else None
    batch_size = int(sys.argv[5]) if len(sys.argv) > 5 else 10

    # Lancer le grid search BATCH
    results = run_grid_search_batch(symbol, timeframe, bars,
                                     max_workers=workers,
                                     batch_size=batch_size)

    # Sauvegarder les top 5
    report_path = save_top_results(results, symbol, timeframe, bars, top_n=5)

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
