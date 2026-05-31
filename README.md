# JARVIS Desktop Assistant

A futuristic Windows desktop assistant built with Python and Tkinter. JARVIS can open apps, respond to typed or optional voice commands, summarize files, and chat using a real AI provider when available.

The assistant uses a flexible brain chain:

```text
OpenAI-compatible API -> Ollama -> Offline fallback
```   //

That means it can still run without internet or external AI services, but it becomes much smarter when connected to Ollama, OpenAI, LM Studio, or another OpenAI-compatible model server.

## Features

- Futuristic desktop UI
- App launcher for common Windows tools
- Typed chat commands
- Optional voice command support
- File summarization for text, code, CSV, log, JSON, Markdown, and DOCX files
- Offline fallback brain for simple answers, plans, checklists, definitions, and math
- Ollama support for local AI chat
- OpenAI-compatible API support for cloud or local model servers
- Simple JSON configuration file

## Screenshots

### Main Dashboard

![JARVIS dashboard](screenshots/jarvis-dashboard.png)

### AI Brain Chain

![JARVIS brain chain](screenshots/jarvis-brain-chain.png)

## Project Structure

```text
.
+-- jarvis_assistant.py   # Main desktop assistant app
+-- jarvis_config.json    # AI provider configuration
+-- run_jarvis.bat        # Windows launcher
+-- screenshots/          # README screenshot assets
+-- scripts/              # Utility scripts
+-- README.md             # Project documentation
```

## Requirements

- Windows
- Python 3.10 or newer

Tkinter is included with most Python installations on Windows.

## Quick Start

Clone or download the project, then open PowerShell in the project folder.

Run:

```powershell
python .\jarvis_assistant.py
```

Or double-click:

```text
run_jarvis.bat
```

## Basic Commands

Try these inside the JARVIS chat box:

```text
open notepad
open calculator
what can you do?
define life simply
tell what is smartphone
make a plan for learning Python
calculate 12*8+4
summarize a file
what time is it?
```

## AI Configuration

JARVIS reads AI settings from:

```text
jarvis_config.json
```

Default config:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "",
  "model": "gpt-4o-mini"
}
```

Do not commit a real API key to GitHub. Keep `api_key` empty in public repositories.

## Option 1: Use Ollama

Install Ollama:

[https://ollama.com](https://ollama.com)

Pull the default model:

```powershell
ollama pull llama3.2
```

Make sure Ollama is running, then start JARVIS:

```powershell
python .\jarvis_assistant.py
```

When Ollama is detected, the `AI CORE` indicator shows:

```text
Ollama connected
```

## Option 2: Use OpenAI API

Edit `jarvis_config.json`:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "YOUR_REAL_API_KEY",
  "model": "gpt-4o-mini"
}
```

Restart JARVIS after saving the file.

Important: never share or upload your real API key.

## Option 3: Use LM Studio Or Another Local Server

Start an OpenAI-compatible local server, then edit `jarvis_config.json`.

Example for LM Studio:

```json
{
  "base_url": "http://127.0.0.1:1234/v1",
  "api_key": "local",
  "model": "local-model"
}
```

Restart JARVIS after saving.

## Offline Mode

If no AI provider is available, JARVIS still works in offline fallback mode.

Offline mode can:

- open supported Windows apps
- summarize selected files
- summarize pasted text
- explain common topics
- create simple plans and checklists
- solve basic math expressions
- answer time and date questions

The `AI CORE` indicator shows:

```text
Offline fallback
```

## Voice Commands

Voice support is optional. The app works without it.

Install optional packages:

```powershell
pip install SpeechRecognition PyAudio
```

Then restart JARVIS and click the `Voice` button.

If `PyAudio` is difficult to install on Windows, use typed commands instead or install a wheel that matches your Python version.

## Supported Apps

The built-in launcher supports:

- Notepad
- Calculator
- Paint
- WordPad
- File Explorer
- Task Manager
- Settings
- Control Panel
- Command Prompt
- PowerShell

You can add more apps by editing the `APP_CATALOG` dictionary in `jarvis_assistant.py`.

## Supported File Types For Summaries

- `.txt`
- `.md`
- `.py`
- `.js`
- `.ts`
- `.tsx`
- `.jsx`
- `.json`
- `.csv`
- `.log`
- `.docx`

## Troubleshooting

### Ollama page looks blank in the browser

That is normal. `http://127.0.0.1:11434` is an API endpoint, not a chat webpage. Ask questions inside the JARVIS desktop app.

### Port 11434 is already in use

This usually means Ollama is already running. You do not need to start `ollama serve` again.

Check with:

```powershell
ollama list
```

### JARVIS still shows old behavior

Close the JARVIS window completely and restart it:

```powershell
python .\jarvis_assistant.py
```

### OpenAI API is not working

Check:

- `jarvis_config.json` has a real API key
- the model name is valid
- internet is working
- the file was saved before restarting JARVIS

## Security Notes

- Do not publish real API keys.
- Do not paste private documents into cloud AI providers unless you trust the provider and account settings.
- For private work, prefer Ollama or a local OpenAI-compatible server.

## License

Add your preferred license before publishing this repository.
