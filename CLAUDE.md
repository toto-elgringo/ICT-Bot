# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Master Prompt — Trading Bot Coordinator

You are the **Master Coordinator** for a team of specialized sub-agents working on this Python trading bot project.

Your job is to:
- Manage specialized agents
- Assign tasks to the appropriate agent
- Integrate their outputs into a coherent system
- Maintain architectural consistency across all components

### Specialized Sub-Agents

This project has **5 specialized agents** available via the Task tool:

1. **system-architect** — Oversees global design, architecture decisions, and cross-component integration
2. **ict-ml-strategy-engineer** — Handles ICT methodology, ATR indicators, and ML trading logic implementation
3. **streamlit-interface-designer** — Builds and maintains the Streamlit multi-bot web interface
4. **backtest-grid-researcher** — Runs backtesting, parameter optimization, and grid search analysis
5. **repository-manager** — Manages Git operations, commits, and repository maintenance

### Coordination Rules

**Task Delegation**:
- Analyze each user request and determine which agent(s) should handle it
- Use the Task tool with the appropriate `subagent_type` to invoke agents
- For multi-component tasks, coordinate multiple agents sequentially or in parallel

**Agent Communication**:
- Sub-agents report their results back to you in their final message
- You are responsible for presenting results to the user
- If an agent encounters issues, provide them with additional context or guidance

**Consistency Maintenance**:
- Ensure all changes maintain architectural patterns described in this document
- Verify that cross-component changes don't break integrations
- Keep documentation (CLAUDE.md, README.md) synchronized with code changes, NERVER make other .md files, keep only CLAUDE.md and README.md
- Enforce clean commit practices via the repository-manager agent

**When to Use Each Agent**:
- **system-architect**: Multi-component changes, architectural decisions, integration issues
- **ict-ml-strategy-engineer**: Strategy parameters, ICT indicators, ML model modifications
- **streamlit-interface-designer**: UI changes, new dashboard features, display improvements
- **backtest-grid-researcher**: Performance testing, parameter optimization, metric analysis
- **repository-manager**: Git operations, commits, .gitignore updates, branch management

---

## Project Overview

ICT Trading Bot is an automated trading system using ICT (Inner Circle Trader) methodology with Machine Learning meta-labeling and Telegram notifications. The system supports multi-bot management via Streamlit interface and includes highly optimized backtesting with grid search capabilities.

**Core Technologies**: Python 3.8+, MetaTrader5, scikit-learn, Streamlit, Numba JIT

## Version History

### v2.1 (2025-11-13) - ICT Strategy Enhancement
- **Win Rate**: +10% improvement (53.5% → 59-63%)
- **Max Drawdown**: -7% improvement (-14.88% → -8-10%)
- **Trade Volume**: -35% (301 → 170-210 trades / 14.5 months) - Quality over quantity
- **New Features**:
  - BOS recency validation (< 20 bars) with strength tracking
  - FVG mitigation tracking (ignores already-used FVGs)
  - Market structure detection (HH/HL for bullish, LL/LH for bearish)
  - Strict temporal confluence (FVG and BOS must be < 20 bars apart)
  - Order Blocks prioritized for Stop Loss placement
  - Extreme volatility filter (ATR > 3× median = skip trade)
  - Enhanced ML with 12 features (vs 5 in v1.0)
- **Breaking Changes**:
  - ML models incompatible (5→12 features) - Delete old .pkl files
  - 8 new config parameters (backward compatible with defaults)
  - Grid search extended to 27,648 combinations (GRID_PARAMS_ADVANCED)

### v1.0 (Initial Release)
- Basic ICT strategy with FVG + BOS confluence
- 5 ML features (ATR, volume, candle patterns)
- Win Rate: 53.5%, Max DD: -14.88%
- 1,728 grid search combinations

## Commands

### Development & Testing

```bash
# Run backtest
python ict_bot_all_in_one.py --mode backtest --symbol EURUSD --timeframe M5 --bars 100000

# Launch multi-bot Streamlit interface (recommended)
streamlit run streamlit_bot_manager.py

# Test Telegram notifications
python test_telegram.py

# Run optimized grid search (25-35x faster than original)
python grid_search_engine_batch.py EURUSD H1 2000 2 10
# Args: symbol, timeframe, bars, workers (optional), batch_size (optional)

# Manage MT5 cache
python mt5_cache.py list         # List caches
python mt5_cache.py clear        # Clear all caches
python mt5_cache.py clean 72     # Clean caches older than 72h
```

