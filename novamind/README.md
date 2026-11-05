# NovaMind - Private Document & Voice Assistant

Chat with your own PDFs and text files, fall back to live web search, and talk to it by voice.
Everything (AI model, embeddings, database) runs on **your computer** through Ollama.

## Quick start (Windows)
1. Install Python 3.10+ (tick "Add to PATH") and Ollama (https://ollama.com).
2. Double-click `setup.bat`
3. Open a terminal and run:
   `ollama pull llama3.2:3b`  and  `ollama pull nomic-embed-text`
4. Double-click `start.bat` -> the browser opens at http://127.0.0.1:8000

## Quick start (macOS / Linux)
`bash setup.sh`, pull the two models, then `bash start.sh`.

## Modes
- **Auto** - documents first, web if the documents do not contain the answer
- **Documents** - only your files (says "not found" instead of guessing)
- **Web** - DuckDuckGo search

See the full project documentation for architecture, code walkthrough and troubleshooting.
