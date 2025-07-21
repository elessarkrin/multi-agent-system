# Multi-Agent Meeting Scheduler System

## Prerequisites

Before setting up the project, ensure you have the following installed:

### 1. Python 3.13

#### **Linux/macOS**
```bash
# On Ubuntu (replace 3.13 with the latest available if needed)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13 python3.13-venv python3.13-dev
```
Or download and build from source:
```bash
wget https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz
tar -xvf Python-3.13.0.tgz
cd Python-3.13.0
./configure --enable-optimizations
make -j$(nproc)
sudo make altinstall
```

#### **Windows**
- Download the official installer from [python.org](https://www.python.org/downloads/windows/).
- Run the installer, check “Add Python to PATH”, and complete the installation.

---

### 2. Docker (Not Docker Desktop)

#### **Linux**
Follow the official instructions:  
[Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)

Quick steps:
```bash
sudo apt-get update
sudo apt-get install \
    ca-certificates \
    curl \
    gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
- Add your user to the docker group (optional, to run without sudo):
```bash
sudo usermod -aG docker $USER
```
- Log out and back in for group changes to take effect.

#### **macOS**
- Install with Homebrew:
```bash
brew install --cask docker
```
- Or follow [official Docker for Mac instructions](https://docs.docker.com/engine/install/).

---

### 3. Docker on Windows (with WSL)

**Recommended:** Use WSL2 and install Docker Engine inside your Linux distribution.

#### **Step 1: Install WSL2**
- Open PowerShell as Administrator:
```powershell
wsl --install
```
- Restart your computer if prompted.

#### **Step 2: Install Ubuntu (or your preferred distro)**
- From the Microsoft Store, install “Ubuntu”.

#### **Step 3: Install Docker inside WSL**
- Open Ubuntu (WSL) and follow the Linux Docker install steps above.

#### **Step 4: Enable Docker Daemon**
- Start Docker in WSL:
```bash
sudo service docker start
```
- Test with:
```bash
docker run hello-world
```

**Note:**  
- You do **not** need Docker Desktop for this setup.
- For more details, see [Docker’s official WSL2 guide](https://docs.docker.com/engine/install/ubuntu/#install-using-the-convenience-script) and [Microsoft’s WSL docs](https://learn.microsoft.com/en-us/windows/wsl/).

---

### 4. Other Tools

- **PDM** (Python Dependency Manager):  
  Install with:
  ```bash
  pip install pdm
  ```
- **Bash shell:**  
  - Linux/macOS: Pre-installed.
  - Windows: Use WSL (see above).
- **Git:**  
  - [Download here](https://git-scm.com/downloads)

---

## Setup Instructions

### 1. Clone and Enter the Repository
```bash
git clone <your-repo-url>
cd MultiAgentSystem
```
### 2. Make Setup Script Executable
```bash
chmod +x setup.sh
```
### 3. Download AI Model and Start LLM Server
The project uses a local LLM (Mistral-Nemo) for AI agent processing:
```bash
# This will download the model and start the LLaMA server
./setup.sh setup
```
**Note:** The first run may take 10-15 minutes as it downloads a ~4GB AI model.

### 4. Install Python Dependencies
```bash
# Install PDM if you haven't already
pip install pdm

# Install all project dependencies (PDM automatically manages virtual environment)
pdm install
```
### 5. Verify Setup
Check that the LLM server is running:
```bash
./setup.sh status
```
You should see the `llama-server` container running on port 1234.

---

## Execution

To run this project, execute the `main.py` script directly. This is the entry point for the multi-agent system and handles all orchestration and agent interactions.

**Example:**
```bash
python -m multi_agent.main
```

---

## Project Overview

This is a sophisticated multi-agent system implementing a meeting scheduler where two specialized AI agents negotiate to find optimal meeting times between busy professionals. The system uses mock data to simulate calendars and demonstrates advanced multi-agent coordination concepts.

---

## Architecture Choice

**Coordinator Pattern:**  
The system uses a coordinator-based architecture. This was chosen because there are only a small number of agents to manage, and their execution must follow a specific, predefined order. The coordinator ensures that each agent runs at the appropriate step, maintaining the correct flow and dependencies between tasks.

### Agent Architecture

- **Agent 1: Schedule Analyst** - Analyzes multiple calendars and proposes meeting slots
- **Agent 2: Negotiation Specialist** - Negotiates between conflicting schedules and preferences
- **Coordinator Agent** - Orchestrates the entire process and manages communication

---

## LLM Usage & Rationale

**Limited Role of LLM:**  
Although the initial design considered using a Large Language Model (LLM) for agent reasoning and negotiation, the final implementation uses the LLM only for tailoring the last response to the user. The core agent processes—such as scheduling, negotiation, and coordination—are mechanical, deterministic, and follow well-defined configurations and step-by-step logic. As a result, the LLM is not required for these internal processes, nor for the negotiation rounds.

**Why `mistral-nemo-instruct-2407`?**  
1. **No API Key or Subscription Needed:** I wanted a local model to avoid paid subscriptions or API keys.  
2. **Tool & Reasoning Support:** The model supports tool use and reasoning, which fit my initial orchestration architecture plans.  
3. **Resource Efficiency:** My machine can run this model efficiently.  
4. **Server Deployment:** It can be mounted on a server with an OpenAI-compatible API, making integration flexible.

---

## Project Structure

``` 
MultiAgentSystem/
├── multi_agent/    # Core application code
│   ├── agents/    # Agent implementations
│   │   ├── schedule_analyst.py    # Calendar analysis agent
│   │   └── negotiation_specialist.py # Conflict resolution agent
│   ├── autogent/    # Agent coordination framework
│   │   ├── coordinator.py    # Main orchestrator
│   │   ├── analyst_tool.py    # Analyst wrapper
│   │   └── negotiatior_tool.py    # Negotiator wrapper
│   ├── config/    # Data models and configuration
│   ├── mock_data/    # Data generation utilities
│   └── logger/    # Comprehensive logging system
├── data/    # Input data files
│   ├── calendar_data.tsv    # Participant calendars
│   └── participant_preferences.tsv  # Scheduling preferences
├── models/    # Downloaded AI models
├── logs/    # Application logs
├── setup.sh    # Automated setup script
├── docker-compose.yml   # LLM server configuration
└── README.md    # Project documentation
```

---

## Data Format

The system uses two main data files in TSV (Tab-Separated Values) format:

### participant_preferences.tsv

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

### calendar_data.tsv

Contains existing calendar entries/meetings for participants. This file tracks:
- Participant identifiers
- Existing meeting times and dates
- Duration of existing meetings
- Meeting conflicts and availability

Both files use empty cells (just tabs) to represent missing or unspecified preferences, allowing for flexible participant configurations.

---

## Available Commands

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

## PDM Commands

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
```bash
   ./setup.sh start  # Start the server
   ./setup.sh logs   # Check for errors
```
2. **Python Dependencies Missing**
```bash
   pdm install --dev  # Install with development dependencies
```
3. **Model Download Issues**
```bash
   ./setup.sh download  # Re-download the model
```
4. **Port Conflicts**
    - The LLM server runs on port 1234
    - Modify `docker-compose.yml` if needed

### Useful Commands
```bash
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

## License

MIT License (or your preferred license)