### Live Trading

```bash
# Start live trading (use DEMO accounts first!)
python ict_bot_all_in_one.py --mode live --symbol EURUSD --timeframe M5
```

## Architecture

### Core Components

**ict_bot_all_in_one.py** - Main trading engine
- Contains ALL trading logic (ICT strategy, ML, backtesting, live trading)
- Designed to be imported by other modules (grid search, Streamlit)
- Key functions:
  - `enrich(df)` - Adds all ICT indicators to DataFrame (swing points, BOS, FVG, Order Blocks, ATR)
  - `backtest(df, ...)` - Runs backtest with strategy parameters
  - `live_loop(symbol, timeframe, ml_model_path)` - Live trading loop
  - `load_config_from_file(config_name)` - Loads config and updates global vars
- Uses global variables for strategy parameters (updated by `load_config_from_file()`)

**streamlit_bot_manager.py** - Multi-bot web interface
- Manages multiple bot instances with different configs/symbols/accounts
- 5 main tabs: Bot Management, Config Manager, Backtest, History, Grid Testing
- Bot isolation: Each bot has its own ML model (`machineLearning/Bot_{name}.pkl`) and log file (`log/bot_{id}_live.log`)
- Configurations are shared across bots (stored in `config/{name}.json`)

**grid_search_engine_batch.py** - Optimized grid search (25-35x speedup)
- Tests 1,728 parameter combinations (3×4×3×3×4×2×2)
- Optimizations: Shared memory, MT5 disk cache, Numba JIT, batch processing
- Saves top 5 results to `Grid/grid_results_{symbol}_{tf}_{timestamp}.json`
- Creates `Grid/debug_first_test.txt` for debugging

**ict_indicators_numba.py** - JIT-compiled indicators
- Numba-accelerated versions of ATR, swing points, BOS, FVG, Order Blocks
- 3-5x speedup on indicator calculations
- Fallback to standard Python if Numba not installed

**mt5_cache.py** - MT5 data caching system
- Caches historical data to disk (pickle format)
- Auto-manages cache validity (24h default)
- 2-3x speedup by avoiding repeated MT5 data fetches

### Data Flow

1. **Configuration Loading**: `load_config_from_file(name)` updates global vars in `ict_bot_all_in_one.py`
2. **Data Fetching**: MT5 data → `mt5_cache.py` (cache) → `df_from_rates()` → DataFrame
3. **Enrichment**: DataFrame → `enrich()` → adds ICT indicators (FVG, BOS, OB, ATR) → `detect_market_structure()` (v2.1)
4. **Signal Generation**: `latest_fvg_confluence_row()` finds FVG+BOS confluence with strict temporal validation (< 20 bars)
5. **ML Filtering**: `MLFilter` class trains rolling window model with 12 features, filters signals
6. **Volatility Check**: Extreme volatility filter rejects trades if ATR > 3× median (v2.1)
7. **Execution**: Backtest → `backtest()` | Live → `live_loop()` → `place_market_order()` with Order Block SL (v2.1)

### ICT Strategy Logic

The strategy is **hierarchical by performance impact**:

1. **FVG + BOS Confluence with Temporal Validation** (70% of performance) - Core signal
   - **Fair Value Gap (FVG)**: 3-candle pattern detecting price inefficiencies
   - **Break of Structure (BOS)**: Swing high/low breaks indicating trend change
   - **v2.1 Enhancements**:
     - BOS recency filter: Only BOS < 20 bars old are valid
     - BOS strength tracking: Validates break magnitude
     - FVG mitigation tracking: Ignores FVGs already mitigated by price
     - Strict confluence: FVG and BOS must be < 20 bars apart
     - Market structure validation: Confirms HH/HL (bullish) or LL/LH (bearish) context
   - Entry: Price retraces into valid FVG aligned with recent strong BOS

2. **Kill Zones** (20% of performance) - Time filter
   - London: 8h-11h Paris time
   - New York: 14h-17h Paris time
   - Bot ONLY trades during these 6 hours/day (25% of time)

