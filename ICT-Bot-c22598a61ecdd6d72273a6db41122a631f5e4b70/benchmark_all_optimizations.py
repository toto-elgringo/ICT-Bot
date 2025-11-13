"""
Benchmark Complet de Toutes les Optimisations
Compare: Original, Shared Memory, Batch Processing, Cache MT5, Numba JIT
"""

import time
import sys
import os


def print_header(title):
    """Affiche un en-tête formaté"""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100)


def benchmark_original(symbol, timeframe, bars, workers):
    """Benchmark de la version ORIGINALE avec subprocess"""
    print_header("VERSION ORIGINALE (subprocess)")

    try:
        from grid_search_engine import run_grid_search

        # Limiter à 48 tests
        import grid_search_engine
        original_params = grid_search_engine.GRID_PARAMS.copy()
        grid_search_engine.GRID_PARAMS = {
            'RISK_PER_TRADE': [0.005, 0.01, 0.02],
            'RR_TAKE_PROFIT': [1.5, 1.8, 2.0, 2.5],
            'MAX_CONCURRENT_TRADES': [1],
            'COOLDOWN_BARS': [5],
            'ML_THRESHOLD': [0.5],
            'USE_ATR_FILTER': [True, False],
            'USE_CIRCUIT_BREAKER': [True, False]
        }
        # 3 × 4 × 1 × 1 × 1 × 2 × 2 = 48 tests

        start = time.time()
        results = run_grid_search(symbol, timeframe, bars, max_workers=workers)
        elapsed = time.time() - start

        # Restaurer
        grid_search_engine.GRID_PARAMS = original_params

        print(f"\n✅ Terminé en {elapsed:.1f}s ({elapsed/60:.2f} min)")
        print(f"   Vitesse: {len(results)/elapsed:.2f} tests/seconde")

        return elapsed, len(results), 'ORIGINALE'

    except ImportError as e:
        print(f"\n❌ Non disponible: {e}")
        return None, 0, 'ORIGINALE'


def benchmark_optimized_shared_memory(symbol, timeframe, bars, workers):
    """Benchmark de la version OPTIMISÉE (shared memory)"""
    print_header("VERSION OPTIMISÉE (Shared Memory)")

    try:
        from grid_search_engine_optimized import run_grid_search_optimized

        # Limiter à 48 tests
        import grid_search_engine_optimized
        original_params = grid_search_engine_optimized.GRID_PARAMS.copy()
        grid_search_engine_optimized.GRID_PARAMS = {
            'RISK_PER_TRADE': [0.005, 0.01, 0.02],
            'RR_TAKE_PROFIT': [1.5, 1.8, 2.0, 2.5],
            'MAX_CONCURRENT_TRADES': [1],
            'COOLDOWN_BARS': [5],
            'ML_THRESHOLD': [0.5],
            'USE_ATR_FILTER': [True, False],
            'USE_CIRCUIT_BREAKER': [True, False]
        }

        start = time.time()
        results = run_grid_search_optimized(symbol, timeframe, bars, max_workers=workers)
        elapsed = time.time() - start

        # Restaurer
        grid_search_engine_optimized.GRID_PARAMS = original_params

        print(f"\n✅ Terminé en {elapsed:.1f}s ({elapsed/60:.2f} min)")
        print(f"   Vitesse: {len(results)/elapsed:.2f} tests/seconde")

        return elapsed, len(results), 'SHARED_MEMORY'

    except ImportError as e:
        print(f"\n❌ Non disponible: {e}")
        return None, 0, 'SHARED_MEMORY'


