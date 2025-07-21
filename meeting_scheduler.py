{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Multi-Agent System Package Overview\n",
    "\n",
    "This notebook explores the structure and functionality of the `multi_agent` package, which implements a meeting scheduling system using multiple AI agents."
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Package Structure\n",
    "\n",
    "The package is organized into several key directories:\n",
    "\n",
    "```\n",
    "multi_agent/\n",
    "├── __init__.py\n",
    "├── agents/\n",
    "├── autogent/\n",
    "├── config/\n",
    "├── mock_data/\n",
    "└── main.py\n",
    "```"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Setup and Dependencies\n",
    "\n",
    "First, let's import the necessary dependencies:"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import asyncio\n",
    "import json\n",
    "from autogen_agentchat.messages import TextMessage\n",
    "from autogen_agentchat.ui import Console\n",
    "from autogen_core.models import ModelFamily\n",
    "from autogen_ext.models.openai import OpenAIChatCompletionClient\n",
    "from multi_agent.autogent.coordinator import CoordinatorAgent\n",
    "from multi_agent.autogent.analyst_tool import AnalystAgentAutogen\n",
    "from multi_agent.autogent.negotiatior_tool import NegotiatorAgentAutogen\n",
    "from multi_agent.config.models import MeetingSchedule\n",
    "from multi_agent.mock_data.preferences import get_random_participants"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Model Configuration\n",
    "\n",
    "Define the configuration for the AI model:"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def create_model_client():\n",
    "    return OpenAIChatCompletionClient(\n",
    "        base_url=\"http://127.0.0.1:1234/v1\",\n",
    "        api_key='not-use',\n",
    "        model=\"mistral-nemo-instruct-2407\",\n",
    "        model_info={\n",
    "            \"vision\": False,\n",
    "            \"function_calling\": True,\n",
    "            \"json_output\": False,\n",
    "            \"family\": ModelFamily.MISTRAL,\n",
    "            \"structured_output\": True,\n",
    "        }\n",
    "    )"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Agent Setup\n",
    "\n",
    "Create the necessary agents for scheduling:"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def setup_agents():\n",
    "    client = create_model_client()\n",
    "    initial_meeting_schedule = MeetingSchedule()\n",
    "    \n",
    "    coordinator = CoordinatorAgent(\n",
    "        model_client=client,\n",
    "        analyst_agent=AnalystAgentAutogen(\n",
    "            name=\"analyst\",\n",
    "            description=\"Proposes meeting slots that satisfy individual calendars.\"\n",
    "        ),\n",
    "        negotiator_agent=NegotiatorAgentAutogen(\n",
    "            name=\"negotiator\",\n",
    "            description=\"Negotiates preferences & selects best slot(s).\",\n",
    "        ),\n",
    "        initial_meeting_schedule=initial_meeting_schedule\n",
    "    )\n",
    "    \n",
    "    return coordinator"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Meeting Scheduling Process\n",
    "\n",
    "Define and run the meeting scheduling process:"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "async def schedule_meeting(max_participants=3):\n",
    "    try:\n",
    "        # Get random participants\n",
    "        participants = get_random_participants(max_number=max_participants)\n",
    "        print(f\"Scheduling meeting for participants: {participants}\")\n",
    "        \n",
    "        # Setup coordinator agent\n",
    "        coordinator = setup_agents()\n",
    "        \n",
    "        # Create user message\n",
    "        user_message = TextMessage(\n",
    "            source=\"user\",\n",
    "            content=json.dumps({\"participants\": participants})\n",
    "        )\n",
    "        \n",
    "        # Run scheduling process\n",
    "        result = await coordinator.run(task=[user_message])\n",
    "        \n",
    "        # Display results\n",
    "        await Console(result.messages)\n",
    "        \n",
    "    except Exception as e:\n",
    "        print(f\"Error during scheduling process: {str(e)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Run the Scheduler\n",
    "\n",
    "Execute the meeting scheduling process:"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Run the scheduling process\n",
    "await schedule_meeting(max_participants=3)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Understanding the Results\n",
    "\n",
    "The scheduling process involves multiple steps:\n",
    "\n",
    "1. **Participant Selection**: Random participants are selected for the meeting\n",
    "2. **Analysis Phase**: The analyst agent evaluates available time slots\n",
    "3. **Negotiation Phase**: The negotiator agent finds optimal slots based on preferences\n",
    "4. **Coordination**: The coordinator agent manages the overall process\n",
    "\n",
    "The final output includes:\n",
    "- Selected meeting time slot\n",
    "- Participant availability\n",
    "- Negotiation history\n",
    "- Success/failure status"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.0"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
