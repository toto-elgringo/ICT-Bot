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
- [Structure du Projet](#-structure-du-projet)
- [Troubleshooting](#-troubleshooting)
- [Sécurité](#-sécurité)

---

## ✨ Fonctionnalités

- ✅ **Stratégie ICT** : Fair Value Gaps (FVG), Break of Structure (BOS), Order Blocks (OB), Kill Zones
- ✅ **Machine Learning** : Meta-labelling avec Logistic Regression pour filtrer les trades
- ✅ **Dashboard Streamlit** : Interface web pour contrôler et monitorer le bot
- ✅ **Notifications Telegram** : Alertes en temps réel lors de l'ouverture de positions
- ✅ **Backtesting** : Testez vos stratégies sur des données historiques
- ✅ **Risk Management** : Circuit breaker, risque adaptatif, sessions adaptatives
- ✅ **Comparaison de Backtests** : Comparez plusieurs backtests côte à côte

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

### Mode 1 : Interface Dashboard (Recommandé)

Lancez l'interface web Streamlit :

```bash
streamlit run streamlit_bot_manager_v2.py
```

L'interface s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`

**Depuis le dashboard, vous pouvez** :
- ✅ Démarrer/Arrêter le bot en mode LIVE
- ✅ Modifier les paramètres de trading
- ✅ Lancer des backtests
- ✅ Comparer les résultats de backtests
- ✅ Supprimer des backtests
- ✅ Visualiser les courbes d'équité

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

### Dashboard Streamlit

#### 📊 Onglet "Dashboard Live"
- Visualisez votre solde, équité, profit
- Consultez les positions ouvertes
- Voyez les derniers trades (24h)

#### ⚙️ Onglet "Paramètres"
Configurez tous les paramètres :
- **Risque par trade** : 0.1% - 5%
- **Risk/Reward** : 1.0 - 3.0
- **Max trades concurrents** : 1-5
- **Cooldown** : Barres entre trades
- **ML Threshold** : Seuil de confiance (0.0 - 1.0)
- **Filtres ATR, Circuit Breaker, Risque Adaptatif**

#### 🧪 Onglet "Backtest"
- Sélectionnez symbole, timeframe, nombre de barres
- Lancez un backtest avec les paramètres actuels
- Visualisez les résultats

#### 📈 Onglet "Historique"
- **Consultez** les backtests passés
- **Supprimez** les backtests inutiles (bouton 🗑️)
- **Comparez** plusieurs backtests côte à côte
  - Multiselect dropdown
  - Tableau : Trades | Win Rate (%) | PnL ($) | Max DD (%)

---

### Notifications Telegram

Quand le bot ouvre une position, vous recevez :

```
🔔 Nouvelle Position Ouverte

📈 BUY EURUSD

📍 Entree: 1.08450
🎯 Take Profit: 1.08650
🛑 Stop Loss: 1.08350

📊 Risque: 0.00100
⏰ Heure: 2025-11-02 14:23:15
💰 Volume: 0.15 lots
```

---

## 📂 Structure du Projet

```
ICT-Bot/
├── ict_bot_all_in_one.py              # Bot principal (backtest + live)
├── streamlit_bot_manager_v2.py        # Interface web dashboard
├── test_telegram.py                   # Test des notifications Telegram
│
├── mt5_credentials.json               # Vos credentials MT5 (non versionné)
├── telegram_credentials.json          # Vos credentials Telegram (non versionné)
├── bot_config.json                    # Configuration des paramètres
│
│
├── backtest/                          # Résultats des backtests (JSON)
│   ├── backtest_20250102_1430.json
│   └── backtest_20250102_1520.json
│
├── ict_model.pkl                      # Modèle ML sauvegardé
├── .gitignore                         # Protège les fichiers sensibles
└── README.md                          # Ce fichier
```

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
streamlit run streamlit_bot_manager_v2.py --server.port 8502
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
streamlit run streamlit_bot_manager_v2.py
# Surveillez les performances quotidiennement
```

### Phase 4 : Passage en LIVE (Après validation)
⚠️ **Seulement si les performances DEMO sont satisfaisantes pendant 1+ mois**

---

## 📞 Support & Ressources

- **Guide de déploiement** : Consultez `README.md`
- **Logs du bot** : Les logs s'affichent dans le terminal
- **Backtests** : Résultats sauvegardés dans `backtest/*.json`

---

## 📜 License

Ce projet est fourni "tel quel" sans garantie. Utilisez-le à vos propres risques.

---

## 🎯 Prochaines Étapes

1. ✅ Installer les dépendances
2. ✅ Configurer MT5 et Telegram
3. ✅ Tester avec `test_telegram.py`
4. ✅ Lancer un backtest
5. ✅ Tester sur compte DEMO
6. ✅ Monitorer via Dashboard
7. ⏳ Passage en LIVE après validation

---

**Version** : 2.0
**Dernière mise à jour** : Novembre 2025
**Bot** : ICT Trading Bot with ML Meta-Labelling

🤖 **Happy Trading!**