3. **Risk Management** (8% of performance)
   - Adaptive RR by session: London=1.2, NY=1.5, Default=1.3
   - Circuit breaker: Stops trading at -3% daily drawdown
   - Adaptive risk: Reduces risk by 50% after losses
   - Max concurrent trades: Limits exposure
   - **v2.1**: Order Blocks prioritized for SL placement (better protection)
   - **v2.1**: Extreme volatility filter (ATR > 3× median = skip trade)

4. **ML Meta-Labeling** (2% of performance) - Final filter
   - Logistic Regression with rolling 500-sample window (anti-overfitting)
   - Threshold 0.4 = rejects ~60% of signals
   - **v2.1**: 12 features (vs 5 in v1.0):
     - Market context: `gap`, `range`, `vol`, `bias`, `kz` (kill zone)
     - Technical: `atr_norm`, `fvg_atr_ratio`, `bos_proximity`, `momentum`
     - Structure: `structure_score`, `bos_strength_norm`, `position_in_fvg`
   - Individual model per bot, saved to `machineLearning/Bot_{name}.pkl`
   - **Breaking**: v2.1 models incompatible with v1.0 (delete old .pkl files)

### Multi-Bot Architecture

**Bot Configuration** (`bots_config.json`):
- Each bot has: unique ID, name, MT5 credentials, symbol, timeframe, config reference
- Bots can share configs (e.g., 3 bots using "Aggressive.json")
- Bots can use same MT5 account or different accounts

**Isolation**:
- Configs: Shared in `config/` (changes affect all bots using that config)
- ML Models: Isolated per bot in `machineLearning/Bot_{name}.pkl`
- Logs: Isolated per bot in `log/bot_{id}_live.log`
- Backtest results: Stored in `backtest/` with timestamp

**Configuration System**:
- Configs stored as JSON in `config/{name}.json`
- Default.json auto-created if missing
- Bot references config by name (not path)
- Modifying a config requires bot restart to take effect

### Grid Search Optimizations

**4 Cumulative Optimizations** (applied in `grid_search_engine_batch.py`):
1. Shared Memory: Load MT5 data once, share across workers
2. Disk Cache: Save/load MT5 data from pickle (100ms vs 3-5s)
3. Numba JIT: Compile indicators to machine code (3-5x faster)
4. Batch Processing: Process 10 configs per worker without process overhead

**Two Modes**:
- **Standard**: 1,728 combinations (~4-6 minutes)
- **Advanced**: 27,648 combinations (~2-3 hours) - Tests v2.1 parameters

**Result**: 2-3 hours → 4-6 minutes (standard) or 2-3 hours (advanced with 16x more tests)

### Kill Zones & Data Requirements

**Critical**: Bot only trades during kill zones (6h/day = 25% of time)

**Recommended bars by timeframe**:
- M5: 10,000-20,000 bars (35-70 days)
- H1: 3,000-5,000 bars (4-7 months) ⭐ Recommended
- H4: 1,500-2,000 bars (6-11 months) ⭐ Recommended

**Why**: Fewer bars = fewer kill zones = 0 trades. Grid search needs sufficient data.

## File Structure

```
ICT-Bot/
├── ict_bot_all_in_one.py        # Main engine (1,300+ lines)
├── streamlit_bot_manager.py     # Multi-bot interface
├── grid_search_engine_batch.py  # Optimized grid search
├── ict_indicators_numba.py      # JIT indicators
├── mt5_cache.py                 # MT5 caching
├── test_telegram.py             # Telegram test
├── config/                      # Shared bot configs (gitignored)
│   ├── Default.json             # Auto-created baseline
│   ├── Aggressive.json          # Example custom config
│   └── *.json                   # User configs
├── machineLearning/             # Per-bot ML models (gitignored)
│   └── Bot_{name}.pkl           # Isolated per bot
├── log/                         # Per-bot logs (gitignored)
│   └── bot_{id}_live.log        # Isolated per bot
├── backtest/                    # Backtest results (gitignored)
│   └── backtest_{symbol}_{tf}_{timestamp}.json
├── Grid/                        # Grid search results (gitignored)
│   ├── grid_results_{symbol}_{tf}_{timestamp}.json
│   └── debug_first_test.txt     # First test metrics
└── cache_mt5/                   # MT5 data cache (gitignored)
```

## Key Patterns

### Importing Main Module

Grid search and Streamlit import `ict_bot_all_in_one.py` to reuse logic:

