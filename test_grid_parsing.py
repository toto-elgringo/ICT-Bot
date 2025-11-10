"""
Test de parsing des resultats de backtest pour le grid search
"""

# Simuler une sortie de backtest RÉELLE (format actuel avec 2 lignes)
test_output = """
[*] Utilisation de 500 barres pour H4 (~6 mois)
[*] Chargement de 500 barres depuis MT5...
[OK] 500 barres chargees
[*] Periode : 2025-07-16 -> 2025-11-10
[*] Duree : 117 jours (3.9 mois)
[ML] Meta-labelling: False
[ML] Modele entraine: False
[ML] Samples: 0
[!] Circuit breaker active le 2025-09-16 : DD journalier -29.29%

=== STATISTIQUES DE FILTRAGE ===
Barres analysees: 450
|- Cooldown: 2
|- Kill zones: 307
|- Pas de FVG: 70
|- Biais neutre: 57
|- FVG/Biais incompatibles: 8
|- Filtrees par ML: 0
|- SL trop proche: 0
|- Max trades atteint: 2
|- Filtrees par ATR: 0
|- Circuit breaker: 1
'- Entrees validees: 1

=== METRICS (EURUSD H4) ===
Trades: 1 | Winrate: 0.0% | PnL: -2928.94 | MaxDD: -29.29% | Equity finale: 7071.06
[SAVE] Resultats: backtest/backtest_EURUSD_H4_20251110_063646.json
"""

# Tester le parsing (nouveau code)
results = {
    'total_trades': 0,
    'win_rate': 0.0,
    'pnl_pct': 0.0,
    'max_drawdown_pct': 0.0,
}

lines = test_output.split('\n')
for i, line in enumerate(lines):
    # Chercher la ligne avec les donnees (pas le header)
    if 'Trades:' in line and 'Winrate:' in line and 'PnL:' in line:
        print(f"Ligne trouvee: {line}")
        try:
            # Extraire Trades
            trades_part = line.split('Trades:')[1].split('|')[0].strip()
            results['total_trades'] = int(trades_part)
            print(f"  Trades: {results['total_trades']}")

            # Extraire Winrate
            winrate_part = line.split('Winrate:')[1].split('%')[0].strip()
            results['win_rate'] = float(winrate_part)
            print(f"  Winrate: {results['win_rate']}%")

            # Extraire PnL
            pnl_part = line.split('PnL:')[1].split('|')[0].strip()
            pnl_value = float(pnl_part)
            results['pnl_pct'] = (pnl_value / 10000.0) * 100.0
            print(f"  PnL: {pnl_value} -> {results['pnl_pct']:.2f}%")

            # Extraire MaxDD
            dd_part = line.split('MaxDD:')[1].split('%')[0].strip()
            results['max_drawdown_pct'] = float(dd_part)
            print(f"  MaxDD: {results['max_drawdown_pct']}%")

        except Exception as e:
            print(f"  ERREUR: {e}")
        break

print(f"\nResultats finaux:")
print(f"  Trades: {results['total_trades']}")
print(f"  Win Rate: {results['win_rate']}%")
print(f"  PnL: {results['pnl_pct']:.2f}%")
print(f"  Max DD: {results['max_drawdown_pct']}%")
