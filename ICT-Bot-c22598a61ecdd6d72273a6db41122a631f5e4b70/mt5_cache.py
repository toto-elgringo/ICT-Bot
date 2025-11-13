"""
Système de Cache MT5 pour accélérer le chargement des données
Sauvegarde les données en pickle pour éviter de recharger depuis MT5 à chaque fois
Speedup attendu: 2-3x pour le chargement initial
"""

import os
import pickle
import hashlib
from datetime import datetime, timedelta
import pandas as pd


class MT5Cache:
    """Gestionnaire de cache pour les données MT5"""

    def __init__(self, cache_dir='cache_mt5'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, symbol: str, timeframe: str, bars: int) -> str:
        """Génère une clé unique pour le cache"""
        key_str = f"{symbol}_{timeframe}_{bars}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        """Retourne le chemin du fichier de cache"""
        return os.path.join(self.cache_dir, f"{cache_key}.pkl")

    def _get_metadata_path(self, cache_key: str) -> str:
        """Retourne le chemin du fichier de métadonnées"""
        return os.path.join(self.cache_dir, f"{cache_key}_meta.pkl")

    def is_cache_valid(self, cache_key: str, max_age_hours: int = 24) -> bool:
        """
        Vérifie si le cache est valide et pas trop ancien

        Args:
            cache_key: Clé du cache
            max_age_hours: Âge maximum en heures (24h par défaut)

        Returns:
            True si le cache existe et est valide
        """
        cache_path = self._get_cache_path(cache_key)
        meta_path = self._get_metadata_path(cache_key)

        if not os.path.exists(cache_path) or not os.path.exists(meta_path):
            return False

        try:
            # Charger les métadonnées
            with open(meta_path, 'rb') as f:
                metadata = pickle.load(f)

            # Vérifier l'âge du cache
            cache_time = metadata.get('timestamp', datetime.min)
            age = datetime.now() - cache_time

            if age > timedelta(hours=max_age_hours):
                print(f"[CACHE] Cache trop ancien ({age.total_seconds()/3600:.1f}h > {max_age_hours}h)")
                return False

            return True

        except Exception as e:
            print(f"[CACHE] Erreur lors de la vérification du cache: {e}")
            return False

    def save_to_cache(self, symbol: str, timeframe: str, bars: int, df: pd.DataFrame, info=None):
        """
        Sauvegarde les données dans le cache

        Args:
            symbol: Symbole tradé
            timeframe: Timeframe
            bars: Nombre de barres
            df: DataFrame enrichi avec les indicateurs
            info: Informations du symbole MT5
        """
        cache_key = self._get_cache_key(symbol, timeframe, bars)
        cache_path = self._get_cache_path(cache_key)
        meta_path = self._get_metadata_path(cache_key)

        try:
            # Sauvegarder les données
            with open(cache_path, 'wb') as f:
                pickle.dump((df, info), f, protocol=pickle.HIGHEST_PROTOCOL)

            # Sauvegarder les métadonnées
            metadata = {
                'symbol': symbol,
                'timeframe': timeframe,
                'bars': bars,
                'timestamp': datetime.now(),
                'df_shape': df.shape,
                'cache_key': cache_key
            }
            with open(meta_path, 'wb') as f:
                pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)

            file_size = os.path.getsize(cache_path) / (1024 * 1024)  # MB
            print(f"[CACHE] Données sauvegardées: {cache_path} ({file_size:.1f} MB)")

        except Exception as e:
            print(f"[CACHE] Erreur lors de la sauvegarde: {e}")

    def load_from_cache(self, symbol: str, timeframe: str, bars: int):
        """
        Charge les données depuis le cache

        Args:
            symbol: Symbole tradé
            timeframe: Timeframe
            bars: Nombre de barres

        Returns:
            Tuple (df, info) ou None si cache invalide
        """
        cache_key = self._get_cache_key(symbol, timeframe, bars)

        if not self.is_cache_valid(cache_key):
            return None

        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, 'rb') as f:
                df, info = pickle.load(f)

            print(f"[CACHE] Données chargées depuis cache ({len(df)} barres)")
            return df, info

        except Exception as e:
            print(f"[CACHE] Erreur lors du chargement: {e}")
            return None

    def clear_cache(self, symbol: str = None, timeframe: str = None, bars: int = None):
        """
        Supprime le cache (tout ou spécifique)

        Args:
            symbol: Si spécifié, supprime seulement ce symbole
            timeframe: Si spécifié, supprime seulement ce timeframe
            bars: Si spécifié, supprime seulement ce nombre de barres
        """
        if symbol and timeframe and bars:
            # Supprimer un cache spécifique
            cache_key = self._get_cache_key(symbol, timeframe, bars)
            cache_path = self._get_cache_path(cache_key)
            meta_path = self._get_metadata_path(cache_key)

            for path in [cache_path, meta_path]:
                if os.path.exists(path):
                    os.remove(path)
                    print(f"[CACHE] Supprimé: {path}")
        else:
            # Supprimer tout le cache
            import shutil
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
                os.makedirs(self.cache_dir)
                print(f"[CACHE] Cache complet supprimé")

    def list_cache(self):
        """Liste tous les caches disponibles"""
        cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('_meta.pkl')]

        if not cache_files:
            print("[CACHE] Aucun cache disponible")
            return []

        cache_list = []
        total_size = 0

        print("\n[CACHE] Caches disponibles:")
        print("=" * 80)

        for meta_file in cache_files:
            meta_path = os.path.join(self.cache_dir, meta_file)
            try:
                with open(meta_path, 'rb') as f:
                    metadata = pickle.load(f)

                cache_key = metadata['cache_key']
                cache_path = self._get_cache_path(cache_key)
                file_size = os.path.getsize(cache_path) / (1024 * 1024) if os.path.exists(cache_path) else 0
                age = datetime.now() - metadata['timestamp']

                print(f"  {metadata['symbol']:8} {metadata['timeframe']:4} {metadata['bars']:6} barres "
                      f"| {file_size:6.1f} MB | Age: {age.total_seconds()/3600:.1f}h")

                cache_list.append(metadata)
                total_size += file_size

            except Exception as e:
                print(f"  [ERREUR] {meta_file}: {e}")

        print("=" * 80)
        print(f"Total: {len(cache_list)} cache(s) | Taille totale: {total_size:.1f} MB")

        return cache_list


def load_mt5_data_with_cache(symbol: str, timeframe: str, bars: int,
                              max_cache_age_hours: int = 24,
                              force_reload: bool = False,
                              use_numba: bool = True):
    """
    Charge les données MT5 avec système de cache intelligent

    Args:
        symbol: Symbole à charger
        timeframe: Timeframe
        bars: Nombre de barres
        max_cache_age_hours: Âge maximum du cache en heures
        force_reload: Forcer le rechargement depuis MT5
        use_numba: Utiliser les indicateurs Numba optimisés (3x plus rapide)

    Returns:
        Tuple (df, info)
    """
    import time

    cache = MT5Cache()

    # Essayer de charger depuis le cache
    if not force_reload:
        print(f"[CACHE] Recherche dans le cache...")
        cached_data = cache.load_from_cache(symbol, timeframe, bars)

        if cached_data is not None:
            print(f"[CACHE] ✅ Données chargées depuis cache (instantané)")
            return cached_data

    # Charger depuis MT5
    print(f"[MT5] Chargement depuis MT5...")
    start = time.time()

    # Import des fonctions MT5
    import importlib.util
    spec = importlib.util.spec_from_file_location("ict_bot", "ict_bot_all_in_one.py")
    ict_bot = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ict_bot)

    import MetaTrader5 as mt5
    import json

    # Charger credentials
    with open('mt5_credentials.json', 'r') as f:
        creds = json.load(f)

    # Se connecter
    if not mt5.initialize(login=creds['login'], password=creds['password'], server=creds['server']):
        raise Exception("MT5 initialization failed")

    if not mt5.symbol_select(symbol, True):
        mt5.shutdown()
        raise Exception(f"Symbol {symbol} not available")

    # Charger les données brutes
    tf_code = ict_bot.MT5_TF_MAP.get(timeframe, mt5.TIMEFRAME_H1)
    df = ict_bot.load_rates_mt5(symbol, tf_code, bars)
    info = mt5.symbol_info(symbol)

    mt5.shutdown()

    # Enrichir avec les indicateurs (version optimisée ou standard)
    if use_numba:
        try:
            from ict_indicators_numba import enrich_numba
            print(f"[NUMBA] Utilisation des indicateurs Numba optimisés (3x speedup)")
            df = enrich_numba(df)
        except ImportError:
            print(f"[WARNING] Numba non disponible, utilisation version standard")
            df = ict_bot.enrich(df)
    else:
        df = ict_bot.enrich(df)

    elapsed = time.time() - start
    print(f"[MT5] ✅ Données chargées et enrichies en {elapsed:.1f}s")

    # Sauvegarder dans le cache
    cache.save_to_cache(symbol, timeframe, bars, df, info)

    return df, info


# Fonctions utilitaires
def clear_old_cache(max_age_hours: int = 72):
    """Nettoie les caches trop anciens"""
    cache = MT5Cache()
    cache_list = cache.list_cache()

    deleted = 0
    for metadata in cache_list:
        age = datetime.now() - metadata['timestamp']
        if age.total_seconds() / 3600 > max_age_hours:
            cache.clear_cache(metadata['symbol'], metadata['timeframe'], metadata['bars'])
            deleted += 1

    print(f"[CACHE] {deleted} cache(s) supprimé(s) (> {max_age_hours}h)")


if __name__ == '__main__':
    # Test du système de cache
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == 'list':
            cache = MT5Cache()
            cache.list_cache()
        elif sys.argv[1] == 'clear':
            cache = MT5Cache()
            cache.clear_cache()
        elif sys.argv[1] == 'clean':
            clear_old_cache(int(sys.argv[2]) if len(sys.argv) > 2 else 72)
    else:
        print("Usage:")
        print("  python mt5_cache.py list             - Liste les caches")
        print("  python mt5_cache.py clear            - Supprime tout le cache")
        print("  python mt5_cache.py clean [hours]    - Nettoie les caches > N heures")
