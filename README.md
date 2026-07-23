# 📬 Smart Mail Agent

An intelligent, AI-powered email assistant that automates Gmail synchronization, summarization, categorization, and prioritization. It supports running both cloud models (Gemini) and local offline LLMs (LM Studio/Nvidia NIM) with automated fallbacks, real-time syncing, and a responsive web dashboard.

---

## ✨ Key Features

- 🔄 **Auto-Sync Engine**: Runs a background daemon that periodically fetches new emails from Gmail, processes them, and saves them to a SQLite database.
- 🧠 **Dual AI Engine**:
  - **Cloud Gemini**: Fast, highly accurate reasoning via Google's Gemini models.
  - **Local LM Studio**: Offline, private, and free email processing via locally run LLMs.
  - **Smart Fallback**: Automatically falls back from local models to cloud API if the local server goes offline (unless "Force Selected Provider" is toggled).
- 🏷️ **Smart Categorization & Prioritization**: Automatically classifies emails into categories (e.g., *Work*, *Personal*, *Promotion*, *Update*, *Social*) and assigns priority levels (*Important*, *Normal*, *Low*).
- 📝 **Intelligent Summarization**: Generates short, actionable summaries of incoming emails, displayed directly on the dashboard.
- ⚙️ **Custom Agent Persona**: Configure custom agent instructions to tailor the tone, categorization style, and focus of your assistant.
- 🖥️ **Premium Dashboard**: A clean, responsive, and modern UI displaying the inbox status, AI configuration, sync schedules, and logs.

---

## 🛠️ Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────┐
│                      Web UI                            │
│           (HTML5, Vanilla CSS, JS/API Client)          │
└───────────┬────────────────────────────────┬───────────┘
            │ API Requests                   │ Websockets / Status Check
            ▼                                ▼
┌────────────────────────────────────────────────────────┐
│                   Flask Server                         │
│   (App, DB Manager, Auth Manager, Background Worker)   │
└───────────┬────────────────────────────────┬───────────┘
            │                                │
            ▼ (Gmail API)                    ▼ (SQLite - WAL Mode)
┌──────────────────────┐          ┌──────────────────────┐
│     Google Gmail     │          │    mail_agent.db     │
└──────────────────────┘          └──────────────────────┘
            │
            ▼ (AI API Calls)
┌────────────────────────────────────────────────────────┐
│                     AI Provider                        │
│     (Local LM Studio / NVIDIA NIM / Cloud Gemini)      │
└────────────────────────────────────────────────────────┘
```

- **Backend**: Python, Flask, SQLite (with WAL mode enabled for concurrent read/write safety).
- **Frontend**: HTML5, Vanilla CSS, Modern ES6 Javascript (async/await, custom UI components).
- **Integrations**: Google Gmail API (OAuth 2.0 flow), Google Gemini API, LM Studio Local Server API, NVIDIA NIM API.

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- **Python 3.10+** installed.
- A Google Cloud Project with the **Gmail API** enabled.
- Downloaded client credentials (`credentials.json`) from Google Cloud Console.

### 2. Clone and Setup
```bash
# Clone the repository
git clone https://github.com/vishalriswanth-8/mail-agent.git
cd mail-agent

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
LMSTUDIO_BASE_URL=http://localhost:1234
LMSTUDIO_MODEL=qwen3.5-4b
NVIDIA_API_KEY=your_nvidia_api_key_here
```

### 4. Place Credentials
Copy your downloaded Google Client Credentials file to the root of the project as `credentials.json`.

### 5. Run the Application
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000` (or the port specified in terminal).

---

## ⚙️ How to Configure AI Settings

### 1. Model Providers
Navigate to **Agent Settings** (⚙️ icon in the left sidebar):
- **Cloud Gemini**: Quick, zero-setup option (requires `GEMINI_API_KEY`).
- **Local LM Studio**: Zero-cost, fully private option. Launch LM Studio, load your model (e.g., `qwen` or `llama`), turn on the Local Server (`http://localhost:1234`), and click **Test Connection** in the dashboard.
- **Force Selected Provider**: 
  - *Checked*: Only uses your selected provider. If it's offline, processing fails gracefully.
  - *Unchecked*: Enables smart fallback (e.g. if Local LM Studio is offline, automatically queries Cloud Gemini).

### 2. Auto-Sync
In the **Email Synchronization** section:
- Check **"Enable Auto-Sync"**.
- Specify the **Sync Interval** (default is `300` seconds / 5 minutes).
- Click **"Save Settings"**.

---

## 📂 Project Structure

```
mail_agent/
│
├── agent/
│   ├── __init__.py
│   ├── ai_engine.py          # AI interaction, fallback logic, prompt builder
│   └── autonomous_agent.py   # Background auto-sync daemon
│
├── static/
│   ├── css/
│   │   └── style.css         # Dashboard styles
│   └── js/
│       ├── api.js            # Frontend API client integration
│       └── app.js            # UI interaction & event listeners
│
├── templates/
│   └── index.html            # Main dashboard HTML template
│
├── app.py                    # Flask application endpoints & route handlers
├── config.py                 # Environment variables and system config
├── requirements.txt          # Python packages list
└── mail_agent.db             # Local SQLite database (auto-generated)
```

---

## 🆘 Troubleshooting

- **No Emails Showing**: Verify your Gmail API authentication. Look at the terminal for the Google Sign-in flow prompts.
- **Model Status is Offline**: Click **"Test Connection"** under Settings. If local, make sure LM Studio server is running on `http://127.0.0.1:1234`. If cloud, make sure your API key in the `.env` file is correct and you have internet access.
- **Emails are Syncing but Not Categorizing**: Check if both providers are offline or if the database is locked. You can view the live terminal log for exact warning/error codes.

---

## 📄 License
This project is licensed under the MIT License.
