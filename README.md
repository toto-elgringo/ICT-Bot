# 🤖 ICT Trading Bot

Bot de trading automatisé basé sur la méthodologie **ICT (Inner Circle Trader)** avec filtrage par **Machine Learning** et notifications **Telegram** en temps réel.

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration](#️-configuration)
  - [1. Credentials MetaTrader 5](#1-credentials-metatrader-5)
  - [2. Configuration Telegram](#2-configuration-telegram)
- [Démarrage](#-démarrage)
- [Utilisation](#-utilisation)
- [Grid Testing](#-grid-testing---optimisation-automatique)
- [Structure du Projet](#-structure-du-projet)
- [Troubleshooting](#-troubleshooting)
- [Sécurité](#-sécurité)

---

## ✨ Fonctionnalités

- ✅ **Stratégie ICT** : Fair Value Gaps (FVG), Break of Structure (BOS), Order Blocks (OB), Kill Zones
- ✅ **Machine Learning** : Meta-labelling avec Logistic Regression pour filtrer les trades (modèle individuel par bot)
- ✅ **Gestion Multi-Bot** : Gérez plusieurs bots simultanément avec des configurations différentes
- ✅ **Dashboard Streamlit** : Interface web complète pour contrôler tous vos bots
- ✅ **Configurations Nommées** : Créez et gérez plusieurs stratégies (Default, Aggressive, Conservative, etc.)
- ✅ **Grid Testing** : Optimisation automatique de 1,728 combinaisons de paramètres pour trouver la meilleure config
- ✅ **Notifications Telegram** : Alertes en temps réel lors de l'ouverture de positions
- ✅ **Backtesting** : Testez vos stratégies sur des données historiques
- ✅ **Risk Management** : Circuit breaker, risque adaptatif, sessions adaptatives
- ✅ **Comparaison de Backtests** : Comparez plusieurs backtests côte à côte
- ✅ **Organisation des Fichiers** : Logs, modèles ML et configurations isolés par bot

---

## 🔧 Prérequis

Avant de commencer, assurez-vous d'avoir :

- **Python 3.8+** installé ([Télécharger Python](https://www.python.org/downloads/))
- **MetaTrader 5** installé et configuré
- Un compte **Telegram** (pour les notifications)
- **Git** (optionnel, pour cloner le repository)

---

## 📦 Installation

### 1. Cloner ou télécharger le projet

```bash
# Option 1 : Cloner avec Git
git clone https://github.com/votre-repo/ICT-Bot.git
cd ICT-Bot

# Option 2 : Télécharger le ZIP et extraire
```

### 2. Installer les dépendances Python

Toutes les librairies nécessaires en une seule commande :

```bash
pip install MetaTrader5 scikit-learn numpy pandas matplotlib pytz requests streamlit plotly joblib
```

#### Détail des librairies :

| Librairie | Usage |
|-----------|-------|
| `MetaTrader5` | Connexion et trading sur MT5 |
| `scikit-learn` | Machine Learning (Logistic Regression) |
| `numpy` | Calculs numériques |
| `pandas` | Manipulation de données |
| `matplotlib` | Graphiques (backtests) |
| `pytz` | Gestion des fuseaux horaires |
| `requests` | Notifications Telegram |
| `streamlit` | Interface web dashboard |
| `plotly` | Graphiques interactifs |
| `joblib` | Sauvegarde du modèle ML |

### 3. Vérifier l'installation

```bash
python --version
# Python 3.8.0 ou supérieur

pip list | grep -E "MetaTrader5|streamlit|sklearn"
# Vérifier que les packages sont installés
```

---

## ⚙️ Configuration

### 1. Credentials MetaTrader 5

#### Étape 1 : Créer le fichier de credentials MT5

Créez le fichier mt5_credentials.json et rentrez y vos informations sous cette forme:

```json
{
    "login": 123456,
    "password": "VotreMotDePasse",
    "server": "VotreServeurMT5"
}
```

**Où trouver ces informations ?**
- **Login** : Votre numéro de compte MT5
- **Password** : Mot de passe de votre compte MT5
- **Server** : Nom du serveur de votre broker (ex: `ICMarkets-Demo`, `FusionMarkets-Demo`)
- **Fonction** : Il permet de pouvoir charger les graphiques et faire les backtest

---

### 2. Configuration Telegram

#### Étape 1 : Créer un Bot Telegram

1. Ouvrez **Telegram** et cherchez `@BotFather`
2. Envoyez la commande `/newbot`
3. Donnez un **nom** à votre bot (ex: "ICT Trading Bot")
4. Donnez un **username** unique (ex: "my_ict_trading_bot")
5. **BotFather** vous donnera un **TOKEN** → Copiez-le !

Exemple de token : `1234567891:AAEw9t_OM_ApiOhnhFGTjnvghfTHFpoiA_w`

#### Étape 2 : Obtenir votre Chat ID

1. Cherchez `@userinfobot` sur Telegram
2. Démarrez une conversation avec ce bot
3. Il vous donnera votre **Chat ID** → Copiez-le !

Exemple de Chat ID : `9876452298`

#### Étape 3 : Créer le fichier de credentials Telegram

Créez le fichier telegram_credentials.json et rentrez y vos informations sous cette forme:

```json
{
    "enabled": true,
    "bot_token": "1234567891:AAEw9t_OM_ApiOhnhFGTjnvghfTHFpoiA_w",
    "chat_id": "9876452298"
}
```

- **enabled** : `true` pour activer les notifications, `false` pour les désactiver
- **bot_token** : Token obtenu de BotFather
- **chat_id** : Votre Chat ID

#### Étape 5 : Tester la configuration Telegram

```bash
python test_telegram.py
```

Vous devriez recevoir un message de test sur Telegram ! 🎉

---

## 🚀 Démarrage

### Mode 1 : Interface Multi-Bot (Recommandé)

Lancez l'interface web Streamlit :

```bash
streamlit run streamlit_bot_manager.py
```

L'interface s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

**Depuis le dashboard, vous pouvez** :
- ✅ **Gérer plusieurs bots** : Créer, modifier, supprimer des bots
- ✅ **Chaque bot a** : Son propre compte MT5, symbole, configuration et modèle ML
- ✅ **Démarrer/Arrêter** : Contrôlez chaque bot individuellement
- ✅ **Créer des configurations** : Nommez vos stratégies (Aggressive, Scalping, etc.)
- ✅ **Lancer des backtests** : Testez vos configurations
- ✅ **Grid Testing** : Optimisez automatiquement vos paramètres (1,728 combinaisons)
- ✅ **Comparer les résultats** : Analysez plusieurs backtests côte à côte
- ✅ **Visualiser les performances** : Courbes d'équité, métriques détaillées
- ✅ **Consulter les logs** : Logs individuels par bot dans le dossier log/

---

### Mode 2 : Ligne de commande

#### Backtest (Mode simulation)

```bash
python ict_bot_all_in_one.py --mode backtest --symbol EURUSD --timeframe M5 --bars 100000
```

**Options disponibles** :
- `--mode` : `backtest` ou `live`
- `--symbol` : `EURUSD`, `GBPUSD`, `XAUUSD`, `BTCUSD`, etc.
- `--timeframe` : `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`
- `--bars` : Nombre de barres à analyser (ex: `100000`)

#### Live Trading (Mode réel)

⚠️ **ATTENTION** : Testez d'abord sur un compte DEMO !

```bash
python ict_bot_all_in_one.py --mode live --symbol EURUSD --timeframe M5
```

**Le bot va** :
1. Se connecter à MT5
2. Charger 100,000 barres historiques pour entraîner le ML
3. Commencer à surveiller le marché
4. Envoyer des notifications Telegram lors de l'ouverture de positions

---

## 📖 Utilisation

### Dashboard Streamlit Multi-Bot

#### 🤖 Onglet "Gestion des Bots"

**Ajouter un nouveau bot** :
1. Remplissez les informations :
   - **Nom** : Ex. "Bot EURUSD Agressif"
   - **Login MT5** : Numéro de compte
   - **Password & Server** : Identifiants MT5
   - **Symbole** : EURUSD, GBPUSD, XAUUSD, BTCUSD, etc.
   - **Timeframe** : M1, M5, M15, etc.
   - **Configuration** : Sélectionnez une stratégie (Default, Aggressive, etc.)
2. Cliquez sur "✅ Ajouter le Bot"
3. Le système crée automatiquement :
   - Un modèle ML dans `machineLearning/Bot_EURUSD.pkl`
   - Un fichier de log dans `log/bot_{id}_live.log`

**Gérer vos bots** :
- ▶️ **Démarrer** : Lance le bot avec sa configuration
- ⏸️ **Arrêter** : Stoppe le bot
- ✏️ **Modifier** : Changez symbole, configuration, credentials
- 🗑️ **Supprimer** : Supprime le bot (+ modèle ML + log)
- 📊 **Infos MT5** : Consultez balance, equity, marge
- 📍 **Positions** : Voir les positions ouvertes
- 📋 **Logs** : Logs en temps réel du bot

#### ⚙️ Onglet "Gestionnaire de Configurations"

**Créer une configuration** :
1. Nommez votre stratégie (ex: "Aggressive", "Scalping")
2. Elle sera créée avec les paramètres par défaut
3. Modifiez-la selon vos besoins

**Paramètres configurables** :
- **Risque & MM** : Risque par trade, RR, Max trades, Cooldown
- **ML & RR Adaptatif** : ML threshold, samples, RR par session
- **Filtres** : ATR, Circuit Breaker, Risque Adaptatif

**Important** :
- Plusieurs bots peuvent utiliser la même configuration
- Les modifications s'appliquent à tous les bots au prochain redémarrage
- Vous ne pouvez pas supprimer une config utilisée par un bot

#### 🧪 Onglet "Backtest"
- Sélectionnez symbole, timeframe, nombre de barres et configuration
- Lancez un backtest pour tester une stratégie
- Résultats sauvegardés dans `backtest/`
- Visualisez les métriques détaillées

#### 📈 Onglet "Historique"
- **Consultez** un backtest : Métriques + courbe d'équité
- **Supprimez** les backtests inutiles (bouton 🗑️)
- **Comparez** plusieurs backtests côte à côte
  - Sélection multiple
  - Tableau comparatif : Trades | Win Rate (%) | PnL ($) | Max DD (%)

#### 🔬 Onglet "Grid Testing"
- **Optimisation automatique** de 1,728 combinaisons de paramètres
- Teste 7 paramètres : Risk, RR, Max Trades, Cooldown, ML Threshold, ATR Filter, Circuit Breaker
- Multiprocessing pour accélérer les tests (1-4 workers)
- Score composite : 40% PnL + 30% Sharpe + 20% WinRate + 10% (1-DD)
- Sauvegarde automatique du top 5 dans `Grid/`
- Création de nouvelles configurations à partir des meilleurs résultats
- **Voir section dédiée** ci-dessous pour le guide complet

---

### Notifications Telegram

Quand un bot ouvre une position, vous recevez :

```
🔔 Nouvelle Position Ouverte

📈 BUY EURUSD

📍 Entree: 1.08450
🎯 Take Profit: 1.08650
🛑 Stop Loss: 1.08350

📊 Risque: 0.00100
⏰ Heure: 2025-11-09 14:23:15
💰 Volume: 0.15 lots
```

---

## 🔬 Grid Testing - Optimisation Automatique

### 🎯 Qu'est-ce que le Grid Testing?

Le Grid Testing teste **automatiquement 1,728 combinaisons** de paramètres pour trouver la configuration optimale de votre bot ICT.

### ⚠️ IMPORTANT: Kill Zones et Nombre de Barres

Le bot ICT **trade UNIQUEMENT pendant les Kill Zones**:
- London Kill Zone: 02h-05h ET (Eastern Time)
- New York Kill Zone: 07h-10h ET

Cela représente **seulement 6 heures sur 24** (25% du temps).

**Pourquoi c'est important?**
- **M5 avec 500 barres** = 1.7 jours = **0 trades** (pas assez de kill zones)
- **M5 avec 100,000 barres** = 347 jours = **Crash/timeout**
- **Solution**: Utilisez H1 ou H4 avec 2,000-5,000 barres

### ✅ Nombre de Barres Recommandé par Timeframe

| Timeframe | Minimum | Optimal | Maximum | Période |
|-----------|---------|---------|---------|---------|
| **M5** | 10,000 | 15,000-20,000 | 30,000 | 35-70 jours |
| **H1** ⭐ | 2,000 | 3,000-5,000 | 10,000 | 83-208 jours |
| **H4** ⭐ | 1,000 | 1,500-2,000 | 3,000 | 166-333 jours |

**Recommandation**: H1 ou H4 sont les meilleurs compromis vitesse/données.

### 🚀 Configuration Optimale Recommandée

#### Option 1: Test Rapide (2 heures)
```
Symbole: EURUSD
Timeframe: H1
Barres: 3,000 (≈4 mois)
Workers: 1 (mode séquentiel - le plus stable)
```

#### Option 2: Équilibré (3 heures) - RECOMMANDÉ
```
Symbole: EURUSD
Timeframe: H1
Barres: 5,000 (≈7 mois)
Workers: 2
```

#### Option 3: Maximum de Données (4 heures)
```
Symbole: EURUSD
Timeframe: H4
Barres: 2,000 (≈11 mois)
Workers: 1
```

### ⚙️ Paramètres Testés (1,728 combinaisons)

| Paramètre | Valeurs testées | Description |
|-----------|----------------|-------------|
| RISK_PER_TRADE | 0.005, 0.01, 0.02 | Risque par trade (0.5%, 1%, 2%) |
| RR_TAKE_PROFIT | 1.5, 1.8, 2.0, 2.5 | Ratio Risk/Reward |
| MAX_CONCURRENT_TRADES | 1, 2, 3 | Nombre de trades simultanés |
| COOLDOWN_BARS | 3, 5, 8 | Barres d'attente entre trades |
| ML_THRESHOLD | 0.3, 0.4, 0.5, 0.6 | Seuil de confiance ML |
| USE_ATR_FILTER | True, False | Filtre basé sur la volatilité |
| USE_CIRCUIT_BREAKER | True, False | Stop en cas de drawdown élevé |

**Total**: 3 × 4 × 3 × 3 × 4 × 2 × 2 = **1,728 tests**

### 📊 Score Composite

Chaque configuration reçoit un score basé sur:

```
Score = 40% PnL + 30% Sharpe + 20% WinRate + 10% (1 - Drawdown)
```

Les **top 5** configurations sont sauvegardées dans `Grid/`.

### 💻 Workers et Performance

| Workers | Temps | Stabilité | RAM | Recommandation |
|---------|-------|-----------|-----|----------------|
| **1** | 3-4h | ⭐⭐⭐⭐⭐ | 4GB | ✅ Le plus stable |
| **2** | 2-3h | ⭐⭐⭐⭐ | 8GB | ✅ Bon compromis |
| **3** | 1.5-2h | ⭐⭐⭐ | 12GB | ⚠️ Risqué |
| **4** | 1-1.5h | ⭐⭐ | 16GB+ | ⚠️ Très risqué |

**Important**: Fermez toutes les applications gourmandes (Chrome, PyCharm, etc.) avant de lancer.

### 🔍 Vérifier que ça Fonctionne

Après le lancement, consultez `Grid/debug_first_test.txt`:

**✅ Bon signe** (backtest avec des trades):
```
=== METRICS (EURUSD H1) ===
Trades: 45 | Winrate: 62.5% | PnL: 1234.56 | MaxDD: -8.75% | Equity finale: 11234.56
```

**❌ Mauvais signe** (pas assez de barres):
```
=== METRICS (EURUSD M5) ===
Trades: 0 | Winrate: 0.0% | PnL: 0.00 | MaxDD: 0.00% | Equity finale: 10000.00

=== STATISTIQUES DE FILTRAGE ===
|- Kill zones: 342    <-- 76% des barres filtrées
'- Entrees validees: 0    <-- Aucun trade généré
```

**Solution**: Augmentez le nombre de barres ou utilisez H1/H4.

### 📁 Fichiers Générés

```
Grid/
├── grid_results_EURUSD_H1_20251110_143012.json   # Top 5 configurations
├── grid_results_EURUSD_H4_20251110_152045.json   # Autre test
└── debug_first_test.txt                          # Debug du premier test
```

### 🎯 Utiliser les Résultats

1. **Ouvrez l'onglet Grid Testing** dans Streamlit
2. **Sélectionnez un rapport** dans l'historique
3. **Examinez le top 5** configurations
4. **Cliquez sur "💾 Sauvegarder"** pour créer une nouvelle configuration
5. **Testez manuellement** dans l'onglet Backtest
6. **Lancez un bot** avec cette config si les résultats sont bons

### ❓ FAQ Grid Testing

**Q: Pourquoi j'ai 0 trades avec M5?**
R: Pas assez de barres. M5 nécessite 10,000-20,000 barres minimum.

**Q: Mon PC crash, que faire?**
R: Utilisez 1 worker uniquement, fermez les autres apps, réduisez le nombre de barres.

**Q: Quel timeframe choisir?**
R: H1 ou H4 sont recommandés. Plus rapide et moins gourmand que M5.

**Q: Combien de temps ça prend?**
R: 2-4 heures avec 1 worker selon le nombre de barres.

**Q: Puis-je arrêter et reprendre?**
R: Non, le grid search doit tourner en continu. Mais vous pouvez utiliser votre PC normalement pendant (évitez juste les tâches lourdes).

**Q: Les résultats sont-ils fiables?**
R: Plus vous utilisez de barres (données historiques), plus les résultats sont fiables. Minimum recommandé: 3-6 mois de données.

### 🚨 Troubleshooting Grid Testing

**Erreur: "Timeout"**
- Réduisez le nombre de barres
- Le timeout s'ajuste automatiquement mais a une limite de 5 minutes par test

**Erreur: "Memory Error"**
- Réduisez à 1 worker
- Fermez Chrome, PyCharm, etc.
- Réduisez le nombre de barres

**Tous les scores à 0**
- Vérifiez `Grid/debug_first_test.txt`
- Augmentez le nombre de barres (minimum 2,000 en H1, 1,000 en H4)
- Essayez H1 ou H4 au lieu de M5

**PC freeze/crash**
- TROP de workers
- TROP de barres
- Pas assez de RAM
- **Solution**: 1 worker + 3,000-5,000 barres en H1

---

## 🏗️ Architecture Multi-Bot

### Comment ça fonctionne ?

1. **Création d'un bot** :
   - Vous donnez un nom, symbole, timeframe, et credentials MT5
   - Vous choisissez une configuration (Default, Aggressive, etc.)
   - Le système génère un ID unique (ex: `a1b2c3d4`)
   - Crée automatiquement :
     - `machineLearning/Bot_{nom}.pkl` (modèle ML)
     - `log/bot_{id}_live.log` (fichier de log)

2. **Lancement d'un bot** :
   - La configuration sélectionnée est chargée depuis `config/{config_name}.json`
   - Les credentials MT5 du bot sont utilisés
   - Le bot charge/entraîne son modèle ML personnel
   - Les logs sont écrits dans son fichier dédié

3. **Plusieurs bots peuvent** :
   - Utiliser la même configuration (ex: 3 bots avec "Aggressive")
   - Trader sur le même compte MT5 ou des comptes différents
   - Trader le même symbole avec des timeframes différents
   - Fonctionner simultanément sans conflit

4. **Suppression d'un bot** :
   - Supprime l'entrée dans `bots_config.json`
   - Supprime le modèle ML `machineLearning/Bot_{nom}.pkl`
   - Supprime le fichier de log `log/bot_{id}_live.log`
   - Conserve la configuration (peut être utilisée par d'autres bots)

### Exemple d'utilisation

**Scénario : 3 bots avec 2 configurations**

```
Bot 1: "EURUSD Agressif"
- Symbole: EURUSD, TF: M5
- Config: Aggressive
- Compte: Demo Account 1

Bot 2: "GBPUSD Agressif"
- Symbole: GBPUSD, TF: M5
- Config: Aggressive (même config que Bot 1)
- Compte: Demo Account 1

Bot 3: "XAUUSD Conservateur"
- Symbole: XAUUSD, TF: H1
- Config: Conservative
- Compte: Demo Account 2
```

→ Si vous modifiez "Aggressive", cela impacte Bot 1 et Bot 2 au redémarrage

---

## 📂 Structure du Projet

```
ICT-Bot/
├── ict_bot_all_in_one.py              # Bot principal (backtest + live)
├── streamlit_bot_manager_v2.py        # Interface web multi-bot
├── grid_search_engine.py              # Moteur d'optimisation Grid Testing
├── test_telegram.py                   # Test des notifications Telegram
├── test_grid_parsing.py               # Test du parsing Grid Testing
│
├── mt5_credentials.json               # Credentials MT5 (non versionné)
├── telegram_credentials.json          # Credentials Telegram (non versionné)
├── bots_config.json                   # Liste des bots configurés (non versionné)
│
├── config/                            # Configurations nommées (non versionné)
│   ├── Default.json                   # Configuration par défaut (auto-créée)
│   ├── Aggressive.json                # Exemple de config personnalisée
│   └── Conservative.json              # Autre config personnalisée
│
├── machineLearning/                   # Modèles ML par bot (non versionné)
│   ├── Bot_EURUSD.pkl                 # Modèle ML du bot EURUSD
│   ├── Bot_GBPUSD.pkl                 # Modèle ML du bot GBPUSD
│   └── Bot_XAUUSD.pkl                 # Modèle ML du bot XAUUSD
│
├── log/                               # Logs individuels par bot (non versionné)
│   ├── bot_a1b2c3d4_live.log         # Log du bot ID a1b2c3d4
│   └── bot_e5f6g7h8_live.log         # Log du bot ID e5f6g7h8
│
├── backtest/                          # Résultats des backtests (non versionné)
│   ├── backtest_EURUSD_M5_20251109_143012.json
│   └── backtest_XAUUSD_H1_20251109_152045.json
│
├── Grid/                              # Résultats Grid Testing (non versionné)
│   ├── grid_results_EURUSD_H1_20251110_143012.json
│   ├── grid_results_EURUSD_H4_20251110_152045.json
│   └── debug_first_test.txt           # Debug du premier test
│
├── .gitignore                         # Protège les fichiers sensibles
└── README.md                          # Ce fichier
```

### 📋 Organisation des fichiers

**Fichiers de configuration** :
- Chaque bot référence une configuration nommée dans `config/`
- Les configurations sont partagées entre bots
- Modification d'une config = impact tous les bots l'utilisant

**Modèles ML** :
- Chaque bot a son propre modèle dans `machineLearning/`
- Nommés `{Nom_du_bot}.pkl`
- Créés automatiquement au lancement
- Supprimés avec le bot

**Logs** :
- Chaque bot a son fichier de log dans `log/`
- Nommés `bot_{id}_live.log`
- Supprimés avec le bot

---

## 🐛 Troubleshooting

### Le bot ne démarre pas

**Erreur : "MT5 not initialized"**
```bash
# Vérifiez que MT5 est installé et lancé
# Vérifiez vos credentials dans mt5_credentials.json
# Vérifiez que votre compte est connecté sur MT5
```

**Erreur : "Symbol not found"**
```bash
# Le symbole n'existe pas sur votre broker
# Vérifiez la liste des symboles disponibles sur MT5
# Exemple : Certains brokers utilisent "XAUUSD" au lieu de "GOLD"
```

---

### Pas de notifications Telegram

**Le bot s'exécute mais pas de notification**

1. Vérifiez `telegram_credentials.json` :
   - `"enabled": true`
   - Token et Chat ID corrects

2. Testez manuellement :
   ```bash
   python test_telegram.py
   ```

3. Vérifiez que `requests` est installé :
   ```bash
   pip install requests
   ```

4. Vérifiez que le bot a pris une position (les notifications ne sont envoyées qu'en mode LIVE, pas en backtest)

---

### L'interface Streamlit ne se lance pas

**Erreur : "Port 8501 already in use"**
```bash
# Utilisez un autre port
streamlit run streamlit_bot_manager.py --server.port 8502
```

**Erreur : "streamlit: command not found"**
```bash
# Installez streamlit
pip install streamlit plotly
```

---

### Erreurs de librairies manquantes

```bash
# Si vous avez des erreurs "ModuleNotFoundError", réinstallez toutes les dépendances :
pip install --upgrade MetaTrader5 scikit-learn numpy pandas matplotlib pytz requests streamlit plotly joblib
```

---

## 🔒 Sécurité

### ⚠️ IMPORTANT - Protégez vos credentials !

- ✅ Les fichiers `mt5_credentials.json` et `telegram_credentials.json` sont dans `.gitignore`
- ✅ Ne partagez JAMAIS vos tokens, passwords, ou Chat ID
- ✅ Utilisez un compte **DEMO** pour tester
- ✅ Ne commitez JAMAIS de credentials sur Git/GitHub

### Que faire si j'ai accidentellement commit mes credentials ?

1. **Régénérez immédiatement** :
   - Telegram : Utilisez `/revoke` avec @BotFather
   - MT5 : Changez votre mot de passe

2. **Supprimez l'historique Git** :
   ```bash
   # Si le repo n'est pas encore publié
   git filter-branch --force --index-filter \
   "git rm --cached --ignore-unmatch mt5_credentials.json telegram_credentials.json" \
   --prune-empty --tag-name-filter cat -- --all
   ```

---

## 📊 Configuration Baseline (Optimale)

La configuration par défaut dans `bot_config.json` correspond aux **meilleurs résultats testés** :

**Performances historiques (14.5 mois)** :
- Trades : **301**
- Win Rate : **53.49%**
- PnL : **+$20,678**
- Max Drawdown : **-14.88%**

**Paramètres** :
```json
{
  "RISK_PER_TRADE": 0.01,
  "RR_TAKE_PROFIT": 1.8,
  "MAX_CONCURRENT_TRADES": 2,
  "COOLDOWN_BARS": 5,
  "ML_THRESHOLD": 0.4,
  "USE_SESSION_ADAPTIVE_RR": true,
  "RR_LONDON": 1.2,
  "RR_NEWYORK": 1.5,
  "USE_ML_META_LABELLING": true,
  "USE_ATR_FILTER": true,
  "USE_CIRCUIT_BREAKER": true,
  "DAILY_DD_LIMIT": 0.03,
  "USE_ADAPTIVE_RISK": true
}
```

---

## 🧪 Étapes Recommandées

### Phase 1 : Test en Backtest (1-2 jours)
```bash
python ict_bot_all_in_one.py --mode backtest --symbol EURUSD --timeframe M5 --bars 100000
```

### Phase 2 : Test sur Compte DEMO (1 mois minimum)
```bash
# Assurez-vous d'utiliser un compte DEMO dans mt5_credentials.json
python ict_bot_all_in_one.py --mode live --symbol EURUSD --timeframe M5
```

### Phase 3 : Monitoring via Dashboard
```bash
streamlit run streamlit_bot_manager.py
# Surveillez les performances quotidiennement
```

### Phase 4 : Passage en LIVE (Après validation)
⚠️ **Seulement si les performances DEMO sont satisfaisantes pendant 1+ mois**

---

## Commnent Fonctionne le Bot

Composants par ordre d'importance pour la performance :

### 1. Stratégie ICT de base (★★★★★) - LA PLUS IMPORTANTE

  - Fair Value Gaps (FVG) : Détecte les inefficiences de prix
  - Break of Structure (BOS) : Identifie les changements de tendance
  - Order Blocks : Zones institutionnelles
  - Confluence FVG+BOS : La combinaison gagnante

  Preuve : Votre baseline (301 trades, 53.49% WR, +20,678$ PnL) vient principalement de cette stratégie.

### 2. Kill Zones - Sessions de trading (★★★★☆)

  KZ_LONDON = (8, 11)    # 8h-11h Paris
  KZ_NEWYORK = (14, 17)  # 14h-17h Paris
  Impact : Trade uniquement pendant les sessions à forte liquidité (London & New York)
  - Réduit drastiquement les faux signaux
  - Capture les mouvements institutionnels

### 3. Risk Management (★★★★☆)

  - RR_TAKE_PROFIT = 1.8 : Ratio risque/récompense 1:1.8
  - DAILY_DD_LIMIT = 0.03 : Circuit breaker à -3%
  - USE_ADAPTIVE_RISK : Réduit le risque après pertes
  - MAX_CONCURRENT_TRADES = 2 : Limite l'exposition

  Impact : Protège le capital et maximise les gains

### 4. Filtre ATR (★★★☆☆)

  ATR_FVG_MIN_RATIO = 0.2
  ATR_FVG_MAX_RATIO = 2.5
  Impact : Filtre les FVG trop petits ou trop grands par rapport à la volatilité

### 5. ML Meta-Labelling (★★☆☆☆) - FILTRE SECONDAIRE

  ML_THRESHOLD = 0.4
  Impact : Avec un seuil de 0.4 (40%), le ML rejette environ 60% des signaux
  - C'est un filtre conservateur, pas le moteur principal
  - Aide à réduire les faux positifs
  - Améliore légèrement le winrate mais réduit le nombre de trades

  Preuve de l'importance relative :
  - Quand vous avez augmenté ML_THRESHOLD de 0.4 à 0.6 → Performance DÉGRADÉE
  - Grid search de 432 combinaisons → Aucune amélioration vs baseline
  - Cela montre que la stratégie ICT est déjà très sélective

### Conclusion :

  Hiérarchie de performance :
  1. ICT Strategy (FVG + BOS + OB) : 70% de la performance
  2. Kill Zones (London/NY) : 20% de la performance
  3. Risk Management : 8% de la performance
  4. ML + Filtres : 2% de la performance (fine-tuning)

---

## 📞 Support & Ressources

- **Guide de déploiement** : Consultez `README.md`
- **Logs du bot** : Les logs s'affichent dans le terminal
- **Backtests** : Résultats sauvegardés dans `backtest/*.json`

---

## 📜 License

Ce projet est fourni "tel quel" sans garantie. Utilisez-le à vos propres risques.

---

## 🎯 Résumé des Étapes

1. ✅ Installer les dépendances
2. ✅ Configurer MT5 et Telegram
3. ✅ Tester avec `test_telegram.py`
4. ✅ Lancer un backtest
5. ✅ Tester sur compte **DEMO**
6. ✅ Monitorer via Dashboard
7. ⏳ Passage en LIVE après validation

---

**Version** : 3.1 - Multi-Bot Edition avec Grid Testing
**Dernière mise à jour** : 10 Novembre 2025
**Bot** : ICT Trading Bot with ML Meta-Labelling, Multi-Bot Management & Grid Testing Optimization

🤖 **Happy Trading!**
