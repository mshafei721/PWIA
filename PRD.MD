\# 📄 PWIA: Persistent Web Intelligence Agent  

\*\*Version:\*\* 2.0  

\*\*Project Owner:\*\* Mohammed  

\*\*Starting Repo:\*\* \[OpenAI Assistant API Boilerplate](https://github.com/ali-abassi/OpenAI\_Assistant\_API\_Boilerplate\_CursorRules)  

\*\*Frontend:\*\* Pre-existing (needs refinement)  

\*\*Execution Mode:\*\* Local QEMU/KVM sandbox with GUI  

\*\*Interface:\*\* Web UI + Realtime VM Stream + CLI Agent



---



\## 🧠 Project One-Liner

A persistent, autonomous research agent that operates inside a secure local VM to browse, scrape, and export structured results—guided by an OpenAI LLM and visible via a real-time web UI.



---



\## 🎯 Goals



\- Persistent LLM-guided research agent

\- Operates inside a fully isolated Linux GUI VM

\- Starts with a user prompt and completes task only after high-confidence

\- Real-time updates to the user via chat interface

\- Creates and maintains structured `todo.md` log

\- Final results downloadable in CSV/Markdown/ZIP



---



\## 🏗️ Core Tech Stack



| Layer             | Stack                                        |

|------------------|----------------------------------------------|

| Agent (CLI)       | Python 3.11, Playwright, Typer, asyncio       |

| LLM               | OpenAI GPT-4 via Assistant API Boilerplate    |

| Backend           | FastAPI (API + WebSocket)                    |

| Frontend          | React + Tailwind (exists, refine further)    |

| VM Engine         | QEMU + KVM                                   |

| VM OS             | Ubuntu 22.04 + XFCE                          |

| GUI Streaming     | noVNC or SPICE                               |

| Memory            | TinyDB / JSON + Markdown (todo.md)           |

| Outputs           | `.md`, `.csv`, `.zip`                        |



---



\## 📁 Project Structure



```plaintext

pwia/

├── agent/

│   ├── main.py

│   ├── planner.py

│   ├── llm\_agent.py

│   ├── browser.py

│   ├── crawler.py

│   ├── scraper.py

│   ├── confidence.py

│   ├── memory.py

│   ├── output\_writer.py

│   └── utils.py



├── sandbox\_vm/

│   ├── start\_vm.sh

│   ├── image.qcow2

│   ├── cloud-init/

│   └── preinstall/



├── backend/

│   ├── api.py

│   ├── file\_export.py

│   └── websocket\_manager.py



├── frontend/                # (already exists – needs refinement)

│   ├── components/

│   ├── pages/

│   ├── App.tsx

│   └── tailwind.config.js



├── memory-bank/

│   ├── CLAUDE.md

│   ├── PLAN.md

│   ├── projectbrief.md

│   ├── techContext.md

│   ├── systemPatterns.md

│   ├── activeContext.md

│   └── progress.md



├── workspace/

│   └── <task\_id>/

│       ├── todo.md

│       ├── output.md

│       ├── output.csv

│       └── logs.json



├── config/

│   ├── prompt.txt

│   ├── task.yaml

│   └── .env



└── README.md

✅ Key Features

✅ OpenAI LLM Assistant Planning



✅ Autonomous Google search with fallback (Serper.dev / Brave)



✅ Playwright-powered browsing and scraping



✅ robots.txt-aware crawling



✅ Persistent execution with retries



✅ Structured memory (memory-bank/, todo.md, task.json)



✅ Confidence-based completion and halting



✅ Timestamped checklist tracking



✅ Realtime chat updates (WebSocket → frontend)



✅ Full VM GUI stream embedded in UI



✅ Final output export (via API or frontend)



📋 todo.md Content Format

markdown

Copy

Edit

\# 🧠 PWIA Task Plan: agent\_frameworks\_2025



\## Prompt

"Compare top open-source agent orchestration frameworks"



\## 🎯 Objectives

\- Search and gather open-source agent frameworks

\- Crawl GitHub, extract stars, docs, contributors

\- Verify ≥ 5 diverse sources



\## ✅ Success Criteria

\- Min 5 sources, unique domains

\- Docs, repo metrics present

\- Confidence ≥ 85%



\## 📋 Checklist

\- \[x] Parsed task with LLM – 2025-07-13 14:21

\- \[x] Google search executed – 2025-07-13 14:24

\- \[ ] Crawled GitHub pages

\- \[ ] Metadata extracted

\- \[ ] Confidence check passed

\- \[ ] Exported final report



\## 🧠 LLM Reflection Notes

\- 2025-07-13 14:27 – Genspark robots.txt disallowed

\- 2025-07-13 14:29 – Adjusted query after repeated domains

📤 Outputs

File	Description

.md	Markdown-formatted research report

.csv	Tabular extracted metadata

.zip	Full task archive

todo.md	Task goals, status, reflections

.json	Agent memory state



All located in /home/agent/workspace/<task\_id>/ and available for download.



🧠 Best Practice Alignment

✅ CLAUDE.md with rules at root



✅ External memory (memory-bank/)



✅ PLAN.md with task-level prompts (checklist style)



✅ Controlled scope (techContext.md)



✅ UI-first approach supported



✅ Real-time updates to user



✅ File-based memory vs. token overload



✅ Each module tracked in progress.md

