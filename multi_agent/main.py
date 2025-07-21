import asyncio
import json
import os
import logging

from autogen_agentchat.messages import TextMessage
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient

from multi_agent.autogent.analyst_tool import AnalystAgentAutogen
from multi_agent.autogent.coordinator import CoordinatorAgent
from multi_agent.autogent.negotiatior_tool import NegotiatorAgentAutogen
from multi_agent.config.models import MeetingSchedule
from multi_agent.mock_data.preferences import get_random_participants
from multi_agent.logger.AgentLogger import AgentLogger, get_system_logger

# Configuration constants
MODEL_BASE_URL = "http://127.0.0.1:1234/v1"
MODEL_NAME = "mistral-nemo-instruct-2407"
API_KEY = 'not-use'
MAX_PARTICIPANTS = 3
SCHEDULE_DATE = '2025-07-22'
PARTICIPANTS = get_random_participants(max_number=MAX_PARTICIPANTS) # Random list of participants, based on mock data
MAX_NEGOTIATION_ROUNDS = 5

def setup_logging(log_level=logging.INFO):
    """
    Setup logging system for the application

    Args:
        log_level: Minimum log level to record
    """
    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    return get_system_logger(log_dir=log_dir, log_level=log_level)


def create_model_client() -> OpenAIChatCompletionClient:
    """
    Creates and configures the OpenAI chat completion client.

    Returns:
        OpenAIChatCompletionClient: Configured model client
    """
    return OpenAIChatCompletionClient(
        base_url=MODEL_BASE_URL,
        api_key=API_KEY,
        model=MODEL_NAME,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": ModelFamily.MISTRAL,
            "structured_output": True,
        }
    )


async def messages_to_async_stream(messages):
    """
    Convert a list of messages to an async generator.
    """
    for message in messages:
        yield message


async def main() -> None:
    """
    Main function that orchestrates the meeting scheduling process.
    Initializes agents, processes scheduling request and displays results.
    """
    # Initialize logging
    logger = setup_logging(logging.INFO)
    logger.info("Starting meeting scheduler application")

    try:
        # Initialize participants and schedule
        participants = PARTICIPANTS
        logger.info(f"Selected {len(participants)} random participants: {participants}")

        initial_meeting_schedule = MeetingSchedule()
        logger.info(f"Created initial meeting schedule: {initial_meeting_schedule}")

        # Initialize model client and agents
        logger.process_step("initialization", "Creating model client and agents")
        client = create_model_client()

        # Create agent loggers
        analyst_logger = AgentLogger(agent_name="AnalystAgent", log_level=logging.INFO)
        negotiator_logger = AgentLogger(agent_name="NegotiatorAgent", log_level=logging.INFO)
        coordinator_logger = AgentLogger(agent_name="CoordinatorAgent", log_level=logging.INFO)

        analyst_agent = AnalystAgentAutogen(
            name="analyst",
            description="Proposes meeting slots that satisfy individual calendars.",
            logger=analyst_logger
        )

        negotiator_agent = NegotiatorAgentAutogen(
            name="negotiator",
            description="Negotiates preferences & selects best slot(s).",
            logger=negotiator_logger
        )

        coordinator = CoordinatorAgent(
            model_client=client,
            analyst_agent=analyst_agent,
            negotiator_agent=negotiator_agent,
            max_negotiation_rounds=MAX_NEGOTIATION_ROUNDS,
            initial_meeting_schedule=initial_meeting_schedule,
            logger=coordinator_logger
        )
        logger.info("Agents initialized successfully")

        # Process scheduling request
        logger.process_step("schedule_request", "Processing scheduling request")
        user_message = TextMessage(
            source="user",
            content=json.dumps({
                "participants": participants,
                'schedule_date': SCHEDULE_DATE,
            })
        )
        logger.data_in("User", "Received scheduling request", user_message.content)

        logger.process_step("coordination", "Starting coordination process")
        # Execute Coordinator
        result = await coordinator.run(task=[user_message])
        logger.process_step("coordination", "Coordination process completed")

        # Output messages
        logger.info(f"{'-' * 80}")
        logger.info(f"Agent Messages")
        logger.info(f"{'-' * 80}")

        for message in result.messages:
            logger.info(f"{message.source}: {message.content}")

        logger.info(f"{'-' * 80}")

        logger.info("Meeting scheduling completed successfully")

    except Exception as e:
        logger.error(f"Error during scheduling process: {str(e)}", exc_info=True)
        print(f"Error during scheduling process: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())