def benchmark_batch_processing(symbol, timeframe, bars, workers, batch_size=10):
    """Benchmark de la version BATCH PROCESSING"""
    print_header(f"VERSION BATCH PROCESSING (batch_size={batch_size})")

    try:
        from grid_search_engine_batch import run_grid_search_batch

        # Limiter à 48 tests
        import grid_search_engine_batch
        original_params = grid_search_engine_batch.GRID_PARAMS.copy()
        grid_search_engine_batch.GRID_PARAMS = {
            'RISK_PER_TRADE': [0.005, 0.01, 0.02],
            'RR_TAKE_PROFIT': [1.5, 1.8, 2.0, 2.5],
            'MAX_CONCURRENT_TRADES': [1],
            'COOLDOWN_BARS': [5],
            'ML_THRESHOLD': [0.5],
            'USE_ATR_FILTER': [True, False],
            'USE_CIRCUIT_BREAKER': [True, False]
        }

        start = time.time()
        results = run_grid_search_batch(symbol, timeframe, bars,
                                         max_workers=workers,
                                         batch_size=batch_size)
        elapsed = time.time() - start

        # Restaurer
        grid_search_engine_batch.GRID_PARAMS = original_params

        print(f"\n✅ Terminé en {elapsed:.1f}s ({elapsed/60:.2f} min)")
        print(f"   Vitesse: {len(results)/elapsed:.2f} tests/seconde")

        return elapsed, len(results), f'BATCH_{batch_size}'

    except ImportError as e:
        print(f"\n❌ Non disponible: {e}")
        return None, 0, f'BATCH_{batch_size}'


def test_cache_performance(symbol, timeframe, bars):
    """Test la performance du cache MT5"""
    print_header("TEST CACHE MT5")

    try:
        from mt5_cache import MT5Cache, load_mt5_data_with_cache

        cache = MT5Cache()

        # Clear cache pour test propre
        cache.clear_cache(symbol, timeframe, bars)

        # Premier chargement (depuis MT5)
        print("\n[1] Premier chargement (depuis MT5)...")
        start = time.time()
        df1, info1 = load_mt5_data_with_cache(symbol, timeframe, bars,
                                               force_reload=True,
                                               use_numba=False)
        time_mt5 = time.time() - start
        print(f"✅ Temps: {time_mt5:.3f}s")

        # Deuxième chargement (depuis cache)
        print("\n[2] Deuxième chargement (depuis cache)...")
        start = time.time()
        df2, info2 = load_mt5_data_with_cache(symbol, timeframe, bars,
                                               force_reload=False,
                                               use_numba=False)
        time_cache = time.time() - start
        print(f"✅ Temps: {time_cache:.3f}s")

        speedup_cache = time_mt5 / time_cache if time_cache > 0 else 0
        print(f"\n🚀 CACHE SPEEDUP: {speedup_cache:.1f}x plus rapide")
        print(f"⏱️  Temps gagné: {(time_mt5 - time_cache)*1000:.0f}ms")

        return time_mt5, time_cache, speedup_cache

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return None, None, 0


def test_numba_performance(bars=10000):
    """Test la performance de Numba JIT"""
    print_header("TEST NUMBA JIT COMPILATION")

    try:
        import pandas as pd
        import numpy as np

        # Créer des données de test
        np.random.seed(42)
        closes = np.cumsum(np.random.randn(bars) * 0.01) + 100
        opens = closes + np.random.randn(bars) * 0.02
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(bars) * 0.05)
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(bars) * 0.05)

        df = pd.DataFrame({
            'time': pd.date_range('2024-01-01', periods=bars, freq='1H'),
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'tick_volume': np.random.randint(100, 1000, bars),
            'spread': np.random.randint(1, 10, bars),
            'real_volume': np.random.randint(1000, 10000, bars)
        })

        # Test Numba
        print(f"\n[1] Test version NUMBA sur {bars} barres...")
        try:
            from ict_indicators_numba import enrich_numba
            df_numba = df.copy()
            start = time.time()
            df_numba = enrich_numba(df_numba)
            time_numba = time.time() - start
            print(f"✅ Temps: {time_numba:.3f}s")
        except ImportError:
            print("❌ Numba non disponible (pip install numba)")
            time_numba = None

        # Test standard
        print(f"\n[2] Test version STANDARD sur {bars} barres...")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("ict_bot", "ict_bot_all_in_one.py")
            ict_bot = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ict_bot)

            df_standard = df.copy()
            start = time.time()
            df_standard = ict_bot.enrich(df_standard)
            time_standard = time.time() - start
            print(f"✅ Temps: {time_standard:.3f}s")
        except Exception:
            print("❌ Version standard non disponible")
            time_standard = None

        if time_numba and time_standard:
            speedup_numba = time_standard / time_numba
            print(f"\n🚀 NUMBA SPEEDUP: {speedup_numba:.1f}x plus rapide")
            print(f"⏱️  Temps gagné: {(time_standard - time_numba)*1000:.0f}ms par enrichissement")
            return time_standard, time_numba, speedup_numba
        else:
            return time_standard, time_numba, 0

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return None, None, 0


