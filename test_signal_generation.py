"""
Test Signal Generation v2.1
Quick diagnostic to verify signal generation works after bugfixes
"""

import os
import sys
import json

# Import the main bot module
import ict_bot_all_in_one as bot

def test_signal_generation():
    """Test that v2.1 signal generation produces trades"""

    print("=" * 60)
    print("ICT Bot v2.1 Signal Generation Test")
    print("=" * 60)

    # Load default config
    print("\n[1/5] Loading configuration...")
    bot.load_config_from_file('Default')
    print(f"    - BOS_MAX_AGE: {bot.BOS_MAX_AGE}")
    print(f"    - FVG_BOS_MAX_DISTANCE: {bot.FVG_BOS_MAX_DISTANCE}")
    print(f"    - USE_FVG_MITIGATION_FILTER: {bot.USE_FVG_MITIGATION_FILTER}")
    print(f"    - USE_BOS_RECENCY_FILTER: {bot.USE_BOS_RECENCY_FILTER}")
    print(f"    - USE_MARKET_STRUCTURE_FILTER: {bot.USE_MARKET_STRUCTURE_FILTER}")

    # Connect to MT5
    print("\n[2/5] Connecting to MT5...")
    import MetaTrader5 as mt5

    if not mt5.initialize(login=bot.LOGIN, password=bot.PASSWORD, server=bot.SERVER):
        print("    ERROR: MT5 connection failed!")
        return False
    print("    OK: MT5 connected")

    # Load data
    print("\n[3/5] Loading market data (1000 bars M5)...")
    symbol = "EURUSD"
    timeframe = mt5.TIMEFRAME_M5
    bars = 1000

    if not mt5.symbol_select(symbol, True):
        print(f"    ERROR: Symbol {symbol} not available!")
        mt5.shutdown()
        return False

    df = bot.enrich(bot.load_rates_mt5(symbol, timeframe, bars))
    print(f"    OK: Loaded {len(df)} bars")
    print(f"    Date range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")

    # Check v2.1 columns exist
    print("\n[4/5] Verifying v2.1 enrichment columns...")
    required_cols = ['bos_age', 'bos_strength', 'fvg_mitigated', 'market_structure', 'structure_score']
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        print(f"    ERROR: Missing columns: {missing}")
        mt5.shutdown()
        return False
    print(f"    OK: All v2.1 columns present")

    # Count FVGs and BOS
    print("\n    Market Data Summary:")
    fvg_count = (df['fvg_side'] != 'none').sum()
    bos_up_count = df['bos_up'].sum()
    bos_down_count = df['bos_down'].sum()
    print(f"    - FVGs detected: {fvg_count}")
    print(f"    - BOS Up: {bos_up_count}")
    print(f"    - BOS Down: {bos_down_count}")

    # Check market structure distribution
    struct_counts = df['market_structure'].value_counts()
    print(f"    - Market Structure:")
    for struct, count in struct_counts.items():
        print(f"      - {struct}: {count} bars ({count/len(df)*100:.1f}%)")

    # Run backtest
    print("\n[5/5] Running backtest...")
    info = mt5.symbol_info(symbol)

    # Create ML filter
    ml = bot.MLFilter(model_path=None, use_meta_labelling=True)

    metrics, hist = bot.backtest(
        df,
        symbol=symbol,
        risk=bot.RISK_PER_TRADE,
        rr=bot.RR_TAKE_PROFIT,
        cooldown=bot.COOLDOWN_BARS,
        use_killzones=True,
        ml=ml,
        info=info
    )

    mt5.shutdown()

    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)

    st = metrics['stats']
    print(f"\nMetrics:")
    print(f"  - Trades: {metrics['trades']}")
    print(f"  - Win Rate: {metrics['winrate']:.1f}%")
    print(f"  - PnL: ${metrics['pnl']:.2f}")
    print(f"  - Max DD: {metrics['dd']:.2f}%")

    print(f"\nFilter Statistics:")
    total_bars = len(df) - 50
    print(f"  Total bars analyzed: {total_bars}")
    print(f"\n  PRIMARY FILTERS:")
    print(f"    - Cooldown: {st['cooldown_filtered']} ({st['cooldown_filtered']/total_bars*100:.1f}%)")
    print(f"    - Kill zones: {st['killzone_filtered']} ({st['killzone_filtered']/total_bars*100:.1f}%)")
    print(f"    - No FVG confluence: {st['no_fvg']} ({st['no_fvg']/total_bars*100:.1f}%)")
    print(f"    - Neutral bias: {st['neutral_bias']}")
    print(f"    - FVG/Bias mismatch: {st['fvg_bias_mismatch']}")

    print(f"\n  v2.1 FILTERS:")
    print(f"    - FVG mitigated: {st.get('fvg_mitigated_filtered', 0)}")
    print(f"    - BOS too old: {st.get('bos_too_old_filtered', 0)}")
    print(f"    - FVG-BOS too far: {st.get('fvg_bos_too_far_filtered', 0)}")
    print(f"    - Market structure: {st.get('market_structure_filtered', 0)}")
    print(f"    - Extreme volatility: {st.get('extreme_volatility_filtered', 0)}")

    print(f"\n  FINAL FILTERS:")
    print(f"    - ATR filtered: {st['atr_filtered']}")
    print(f"    - ML filtered: {st['ml_filtered']}")
    print(f"    - SL too close: {st['sl_too_close']}")
    print(f"    - Max trades: {st['max_trades_reached']}")

    print(f"\n  ENTRIES VALIDATED: {st['entries']}")

    # Diagnosis
    print("\n" + "=" * 60)
    print("DIAGNOSIS")
    print("=" * 60)

    if metrics['trades'] == 0:
        print("\nCRITICAL ISSUE: ZERO TRADES GENERATED")
        print("\nLikely causes:")

        if st['killzone_filtered'] > total_bars * 0.5:
            print("  1. Kill zone filtering too aggressive")
            print(f"     - {st['killzone_filtered']/total_bars*100:.1f}% of bars filtered")
            print("     - Solution: Use more data or check timezone settings")

        if st['no_fvg'] > total_bars * 0.2:
            print("  2. FVG confluence not found")
            print(f"     - {st['no_fvg']} bars had no valid FVG+BOS confluence")
            print("     - Check if v2.1 filters are too strict")

        if fvg_count < 10:
            print("  3. Not enough FVGs detected")
            print(f"     - Only {fvg_count} FVGs found in {len(df)} bars")
            print("     - Data may be too short or market too quiet")

        if bos_up_count + bos_down_count < 10:
            print("  4. Not enough BOS detected")
            print(f"     - Only {bos_up_count + bos_down_count} BOS found")
            print("     - Swing detection may need tuning")

        return False
    else:
        print(f"\nSUCCESS: {metrics['trades']} trades generated")
        print(f"Signal generation is working correctly!")

        if metrics['trades'] < 5:
            print(f"\nWARNING: Very few trades ({metrics['trades']})")
            print("Consider:")
            print("  - Using more historical data")
            print("  - Relaxing v2.1 filters (BOS_MAX_AGE, FVG_BOS_MAX_DISTANCE)")
            print("  - Checking if market conditions match strategy")

        return True

if __name__ == "__main__":
    try:
        success = test_signal_generation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
