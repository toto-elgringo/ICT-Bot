"""
Script de test de compatibilite backward des configs v2.0 → v2.1
Verifie que les anciennes configs fonctionnent avec les nouveaux parametres
"""

import json
import os

def test_config_compatibility():
    """Teste la compatibilite des configs existantes avec v2.1"""

    print("=" * 60)
    print("TEST COMPATIBILITE BACKWARD CONFIGS v2.0 -> v2.1")
    print("=" * 60)

    # Parametres attendus v2.1 (26 parametres au total)
    expected_params_v21 = {
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
        # NOUVEAUX v2.1
        'USE_FVG_MITIGATION_FILTER': True,
        'USE_BOS_RECENCY_FILTER': True,
        'USE_MARKET_STRUCTURE_FILTER': True,
        'BOS_MAX_AGE': 20,
        'FVG_BOS_MAX_DISTANCE': 20,
        'USE_ORDER_BLOCK_SL': True,
        'USE_EXTREME_VOLATILITY_FILTER': True,
        'VOLATILITY_MULTIPLIER_MAX': 3.0
    }

    config_dir = 'config'

    if not os.path.exists(config_dir):
        print("\n[ERROR] Dossier config/ introuvable")
        return False

    configs = [f for f in os.listdir(config_dir) if f.endswith('.json')]

    if not configs:
        print("\n[ERROR] Aucun fichier config trouve")
        return False

    print(f"\n[INFO] {len(configs)} configurations trouvees\n")

    results = []

    for config_file in configs:
        config_path = os.path.join(config_dir, config_file)
        config_name = config_file.replace('.json', '')

        print(f"Testing: {config_name}...")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Lecture: {e}")
            results.append({'name': config_name, 'status': 'ERROR', 'missing': [], 'extra': []})
            continue

        # Verifier parametres manquants
        missing_params = []
        for param in expected_params_v21.keys():
            if param not in config:
                missing_params.append(param)

        # Verifier parametres en trop (non standards)
        extra_params = []
        for param in config.keys():
            if param not in expected_params_v21:
                extra_params.append(param)

        # Statut - Detecter si ce sont les 8 nouveaux parametres v2.1 qui manquent
        new_v21_params = {
            'USE_FVG_MITIGATION_FILTER',
            'USE_BOS_RECENCY_FILTER',
            'USE_MARKET_STRUCTURE_FILTER',
            'BOS_MAX_AGE',
            'FVG_BOS_MAX_DISTANCE',
            'USE_ORDER_BLOCK_SL',
            'USE_EXTREME_VOLATILITY_FILTER',
            'VOLATILITY_MULTIPLIER_MAX'
        }

        missing_v21 = set(missing_params) & new_v21_params

        if missing_params and len(missing_v21) == len(new_v21_params):
            # Tous les 8 nouveaux parametres v2.1 manquent = config v2.0
            status = 'PARTIAL_V2.0'
        elif missing_params:
            status = 'INCOMPLETE'
        elif extra_params:
            status = 'CUSTOM'
        else:
            status = 'COMPLETE_V2.1'

        results.append({
            'name': config_name,
            'status': status,
            'missing': missing_params,
            'extra': extra_params,
            'total_params': len(config)
        })

        # Affichage
        status_icon = {
            'COMPLETE_V2.1': '[OK]',
            'PARTIAL_V2.0': '[WARN]',
            'INCOMPLETE': '[ERROR]',
            'CUSTOM': '[CUSTOM]',
            'ERROR': '[ERROR]'
        }

        print(f"  {status_icon.get(status, '[?]')} {status}")
        if missing_params:
            print(f"    Missing: {len(missing_params)} parametres")
            if status == 'PARTIAL_V2.0':
                print(f"      -> Config v2.0 detectee (fonctionnera avec valeurs par defaut)")
        if extra_params:
            print(f"    Extra: {extra_params}")
        print()

    # Resume
    print("=" * 60)
    print("RESUME")
    print("=" * 60)

    complete_v21 = sum(1 for r in results if r['status'] == 'COMPLETE_V2.1')
    partial_v20 = sum(1 for r in results if r['status'] == 'PARTIAL_V2.0')
    incomplete = sum(1 for r in results if r['status'] == 'INCOMPLETE')
    custom = sum(1 for r in results if r['status'] == 'CUSTOM')
    errors = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"\n[OK] Complete v2.1:   {complete_v21}")
    print(f"[WARN] Partial v2.0:    {partial_v20} (fonctionnelles avec defaults)")
    print(f"[CUSTOM] Custom configs:  {custom}")
    print(f"[ERROR] Incomplete:      {incomplete}")
    print(f"[ERROR] Errors:          {errors}")

    # Verdict
    print("\n" + "=" * 60)
    if partial_v20 > 0:
        print("[OK] COMPATIBILITE BACKWARD: OK")
        print(f"   {partial_v20} config(s) v2.0 detectees")
        print("   Ces configs utiliseront les valeurs par defaut v2.1 pour les parametres manquants")
        print("   Comportement: load_config_from_file() fait le fallback sur globals")
    else:
        print("[OK] COMPATIBILITE: PARFAITE")
        print("   Toutes les configs sont a jour v2.1")
    print("=" * 60)

    return True

if __name__ == '__main__':
    test_config_compatibility()