def main():
    if len(sys.argv) < 4:
        print("Usage: python benchmark_all_optimizations.py SYMBOL TIMEFRAME BARS [WORKERS]")
        print("Example: python benchmark_all_optimizations.py EURUSD H1 2000 1")
        print("\nCe script compare TOUTES les optimisations:")
        print("  1. Version ORIGINALE (subprocess)")
        print("  2. Version SHARED MEMORY (10x speedup attendu)")
        print("  3. Version BATCH PROCESSING (15x speedup attendu)")
        print("  4. Cache MT5 (2-3x sur chargement)")
        print("  5. Numba JIT (3x sur calculs)")
        sys.exit(1)

    symbol = sys.argv[1]
    timeframe = sys.argv[2]
    bars = int(sys.argv[3])
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    print("\n" + "=" * 100)
    print("  BENCHMARK COMPLET - TOUTES LES OPTIMISATIONS")
    print("=" * 100)
    print(f"\nParamètres:")
    print(f"  Symbole: {symbol}")
    print(f"  Timeframe: {timeframe}")
    print(f"  Barres: {bars}")
    print(f"  Workers: {workers}")
    print(f"\nNOTE: Tests limités à 48 combinaisons pour benchmark rapide")
    print("=" * 100)

    # Collecter tous les résultats
    all_results = []

    # Test 1: Cache MT5
    print("\n" + "🔥" * 50)
    print("PHASE 1: TEST CACHE MT5")
    print("🔥" * 50)
    time_mt5, time_cache, speedup_cache = test_cache_performance(symbol, timeframe, bars)

    # Test 2: Numba JIT
    print("\n" + "🔥" * 50)
    print("PHASE 2: TEST NUMBA JIT")
    print("🔥" * 50)
    time_standard_indicators, time_numba_indicators, speedup_numba = test_numba_performance(bars)

    # Test 3: Grid Search Original
    print("\n" + "🔥" * 50)
    print("PHASE 3: GRID SEARCH - VERSION ORIGINALE")
    print("🔥" * 50)
    elapsed_orig, count_orig, name_orig = benchmark_original(symbol, timeframe, bars, workers)
    if elapsed_orig:
        all_results.append((name_orig, elapsed_orig, count_orig))

    # Test 4: Grid Search Shared Memory
    print("\n" + "🔥" * 50)
    print("PHASE 4: GRID SEARCH - SHARED MEMORY")
    print("🔥" * 50)
    elapsed_shared, count_shared, name_shared = benchmark_optimized_shared_memory(symbol, timeframe, bars, workers)
    if elapsed_shared:
        all_results.append((name_shared, elapsed_shared, count_shared))

    # Test 5: Grid Search Batch Processing
    print("\n" + "🔥" * 50)
    print("PHASE 5: GRID SEARCH - BATCH PROCESSING")
    print("🔥" * 50)
    elapsed_batch, count_batch, name_batch = benchmark_batch_processing(symbol, timeframe, bars, workers, batch_size=10)
    if elapsed_batch:
        all_results.append((name_batch, elapsed_batch, count_batch))

    # RÉSUMÉ FINAL
    print("\n" + "=" * 100)
    print("  📊 RÉSUMÉ COMPLET DES OPTIMISATIONS")
    print("=" * 100)

    # Composants individuels
    print("\n🔧 OPTIMISATIONS COMPOSANTS:")
    print("-" * 100)
    if speedup_cache > 0:
        print(f"  ✅ Cache MT5:        {speedup_cache:.1f}x speedup ({time_mt5:.2f}s → {time_cache:.2f}s)")
    else:
        print(f"  ⚠️  Cache MT5:        Non testé")

    if speedup_numba > 0:
        print(f"  ✅ Numba JIT:        {speedup_numba:.1f}x speedup ({time_standard_indicators:.3f}s → {time_numba_indicators:.3f}s)")
    else:
        print(f"  ⚠️  Numba JIT:        Non disponible (pip install numba)")

    # Grid Search
    print("\n🚀 GRID SEARCH (48 tests):")
    print("-" * 100)

    if all_results:
        # Trouver le baseline (version originale ou la plus lente)
        baseline_time = None
        if elapsed_orig:
            baseline_time = elapsed_orig
            baseline_name = "ORIGINALE"
        else:
            # Utiliser la version la plus lente comme baseline
            baseline_time = max([r[1] for r in all_results])
            baseline_name = [r[0] for r in all_results if r[1] == baseline_time][0]

        for name, elapsed, count in sorted(all_results, key=lambda x: x[1], reverse=True):
            speedup = baseline_time / elapsed if elapsed > 0 else 0
            saved = baseline_time - elapsed
            print(f"  {name:20} {elapsed:7.1f}s  |  {speedup:5.2f}x  |  {saved/60:6.1f} min sauvées")

        # Extrapolation pour 1728 tests
        print("\n📈 EXTRAPOLATION POUR 1,728 TESTS COMPLETS:")
        print("-" * 100)

        for name, elapsed, count in sorted(all_results, key=lambda x: x[1], reverse=True):
            if count > 0:
                full_time = (elapsed / count) * 1728
                speedup = baseline_time / elapsed if elapsed > 0 else 0
                print(f"  {name:20} ~{full_time/60:6.0f} min ({full_time/3600:5.1f}h)  |  {speedup:5.2f}x")

        # Calcul du speedup cumulatif théorique
        print("\n🎯 SPEEDUP CUMULATIF THÉORIQUE:")
        print("-" * 100)
        cumulative_speedup = 1.0
        components = []

        if speedup_cache > 1:
            cumulative_speedup *= speedup_cache
            components.append(f"Cache: {speedup_cache:.1f}x")

        if speedup_numba > 1:
            cumulative_speedup *= speedup_numba
            components.append(f"Numba: {speedup_numba:.1f}x")

        # Shared memory apporte ~10x vs subprocess
        if elapsed_shared and elapsed_orig:
            shared_vs_orig = elapsed_orig / elapsed_shared
            components.append(f"Shared Memory: {shared_vs_orig:.1f}x")
            cumulative_speedup *= shared_vs_orig

        # Batch apporte ~1.5-2x supplémentaire
        if elapsed_batch and elapsed_shared:
            batch_vs_shared = elapsed_shared / elapsed_batch
            components.append(f"Batch Processing: {batch_vs_shared:.1f}x")

        print(f"  Composants: {' × '.join(components)}")
        print(f"  TOTAL CUMULATIF: ~{cumulative_speedup:.0f}x plus rapide que l'originale!")

        # Temps économisé
        if elapsed_orig and all_results:
            fastest = min([r[1] for r in all_results])
            fastest_name = [r[0] for r in all_results if r[1] == fastest][0]
            time_saved = elapsed_orig - fastest

            print(f"\n⏱️  TEMPS ÉCONOMISÉ ({fastest_name} vs ORIGINALE):")
            print(f"  48 tests:    {time_saved:.1f}s ({time_saved/60:.1f} min)")
            print(f"  1,728 tests: {time_saved * 36:.1f}s ({time_saved * 36/60:.0f} min)")

    else:
        print("  ❌ Aucune version disponible pour comparaison")

    print("\n" + "=" * 100)
    print("  💡 RECOMMANDATIONS")
    print("=" * 100)
    print("\n  Pour un Grid Search optimal:")
    print("  1. ✅ Installer Numba: pip install numba")
    print("  2. ✅ Utiliser grid_search_engine_batch.py (meilleure version)")
    print("  3. ✅ Le cache MT5 se remplit automatiquement")
    print("  4. ✅ Ajuster batch_size selon votre CPU (10-20 recommandé)")
    print("\n  Speedup attendu: 15-30x vs version originale")
    print("=" * 100 + "\n")


if __name__ == '__main__':
    main()
