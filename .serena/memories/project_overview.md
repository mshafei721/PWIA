# PWIA Project Overview

## Purpose
PWIA (Persistent Web Intelligence Agent) is a research agent system designed to operate inside a secure local VM to browse, scrape, and export structured results. The agent is guided by an OpenAI LLM and provides a real-time web UI for monitoring.

## Project Goals
- Persistent LLM-guided research agent
- Operates inside a fully isolated Linux GUI VM (Ubuntu 22.04 + XFCE)
- Starts with user prompt and completes tasks only after high-confidence
- Real-time updates to users via chat interface
- Creates and maintains structured `todo.md` logs
- Final results downloadable in CSV/Markdown/ZIP formats

## Current Implementation Status
**CRITICAL**: Only the Frontend React application exists (100% complete)

**Missing Components (0% complete)**:
- Backend FastAPI server 
- Python agent system
- VM infrastructure (QEMU/KVM)
- Memory system files
- Integration between components

## Project Owner
Mohammed

## Version
2.0

## Starting Reference
Based on OpenAI Assistant API Boilerplate