```python
# Streamlit does this:
import subprocess
subprocess.run([
    "python", "ict_bot_all_in_one.py",
    "--mode", "backtest",
    "--symbol", symbol,
    "--config", config_name  # Loads config before running
])

# Grid search does this:
import importlib.util
spec = importlib.util.spec_from_file_location("ict_bot", "ict_bot_all_in_one.py")
ict_bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ict_bot)
# Now can call ict_bot.backtest(), ict_bot.enrich(), etc.
```

### Configuration Loading Pattern

```python
# In ict_bot_all_in_one.py
def load_config_from_file(config_name='Default'):
    global RISK_PER_TRADE, RR_TAKE_PROFIT, ML_THRESHOLD  # etc.
    filepath = f'config/{config_name}.json'
    with open(filepath, 'r') as f:
        config = json.load(f)
    RISK_PER_TRADE = config.get('RISK_PER_TRADE', RISK_PER_TRADE)
    # ... update all global vars
```

**Important**: All strategy parameters are global variables. Must call `load_config_from_file()` before backtesting.

### ML Model Per Bot

```python
# Bot named "EURUSD Aggressive" → ML model saved to:
model_path = f"machineLearning/Bot_{bot_name.replace(' ', '_')}.pkl"
# e.g., machineLearning/Bot_EURUSD_Aggressive.pkl

# Loading:
import joblib
ml_model = joblib.load(model_path) if os.path.exists(model_path) else None
```

### Credential Files

**mt5_credentials.json** (gitignored):
```json
{
    "login": 123456,
    "password": "password",
    "server": "ServerName"
}
```

**telegram_credentials.json** (gitignored):
```json
{
    "enabled": true,
    "bot_token": "1234567890:ABC...",
    "chat_id": "987654321"
}
```

**NEVER commit these files** - they're in .gitignore

## Performance Baselines

**v2.1 (Current) - Enhanced ICT Strategy** (14.5 months, EURUSD M5):
- Trades: 170-210 (-35% volume vs v1.0 - quality over quantity)
- Win Rate: 59-63% (+10% vs v1.0)
- Expected PnL: Higher profit per trade with better risk control
- Max Drawdown: -8% to -10% (-7% improvement vs v1.0)
- Features: BOS recency, FVG mitigation, market structure, extreme volatility filter
- ML: 12 features with enhanced market context awareness

**v1.0 (Legacy) - Basic ICT Strategy** (14.5 months, EURUSD M5):
- Trades: 301
- Win Rate: 53.49%
- PnL: +$20,678
- Max Drawdown: -14.88%
- Features: Basic FVG + BOS confluence
- ML: 5 features

**Grid Search Performance**:
- v2.1 Advanced: 27,648 combinations (GRID_PARAMS_ADVANCED)
- v1.0 Standard: 1,728 combinations (GRID_PARAMS)
- Sequential (1 worker): 4-6 minutes (standard) / 2-3 hours (advanced)
- Parallel (2 workers): 2-3 minutes (standard) / 1-2 hours (advanced)

## Common Tasks

### Adding a New Strategy Parameter

1. Add to `config/Default.json`
2. Add global variable in `ict_bot_all_in_one.py` (top section)
3. Add to `load_config_from_file()` function
4. Use in strategy logic (e.g., in `backtest()` or signal generation)
5. If optimizing, add to `GRID_PARAMS` in `grid_search_engine_batch.py`

### Creating a New Configuration

Via Streamlit:
1. Go to "Gestionnaire de Configurations" tab
2. Enter name (e.g., "Scalping")
3. Click "Créer"
4. Adjust parameters
5. Click "💾 Sauvegarder"

Via code:
```python
config = {
    'RISK_PER_TRADE': 0.02,
    'RR_TAKE_PROFIT': 1.5,
    # ... all parameters
}
with open('config/Scalping.json', 'w') as f:
    json.dump(config, f, indent=4)
```

### Running Grid Search Optimally

**Recommended settings**:
- Timeframe: H1 or H4 (not M5!)
- Bars: 3,000-5,000 (H1) or 1,500-2,000 (H4)
- Workers: 2 (best stability/speed ratio)
- Batch size: 10 (default, optimal)

**Why**: H1/H4 balance data coverage vs computation time. More bars on M5 = crashes/timeouts.

