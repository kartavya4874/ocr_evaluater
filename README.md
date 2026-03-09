# Exam Evaluator

Automated exam evaluation desktop application powered by OpenAI GPT-4o. Faculty double-clicks it and it works.

## Architecture

```
Electron Shell (Desktop Window)
    └── React UI (Vite)
            ↕ IPC
    Python Backend (FastAPI, spawned as child process)
            ↕
    MongoDB (local or remote)
    Redis (optional, distributed mode)
    OpenAI GPT-4o API
```

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+
- **MongoDB** running locally or remotely
- **Poppler** (for pdf2image PDF conversion)
  - Windows: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases) and add to PATH
  - macOS: `brew install poppler`
  - Linux: `sudo apt install poppler-utils`
- **Redis** (optional, only for distributed mode)

## Setup

### 1. Install Node.js dependencies

```bash
npm install
```

### 2. Create Python virtual environment and install dependencies

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Start MongoDB

```bash
mongod
```

## Development

### Run the full app (Electron + React + Python):

```bash
npm run electron:dev
```

This will:
1. Start the Vite dev server on port 5173
2. Start Electron, which spawns the Python backend
3. Open the app window

### Run just the React frontend:

```bash
npm run dev
```

### Run just the Python backend:

```bash
python -m uvicorn backend.main:app --port 8765 --host 127.0.0.1 --reload
```

## First Run

1. Launch the app
2. Go to **Setup**
3. Set your **Root Exam Folder** path
4. Enter your **OpenAI API Key**
5. Set your **MongoDB URI** (default: `mongodb://localhost:27017`)
6. Click **Test Connections** to verify
7. Click **Save Configuration**
8. Go to **Dashboard** → **Scan Folder** → **Start Evaluation**

## Exam Folder Structure

```
<root_exam_folder>/
├── CS301/
│   ├── CS301_QuestionPaper.pdf
│   ├── CS301_AnswerKey.pdf
│   ├── CS301_2023CS001.pdf
│   ├── CS301_2023CS002.jpg
│   └── ...
├── ECE204/
│   └── ...
```

- Course code = subfolder name
- Question paper: `<CODE>_QuestionPaper.<ext>`
- Answer key: `<CODE>_AnswerKey.<ext>`
- Student sheets: `<CODE>_<ROLLNUMBER>.<ext>`
- Supported: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.tiff`

## Building for Distribution

```bash
npm run electron:build
```

Output:
- Windows: `build/*.exe`
- macOS: `build/*.dmg`
- Linux: `build/*.AppImage`

## Distributed Mode

Enable in Setup → toggle **Distributed Mode**. On worker machines:

```bash
python worker.py --head http://<HEAD_IP>:<PORT> --id worker_2 --threads 4
```

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | Electron |
| Frontend | React (Vite) |
| Backend | Python 3.11+ — FastAPI + Uvicorn |
| AI | OpenAI GPT-4o |
| Database | MongoDB (pymongo) |
| Job queue | Redis (optional) |
| Excel export | openpyxl |
| PDF to image | pdf2image + Pillow |
| Packaging | electron-builder |
