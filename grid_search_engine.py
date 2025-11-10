"""
Grid Search Engine - Optimized Parameter Testing
Teste toutes les combinaisons de parametres pour trouver les meilleures configurations
"""

import os
import json
import itertools
import multiprocessing as mp
from datetime import datetime
from typing import List, Dict, Any, Tuple
import pandas as pd

# Parametres a tester
GRID_PARAMS = {
    'RISK_PER_TRADE': [0.005, 0.01, 0.02],
    'RR_TAKE_PROFIT': [1.5, 1.8, 2.0, 2.5],
    'MAX_CONCURRENT_TRADES': [1, 2, 3],
    'COOLDOWN_BARS': [3, 5, 8],
    'ML_THRESHOLD': [0.3, 0.4, 0.5, 0.6],
    'USE_ATR_FILTER': [True, False],
    'USE_CIRCUIT_BREAKER': [True, False]
}


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

    Args:
        results: Dictionnaire avec pnl_pct, sharpe_ratio, win_rate, max_drawdown_pct

    Returns:
        Score composite (float)
    """
    pnl = results.get('pnl_pct', 0.0)
    sharpe = results.get('sharpe_ratio', 0.0)
    win_rate = results.get('win_rate', 0.0)
    drawdown = results.get('max_drawdown_pct', 0.0)

    # Normaliser les valeurs
    pnl_norm = max(0, min(100, pnl)) / 100.0  # PnL entre 0 et 100%
    sharpe_norm = max(0, min(3, sharpe)) / 3.0  # Sharpe entre 0 et 3
    win_rate_norm = win_rate / 100.0  # Win rate entre 0 et 100%
    dd_norm = 1 - (abs(drawdown) / 100.0)  # Inverser le drawdown

    # Ponderation: 40% PnL, 30% Sharpe, 20% WinRate, 10% (1-DD)
    composite = (0.40 * pnl_norm +
                 0.30 * sharpe_norm +
                 0.20 * win_rate_norm +
                 0.10 * dd_norm)

    return composite


def run_single_backtest(args: Tuple[int, Dict[str, Any], str, str, int]) -> Dict[str, Any]:
    """
    Execute un backtest avec une configuration de parametres
    Fonction appelee en parallele par multiprocessing

    Args:
        args: Tuple (index, params, symbol, timeframe, bars)

    Returns:
        Dictionnaire avec les resultats du backtest
    """
    idx, params, symbol, timeframe, bars = args

    try:
        # Importer ici pour eviter les problemes de multiprocessing
        import subprocess
        import json

        # Creer un fichier de config temporaire pour ce test
        temp_config_name = f"temp_grid_{idx}"
        temp_config_path = f"config/{temp_config_name}.json"

        # Creer la config temporaire
        with open(temp_config_path, 'w', encoding='utf-8') as f:
            json.dump(params, f, indent=4)

        # Lancer le backtest
        cmd = [
            'python', 'ict_bot_all_in_one.py',
            '--mode', 'backtest',
            '--symbol', symbol,
            '--timeframe', timeframe,
            '--bars', str(bars),
            '--config-name', temp_config_name,
            '--no-ml',  # Desactiver ML pour plus de rapidite
            '--no-plot'  # Desactiver les graphiques pour plus de rapidite
        ]

        # Ajuster le timeout en fonction du nombre de barres
        # 1 minute pour 1000 barres, max 10 minutes
        timeout = min(300, max(60, bars // 1000 * 60))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        # Supprimer le fichier temporaire
        if os.path.exists(temp_config_path):
            os.remove(temp_config_path)

        # Verifier si le process s'est termine correctement
        if result.returncode != 0:
            # Sauvegarder stderr pour debug si c'est un des premiers tests
            if idx < 3:
                print(f"[DEBUG] Test {idx} a echoue (returncode={result.returncode})")
                print(f"[DEBUG] stderr: {result.stderr[:500]}")  # Premiers 500 chars

        # Parser la sortie pour extraire les resultats
        output = result.stdout
        stderr = result.stderr

        # Debug: sauvegarder la sortie du premier test pour verification
        if idx == 0:
            os.makedirs('Grid', exist_ok=True)
            with open('Grid/debug_first_test.txt', 'w', encoding='utf-8') as f:
                f.write("=== STDOUT ===\n")
                f.write(output)
                f.write("\n\n=== STDERR ===\n")
                f.write(stderr)
            print(f"[DEBUG] Sortie du test 0 sauvegardee dans Grid/debug_first_test.txt")

        # Extraire les metriques de la sortie
        results = {
            'config_id': idx,
            'params': params,
            'pnl_pct': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown_pct': 0.0,
            'success': False
        }

        # Parser les resultats du backtest depuis la sortie
        # Format sur 2 lignes:
        # Ligne 1: "=== METRICS (EURUSD H4) ==="
        # Ligne 2: "Trades: 1 | Winrate: 0.0% | PnL: -2928.94 | MaxDD: -29.29% | Equity finale: 7071.06"

        lines = output.split('\n')
        for i, line in enumerate(lines):
            # Chercher la ligne avec les donnees (pas le header)
            if 'Trades:' in line and 'Winrate:' in line and 'PnL:' in line:
                try:
                    # Extraire Trades
                    trades_part = line.split('Trades:')[1].split('|')[0].strip()
                    results['total_trades'] = int(trades_part)

                    # Extraire Winrate
                    winrate_part = line.split('Winrate:')[1].split('%')[0].strip()
                    results['win_rate'] = float(winrate_part)

                    # Extraire PnL
                    pnl_part = line.split('PnL:')[1].split('|')[0].strip()
                    pnl_value = float(pnl_part)
                    # Convertir en pourcentage (assumant capital initial de 10000)
                    results['pnl_pct'] = (pnl_value / 10000.0) * 100.0

                    # Extraire MaxDD
                    dd_part = line.split('MaxDD:')[1].split('%')[0].strip()
                    results['max_drawdown_pct'] = float(dd_part)

                    results['success'] = True

                    # Debug pour les premiers tests
                    if idx < 3:
                        print(f"[DEBUG] Test {idx} parse: {results['total_trades']} trades, PnL {results['pnl_pct']:.2f}%")

                except Exception as e:
                    # Si parsing echoue, garder les valeurs par defaut
                    if idx < 3:
                        print(f"[DEBUG] Test {idx} ERREUR parsing: {e}")
                        print(f"[DEBUG] Ligne: {line[:100]}")
                    pass
                break  # Une seule ligne de donnees suffit

        # Calculer un Sharpe ratio approximatif si on a des trades
        if results['total_trades'] > 0 and results['win_rate'] > 0:
            # Approximation simple: WinRate normalisée * sqrt(trades) / (1 + abs(DD))
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
        # En cas d'erreur, retourner un resultat vide
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


def run_grid_search(symbol: str, timeframe: str, bars: int,
                   max_workers: int = None,
                   callback=None) -> List[Dict[str, Any]]:
    """
    Execute la recherche en grille complete

    Args:
        symbol: Paire a tester
        timeframe: Timeframe a tester
        bars: Nombre de barres
        max_workers: Nombre de workers (None = auto-detect, 0 = mode sequentiel)
        callback: Fonction callback pour progression (progress, total)

    Returns:
        Liste des resultats tries par score composite (meilleur en premier)
    """
    import time

    # Generer toutes les combinaisons
    combinations = generate_all_combinations()
    total_tests = len(combinations)

    print(f"\n[GRID SEARCH] Lancement de {total_tests} tests...")
    print(f"[GRID SEARCH] Parametres: {symbol} {timeframe} {bars} barres")

    # Detecter le nombre de CPU disponibles
    # LIMITATION: Max 2 workers par defaut pour eviter les crashs memoire
    if max_workers is None:
        max_workers = min(2, max(1, mp.cpu_count() - 2))  # Maximum 2 workers par defaut
    elif max_workers == 0:
        max_workers = 1  # Mode sequentiel
    else:
        # Limiter a 4 workers max pour eviter surcharge
        max_workers = min(max_workers, 4)

    print(f"[GRID SEARCH] Utilisation de {max_workers} workers paralleles")
    if max_workers <= 2:
        print(f"[GRID SEARCH] Mode conservateur activé pour éviter la surcharge mémoire")

    # Preparer les arguments pour chaque test
    test_args = [
        (idx, params, symbol, timeframe, bars)
        for idx, params in enumerate(combinations)
    ]

    # Executer les tests
    results = []
    completed = 0

    if max_workers == 1:
        # Mode sequentiel (plus lent mais plus stable)
        print("[GRID SEARCH] Mode séquentiel (1 test à la fois)")
        for args in test_args:
            result = run_single_backtest(args)
            results.append(result)
            completed += 1

            # Appeler le callback de progression
            if callback:
                callback(completed, total_tests)

            # Afficher la progression
            if completed % 10 == 0 or completed == total_tests:
                print(f"[GRID SEARCH] Progression: {completed}/{total_tests} tests completes")

            # Petit delai pour ne pas surcharger
            time.sleep(0.1)
    else:
        # Mode parallele avec limitation
        with mp.Pool(processes=max_workers) as pool:
            # Utiliser chunksize=1 pour traiter un test a la fois par worker
            for result in pool.imap_unordered(run_single_backtest, test_args, chunksize=1):
                results.append(result)
                completed += 1

                # Appeler le callback de progression
                if callback:
                    callback(completed, total_tests)

                # Afficher la progression
                if completed % 10 == 0 or completed == total_tests:
                    print(f"[GRID SEARCH] Progression: {completed}/{total_tests} tests completes")

    # Trier par score composite (meilleur en premier)
    results.sort(key=lambda x: x['composite_score'], reverse=True)

    print(f"\n[GRID SEARCH] Tests termines! Meilleur score: {results[0]['composite_score']:.4f}")

    return results


def save_top_results(results: List[Dict[str, Any]],
                    symbol: str,
                    timeframe: str,
                    bars: int,
                    top_n: int = 5) -> str:
    """
    Sauvegarde les N meilleurs resultats dans Grid/

    Args:
        results: Liste des resultats tries
        symbol: Paire testee
        timeframe: Timeframe testee
        bars: Nombre de barres
        top_n: Nombre de top resultats a sauvegarder

    Returns:
        Chemin du fichier sauvegarde
    """
    # Creer le dossier Grid/ s'il n'existe pas
    os.makedirs('Grid', exist_ok=True)

    # Nom du fichier avec timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Grid/grid_results_{symbol}_{timeframe}_{timestamp}.json"

    # Preparer le rapport
    report = {
        'metadata': {
            'symbol': symbol,
            'timeframe': timeframe,
            'bars': bars,
            'total_tests': len(results),
            'timestamp': timestamp,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'top_configs': results[:top_n]
    }

    # Sauvegarder en JSON
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    print(f"\n[GRID SEARCH] Top {top_n} resultats sauvegardes dans: {filename}")

    return filename


def main():
    """Fonction principale pour test en ligne de commande"""
    import sys

    if len(sys.argv) < 4:
        print("Usage: python grid_search_engine.py SYMBOL TIMEFRAME BARS [WORKERS]")
        print("Example: python grid_search_engine.py EURUSD H1 2000 4")
        sys.exit(1)

    symbol = sys.argv[1]
    timeframe = sys.argv[2]
    bars = int(sys.argv[3])
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else None

    # Lancer le grid search
    results = run_grid_search(symbol, timeframe, bars, max_workers=workers)

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