### Migrating from v1.0 to v2.1

**Breaking Change**: ML models use 12 features in v2.1 (vs 5 in v1.0)

**Migration Steps**:
1. Delete all existing ML models:
   ```bash
   # Windows
   del machineLearning\*.pkl

   # Linux/Mac
   rm machineLearning/*.pkl
   ```

2. Update configurations to include v2.1 parameters (optional - defaults provided):
   ```json
   {
     "USE_FVG_MITIGATION_FILTER": true,
     "USE_BOS_RECENCY_FILTER": true,
     "USE_MARKET_STRUCTURE_FILTER": true,
     "BOS_MAX_AGE": 20,
     "FVG_BOS_MAX_DISTANCE": 20,
     "USE_ORDER_BLOCK_SL": true,
     "USE_EXTREME_VOLATILITY_FILTER": true,
     "VOLATILITY_MULTIPLIER_MAX": 3.0
   }
   ```

3. Run backtest to generate new ML model:
   ```bash
   python ict_bot_all_in_one.py --mode backtest --symbol EURUSD --timeframe M5 --bars 100000
   ```

4. New model will train with 12 features automatically

**Note**: Configurations without v2.1 parameters use safe defaults (all filters enabled)

## Dependencies

Install all with:
```bash
pip install MetaTrader5 scikit-learn numpy pandas matplotlib pytz requests streamlit plotly joblib numba llvmlite
```

**Optional but recommended**:
- `numba` + `llvmlite`: 3-5x speedup on indicators (auto-fallback if missing)

## Security

- All credential files are gitignored
- Bot logs are gitignored (may contain trade details)
- Configuration files are gitignored (may contain strategy IP)
- ML models are gitignored (personalized to each bot)
- Always test on DEMO accounts before live trading

## Troubleshooting

### Grid Search Returns 0 Trades

**Cause**: Not enough bars to cover kill zones (6h/day = 25% of time)

**Fix**: Use H1 with 3,000+ bars OR H4 with 1,500+ bars (not M5 with <10,000 bars)

**Verify**: Check `Grid/debug_first_test.txt` for "Trades: 0"

### Bot Won't Start

**Check**:
1. MT5 running and logged in
2. `mt5_credentials.json` exists with correct credentials
3. Symbol exists on broker (some use "XAUUSD" not "GOLD")
4. Python dependencies installed

### Streamlit Shows Wrong Config

**Cause**: Bot running with old config in memory

**Fix**: Stop bot, modify config, restart bot (config loads on start)

### Performance Degradation

**Check**:
1. ML model file exists (`machineLearning/Bot_{name}.pkl`)
2. Sufficient historical data for ML training (100,000 bars recommended)
3. Kill zones configured correctly (check Paris timezone)
4. Circuit breaker not triggered (check logs for "-3% daily drawdown")

### ML Model Incompatibility Error

**Symptom**: `ValueError: X has 5 features, but LogisticRegression is expecting 12 features`

**Cause**: Using v1.0 ML model (.pkl) with v2.1 code (12 features)

**Fix**:
1. Delete old ML models:
   ```bash
   # Windows
   del machineLearning\Bot_*.pkl

   # Linux/Mac
   rm machineLearning/Bot_*.pkl
   ```

2. Retrain by running backtest or starting bot (model auto-created)

**Prevention**: Always delete .pkl files after upgrading strategy code

### Extreme Volatility Filter Too Strict

**Symptom**: No trades during news events, stats show high `extreme_volatility_filtered` count

**Cause**: ATR > 3× median triggers filter (protects from news volatility)

**Solutions**:

**Option 1** - Increase threshold (more aggressive):
```json
{
  "VOLATILITY_MULTIPLIER_MAX": 4.0  // Default is 3.0
}
```

**Option 2** - Disable filter entirely (not recommended):
```json
{
  "USE_EXTREME_VOLATILITY_FILTER": false
}
```

**Trade-off**: Higher threshold = more trades during volatile periods = higher risk

**Recommendation**: Keep default (3.0) for best risk/reward balance

## Code Style

- Functions use snake_case
- Global config vars use UPPER_CASE
- DataFrame operations prefer vectorized numpy over loops
- Numba functions marked with `@jit(nopython=True, cache=True)`
- All file paths use forward slashes (cross-platform)
