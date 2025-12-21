# 📡 TG Sniffer

**Telegram Channel Copier** — Uno strumento Python per copiare automaticamente i messaggi da uno o più canali Telegram di origine verso un canale di destinazione.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Telethon](https://img.shields.io/badge/Telethon-1.28.5-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## ✨ Funzionalità

- 📨 **Copia messaggi in tempo reale** — Inoltra automaticamente i messaggi da canali sorgente a un canale di destinazione
- 📋 **Multi-sorgente** — Supporta più canali sorgente contemporaneamente (per nome o ID)
- 🚫 **Filtro parole bloccate** — Blocca automaticamente i messaggi contenenti parole specifiche (es. link Zoom, Teams, etc.)
- ⏸️ **Modalità Dry-Run** — Testa la configurazione senza copiare effettivamente i messaggi
- 🎨 **Pretty Logger** — Output colorato e formattato per un monitoraggio chiaro
- 🐳 **Docker Ready** — Pronto per il deployment con Docker e Docker Compose
- 📝 **File di log** — Salva tutti i log su file per riferimento futuro

---

## 🚀 Quick Start

### Prerequisiti

- Python 3.9+
- Un account Telegram
- API ID e API Hash da [my.telegram.org](https://my.telegram.org)

### Installazione

1. **Clona la repository**

   ```bash
   git clone https://github.com/bmessaoudi/tg-sniffer.git
   cd tg-sniffer
   ```

2. **Installa le dipendenze**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configura le variabili d'ambiente**

   ```bash
   cp .env.example .env
   ```

   Modifica il file `.env` con le tue credenziali (vedi [Configurazione](#-configurazione))

4. **Genera la Session String**

   ```bash
   python generate_session.py
   ```

   Segui le istruzioni per autenticarti con l'account Telegram e ottenere la session string.

5. **Trova gli ID dei canali (opzionale)**

   ```bash
   python find_channel_id.py
   ```

   Questo script elenca tutti i canali/gruppi dell'account con i relativi ID.

6. **Avvia il bot**
   ```bash
   python main.py
   ```

---

## ⚙️ Configurazione

Crea un file `.env` nella root del progetto (puoi copiare da `.env.example`):

```env
# =============================================================================
# CREDENZIALI TELEGRAM API
# Ottieni da https://my.telegram.org
# =============================================================================
API_ID=your_api_id_here
API_HASH=your_api_hash_here

# =============================================================================
# SESSION STRING
# Generata con python generate_session.py
# =============================================================================
TELEGRAM_STRING_SESSION=your_session_string_here

# =============================================================================
# CANALI SORGENTE
# Lista separata da virgole di nomi di canali O ID
# =============================================================================
SOURCE_CHANNELS=Nome Canale 1,Nome Canale 2,1234567890

# =============================================================================
# CANALE DI DESTINAZIONE
# ID numerico del canale dove inviare i messaggi
# =============================================================================
DESTINATION_CHANNEL_ID=1234567890

# =============================================================================
# CONTROLLO COPIA
# true = copia messaggi, false = solo logging (dry-run)
# =============================================================================
COPY_ENABLED=false

# =============================================================================
# PAROLE BLOCCATE
# Lista separata da virgole (case-insensitive)
# Messaggi con queste parole NON verranno copiati
# =============================================================================
BLOCKED_WORDS=zoom.us,zoom.com,meet.google.com
```

### Variabili d'ambiente

| Variabile                 | Tipo    | Obbligatorio | Descrizione                                                |
| ------------------------- | ------- | ------------ | ---------------------------------------------------------- |
| `API_ID`                  | Integer | ✅           | Il tuo Telegram API ID                                     |
| `API_HASH`                | String  | ✅           | Il tuo Telegram API Hash                                   |
| `TELEGRAM_STRING_SESSION` | String  | ✅           | Session string per l'autenticazione                        |
| `SOURCE_CHANNELS`         | String  | ✅           | Canali sorgente (nomi o ID, separati da virgola)           |
| `DESTINATION_CHANNEL_ID`  | Integer | ✅           | ID del canale di destinazione                              |
| `COPY_ENABLED`            | Boolean | ❌           | `true` per copiare, `false` per dry-run (default: `false`) |
| `BLOCKED_WORDS`           | String  | ❌           | Parole da bloccare, separate da virgola                    |

---

## 🛠️ Script Utili

### `generate_session.py`

Genera una Session String per un account Telegram. Richiede il numero di telefono e il codice OTP ricevuto.

```bash
python generate_session.py
```

**Flusso:**

1. Inserisci il numero di telefono (con prefisso internazionale)
2. Ricevi il codice OTP su Telegram
3. Inserisci il codice
4. Se presente 2FA, inserisci la password
5. Copia la session string nel file `.env`

### `find_channel_id.py`

Trova l'ID di un canale Telegram specifico e elenca tutti i canali/gruppi disponibili.

```bash
python find_channel_id.py
```

---

## 🐳 Docker

### Costruisci l'immagine

```bash
docker build -t tg-sniffer .
```

### Esegui con Docker

```bash
docker run --env-file .env tg-sniffer
```

### Esegui con Docker Compose

```bash
docker-compose up -d
```

> **Nota:** Assicurati di creare il file `.env` prima di eseguire Docker.

---

## 📊 Output di Esempio

All'avvio, il bot mostra un banner ASCII con la configurazione attiva:

```
╔══════════════════════════════════════════════════════════╗
║  📡 TELEGRAM CHANNEL COPIER                              ║
╠══════════════════════════════════════════════════════════╣
║  Source: ['Trading Group', 'Signals Channel']            ║
║  Destination: 1234567890                                 ║
╠══════════════════════════════════════════════════════════╣
║  ✅ COPY MODE: ENABLED (messages will be copied)         ║
║  🚫 Blocked words: zoom.us, zoom.com, meet.google.com    ║
╚══════════════════════════════════════════════════════════╝
```

Durante l'esecuzione, ogni messaggio viene loggato con colori e formattazione:

```
12:30:45 [INFO] ──────────────────────────────────────────────────
12:30:45 [INFO] 📨 NEW MESSAGE
12:30:45 [INFO]    From: Trading Group
12:30:45 [INFO]    Preview: 🚀 BTC is going up! Buy now at...
12:30:45 [INFO]    ✅ COPIED to destination
12:30:45 [INFO] ──────────────────────────────────────────────────
```

---

## 📁 Struttura del Progetto

```
tg-sniffer/
├── main.py              # Script principale del bot
├── generate_session.py  # Generatore Session String
├── find_channel_id.py   # Utility per trovare ID canali
├── requirements.txt     # Dipendenze Python
├── .env.example         # Template configurazione
├── .env                 # Configurazione (da creare)
├── Dockerfile           # Container Docker
├── docker-compose.yml   # Orchestrazione Docker
├── output.log           # File di log
└── README.md            # Questo file
```

---

## 🔧 Dipendenze

```
python-dotenv==1.0.1
Telethon==1.28.5
```

---

## ⚠️ Note Importanti

1. **Session String sicura** — La session string permette accesso completo all'account Telegram. Non condividerla mai!

2. **API Credentials** — L'API_ID e API_HASH sono le tue credenziali personali. Non condividerle mai pubblicamente.

3. **Rate Limits** — Telegram ha limiti di velocità. Il bot gestisce i messaggi in tempo reale ma potrebbe subire rallentamenti con volumi molto elevati.

4. **Dry-Run Mode** — Si consiglia di testare sempre con `COPY_ENABLED=false` prima di attivare la copia effettiva.

5. **Permessi canali** — L'account deve essere membro dei canali sorgente e avere i permessi di scrittura sul canale di destinazione.

---

## 📄 Licenza

Questo progetto è distribuito sotto licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.

---

## 🤝 Contributi

I contributi sono benvenuti! Sentiti libero di aprire issue o pull request.

---

<p align="center">
  Made with ❤️ using <a href="https://github.com/LonamiWebs/Telethon">Telethon</a>
</p>
