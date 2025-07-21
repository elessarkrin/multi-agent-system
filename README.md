# Multi-Agent Meeting Scheduler System - Complete Setup and Execution Guid

## Project Overview
This is a sophisticated multi-agent system implementing a meeting scheduler where two specialized AI agents negotiate to find optimal meeting times between busy professionals. The system uses mock data to simulate calendars and demonstrates advanced multi-agent coordination concepts.


### Agent Architecture
- **Agent 1: Schedule Analyst** - Analyzes multiple calendars and proposes meeting slots
- **Agent 2: Negotiation Specialist** - Negotiates between conflicting schedules and preferences
- **Coordinator Agent** - Orchestrates the entire process and manages communication

## Prerequisites
Before setting up the project, ensure you have the following installed:
- **Docker** (latest version) - [Download here](https://www.docker.com/get-started)
- **Docker Compose** - Usually included with Docker Desktop
- **Python 3.13** - [Download here](https://www.python.org/downloads/)
- **PDM** (Python Dependency Manager) - Install with `pip install pdm`
- **Bash shell** - Linux, macOS, or WSL on Windows
- **Git** - For cloning the repository

---
## Setup Instructions
### 1. Clone and Enter the Repository
``` bash
git clone <your-repo-url>
cd MultiAgentSystem
```
### 2. Make Setup Script Executable
``` bash
chmod +x setup.sh
```
### 3. Download AI Model and Start LLM Server
The project uses a local LLM (Mistral-Nemo) for AI agent processing:
``` bash
# This will download the model and start the LLaMA server
./setup.sh setup
```
**Note:** The first run may take 10-15 minutes as it downloads a ~4GB AI model.
### 4. Install Python Dependencies
``` bash
# Install PDM if you haven't already
pip install pdm

# Install all project dependencies (PDM automatically manages virtual environment)
pdm install
```
### 5. Verify Setup
Check that the LLM server is running:
``` bash
./setup.sh status
```
You should see the `llama-server` container running on port 1234.

---

## Project Structure
``` 
MultiAgentSystem/
├── multi_agent/           # Core application code
│   ├── agents/           # Agent implementations
│   │   ├── schedule_analyst.py      # Calendar analysis agent
│   │   └── negotiation_specialist.py # Conflict resolution agent
│   ├── autogent/         # Agent coordination framework
│   │   ├── coordinator.py           # Main orchestrator
│   │   ├── analyst_tool.py          # Analyst wrapper
│   │   └── negotiatior_tool.py      # Negotiator wrapper
│   ├── config/           # Data models and configuration
│   ├── mock_data/        # Data generation utilities
│   └── logger/           # Comprehensive logging system
├── data/                 # Input data files
│   ├── calendar_data.tsv            # Participant calendars
│   └── participant_preferences.tsv  # Scheduling preferences
├── models/               # Downloaded AI models
├── logs/                 # Application logs
├── setup.sh             # Automated setup script
├── docker-compose.yml   # LLM server configuration
└── README.md           # Project documentation
```

---

## **Data Format**

The system uses two main data files in TSV (Tab-Separated Values) format:

### **participant_preferences.tsv**
Contains participant scheduling preferences with the following columns:
- `person`: Participant identifier (e.g., Person_1, Person_2, etc.)
- `no_meetings_before`: Earliest time for meetings (format: HH:MM or just H)
- `no_meetings_after`: Latest time for meetings (format: HH:MM or just H)
- `prefer_morning`: Boolean preference for morning meetings (True/False)
- `prefer_afternoon`: Boolean preference for afternoon meetings (True/False)
- `avoid_lunch_time`: Boolean to avoid lunch hours (True/False)
- `max_meetings_per_day`: Maximum number of meetings per day (numeric)
- `preferred_max_duration`: Maximum preferred meeting duration in minutes (numeric)

Example entries:
- Person with strict morning preference: `Person_1	09:00	17:00	True	False	False	4.0	45.0`
- Person with flexible schedule: `Person_2` (all fields empty except person name)
- Person with afternoon preference: `Person_6		16	False	True	False		30.0`

### **calendar_data.tsv**
Contains existing calendar entries/meetings for participants. This file tracks:
- Participant identifiers
- Existing meeting times and dates
- Duration of existing meetings
- Meeting conflicts and availability

Both files use empty cells (just tabs) to represent missing or unspecified preferences, allowing for flexible participant configurations.

---

## **Available Commands**

- `./setup.sh setup`  
  Download the model (if not already present) and start the LLaMA server.

- `./setup.sh download`  
  Download the model only.

- `./setup.sh start`  
  Start the LLaMA server (requires model to be present).

- `./setup.sh stop`  
  Stop all running services.

- `./setup.sh logs`  
  View real-time logs from the LLaMA server.

- `./setup.sh status`  
  Show the status of all services.

- `./setup.sh cleanup`  
  Remove all containers, images, and volumes created by Docker Compose.

- `./setup.sh help`  
  Show all available commands and usage examples.

---

## **PDM Commands**

- `pdm add <package>`  
  Add a new dependency to the project.

- `pdm update`  
  Update dependencies to their latest versions.

- `pdm run <command>`  
  Run a command in the PDM environment.

- `pdm run python meeting_scheduler.py`  
  Run the meeting scheduler script.

---

## Troubleshooting
### Common Issues
1. **LLM Server Not Running**
``` bash
   ./setup.sh start  # Start the server
   ./setup.sh logs   # Check for errors
```
1. **Python Dependencies Missing**
``` bash
   pdm install --dev  # Install with development dependencies
```
1. **Model Download Issues**
``` bash
   ./setup.sh download  # Re-download the model
```
1. **Port Conflicts**
    - The LLM server runs on port 1234
    - Modify `docker-compose.yml` if needed

### Useful Commands
``` bash
# View real-time logs
./setup.sh logs

# Check service status
./setup.sh status

# Stop all services
./setup.sh stop

# Complete cleanup
./setup.sh cleanup

# Show all available commands
./setup.sh help
```


---

#### **License**

MIT License (or your preferred license)