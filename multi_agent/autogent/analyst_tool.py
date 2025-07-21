import json
import logging
from typing import Sequence, Optional

import pandas as pd
from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_core import CancellationToken

from multi_agent.agents import ScheduleAnalystAgent
from multi_agent.config.models import SlotInfo, MeetingSchedule
from multi_agent.mock_data.calendar import get_person_calendar
from multi_agent.mock_data.preferences import get_preference
from multi_agent.logger.AgentLogger import AgentLogger


class AnalystAgentAutogen(BaseChatAgent):
    def __init__(self, name="analyst", description=None, logger: Optional[AgentLogger] = None):
        super().__init__(name=name, description=description)
        self.logger = logger or AgentLogger(agent_name=name)
        self.logger.info(f"Initialized {name} agent")

    @property
    def produced_message_types(self):
        return [TextMessage]

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken) -> Response:
        """
        Processes received chat messages to propose available meeting slots based on
        provided participants and schedule information. The method validates and parses
        the information from the latest message, calculates suitable time slots, and
        responds with the proposed options in JSON format.

        :param messages: A sequence of chat messages where the last message contains
            meeting details in JSON format.
        :type messages: Sequence[BaseChatMessage]
        :param cancellation_token: A token to signal cancellation of the operation.
        :type cancellation_token: CancellationToken
        :return: A response containing proposed meeting slots serialized to JSON format.
        :rtype: Response
        """
        self.logger.process_step("on_messages", "Processing incoming messages")

        user_msg = messages[-1]
        assert isinstance(user_msg, TextMessage)

        self.logger.data_in("Coordinator", "Received message with meeting details", user_msg.content)
        self.logger.debug(f"Processing message from {user_msg.source}")

        try:
            payload = json.loads(user_msg.content)
            participants: list[str] = payload["participants"]
            schedule: dict = payload["schedule"]

            self.logger.info(f"Processing request for {len(participants)} participants")
            self.logger.debug(f"Participants: {participants}")
            self.logger.debug(f"Schedule: {schedule}")

            self.logger.process_step("propose_slots", "Finding available meeting slots")

            slots: list[SlotInfo] = self.propose_slots(
                participants=participants,
                meeting_schedule=MeetingSchedule(**schedule)
            )

            self.logger.info(f"Found {len(slots)} potential meeting slots")

            response_content = json.dumps([s.model_dump() for s in slots])

            self.logger.data_out("Coordinator", f"Returning {len(slots)} proposed slots")

            if self.logger.logger.level <= logging.DEBUG:
                for i, slot in enumerate(slots[:3]):  # Just the first 3
                    self.logger.debug(
                        f"Slot {i + 1}: {slot.start_time}-{slot.end_time} (confidence: {slot.confidence})")

            return Response(
                chat_message=TextMessage(
                    source=self.name,
                    content=response_content
                )
            )

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
            raise

    async def on_reset(self, cancellation_token):
        self.logger.info("Agent reset requested")
        return None

    def propose_slots(self, participants: list[str], meeting_schedule: MeetingSchedule) -> list[SlotInfo]:
        """
        Proposes a list of available meeting slots based on participants' calendars,
        preferences, and the meeting schedule parameters provided.

        It identifies free time slots that align with the working hours defined in the
        meeting schedule and ensures that all participants are available during the
        proposed time slots. The free slots are determined using a scheduling analysis
        agent.

        :param participants: A list of participant IDs for whom the meeting slots
            will be determined.
        :type participants: list[str]
        :param meeting_schedule: An object that defines scheduling parameters such as
            working hours, meeting duration, and the target scheduling day.
        :type meeting_schedule: MeetingSchedule
        :return: A list of SlotInfo objects, each representing an available time slot
            that satisfies the requirements for all provided participants.
        :rtype: list[SlotInfo]
        """

        self.logger.process_step("propose_slots", f"Finding slots for {len(participants)} participants")
        self.logger.debug(
            f"Meeting schedule: working hours {meeting_schedule.working_hours_start}-{meeting_schedule.working_hours_end}, duration: {meeting_schedule.default_duration}m")


        self.logger.process_step("data_preparation", "Retrieving participant calendars and preferences")

        participants_data = {}

        for p in participants:

            preferences = get_preference(p)
            calendar = get_person_calendar(p)

            participants_data[p] = {
                "preferences": preferences,
                "calendar": calendar
            }
            self.logger.debug(f"Loaded data for participant {p}")

            if calendar is not None and not calendar.empty:
                self.logger.debug(f"Calendar for {p} has {len(calendar)} entries")

        self.logger.process_step("slot_finding", "Creating schedule analyst to find free slots")

        agent = ScheduleAnalystAgent(
            working_hours=(meeting_schedule.working_hours_start, meeting_schedule.working_hours_end),
            min_slot_duration=meeting_schedule.default_duration
        )

        self.logger.process_step("slot_analysis", "Finding free slots with schedule analyst")

        schedule_day = pd.to_datetime(meeting_schedule.schedule_day)

        self.logger.info(
            f"Finding slots for {schedule_day.strftime('%Y-%m-%d')}, duration: {meeting_schedule.default_duration}m")

        slots = agent.find_free_slots(
            participants_data=participants_data,
            meeting_duration=meeting_schedule.default_duration,
            schedule_day=schedule_day
        )

        self.logger.info(f"Found {len(slots)} potential slots")

        if slots:
            self.logger.debug(
                f"Top slot: {slots[0].start_time}-{slots[0].end_time} with confidence {slots[0].confidence}")
        else:
            self.logger.warning("No available slots found")

        return slots
