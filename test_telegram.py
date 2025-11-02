"""
Script de test pour verifier la configuration Telegram
"""

import requests
import json
import os

def load_telegram_credentials():
    """Charge les identifiants Telegram depuis le fichier telegram_credentials.json"""
    if os.path.exists('telegram_credentials.json'):
        with open('telegram_credentials.json', 'r') as f:
            return json.load(f)
    else:
        print("[ERREUR] Fichier telegram_credentials.json introuvable !")
        print("Veuillez creer le fichier a partir de telegram_credentials.json.example")
        return None

# Chargement des identifiants
_creds = load_telegram_credentials()
if _creds is None:
    exit(1)

TELEGRAM_BOT_TOKEN = _creds.get("bot_token", "")
TELEGRAM_CHAT_ID = _creds.get("chat_id", "")

def test_telegram():
    """Envoie un message de test sur Telegram"""

    message = f"""
🔔 *Test de Configuration Telegram*

✅ Votre bot ICT Trading est correctement configure !

📱 *Bot* : ICT Trading Bot
🆔 *Chat ID* : {TELEGRAM_CHAT_ID}

Vous recevrez des notifications ici quand le bot prendra des positions.

_Message de test envoye avec succes !_
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        print("Envoi du message de test...")
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            print("\n[OK] SUCCESS ! Message envoye avec succes !")
            print("[OK] Verifiez votre Telegram (@ict_trading13_bot)")
            print(f"\nReponse de l'API : {response.json()}")
            return True
        else:
            print(f"\n[ERREUR] Code {response.status_code}")
            print(f"Reponse : {response.text}")
            return False

    except Exception as e:
        print(f"\n[ERREUR] Lors de l'envoi : {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("TEST DE CONFIGURATION TELEGRAM")
    print("="*60)
    print(f"\nBot Token : {TELEGRAM_BOT_TOKEN[:20]}...")
    print(f"Chat ID : {TELEGRAM_CHAT_ID}")
    print()

    success = test_telegram()

    print("\n" + "="*60)
    if success:
        print("[OK] CONFIGURATION VALIDE - Vous pouvez lancer le bot !")
    else:
        print("[ERREUR] Verifiez votre configuration")
    print("="*60)
