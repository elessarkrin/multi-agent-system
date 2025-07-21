import json
import logging
from typing import Sequence, Optional

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import TextMessage, BaseChatMessage
from autogen_core import CancellationToken

from multi_agent.agents import NegotiationSpecialistAgent
from multi_agent.config.models import NegotiationResult, SlotInfo, MeetingSchedule, NegotiationStrategy
from multi_agent.mock_data.calendar import get_person_calendar
from multi_agent.mock_data.preferences import get_preference
from multi_agent.logger.AgentLogger import AgentLogger


class NegotiatorAgentAutogen(BaseChatAgent):
    def __init__(self, name="negotiator", description=None, logger: Optional[AgentLogger] = None):
        super().__init__(name=name, description=description)

        self.logger = logger or AgentLogger(agent_name=name)
        self.logger.info(f"Initialized {name} agent")

    @property
    def produced_message_types(self):
        return [TextMessage]

    async def on_messages(self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken) -> Response:
        """
        Handles incoming messages during a negotiation session and processes them to create
        a response based on the provided negotiation information. It extracts relevant data
        from the messages, evaluates negotiation slots, and returns a response in text form.

        :param messages: A sequence of chat messages where each message is of type
            BaseChatMessage. These messages include the user's input and possibly previous
            negotiation interactions.
        :type messages: Sequence[BaseChatMessage]
        :param cancellation_token: A token used to indicate whether the operation should
            be cancelled.
        :type cancellation_token: CancellationToken
        :return: A response containing the result of the negotiation as a TextMessage,
            ready to be sent back to the user.
        :rtype: Response
        """
        self.logger.process_step("on_messages", "Processing incoming messages")

        user_msg = messages[-1]

        self.logger.data_in("Coordinator", "Received message for negotiation", user_msg.content)

        # Find previous negotiator messages to determine strategy progression
        negotiators = [msg for msg in messages if msg.source == 'negotiator']

        if negotiators:
            self.logger.debug(f"Found {len(negotiators)} previous negotiator messages")

            previous_result = json.loads(negotiators[-1].content)
            previous_strategy = NegotiationResult(**previous_result).strategy_choose

            self.logger.info(f"Previous negotiation strategy: {previous_strategy}")

        else:
            self.logger.info("No previous negotiation strategy found, starting with NONE")

            previous_strategy = NegotiationStrategy.NONE

        assert isinstance(user_msg, TextMessage)

        try:
            payload = json.loads(user_msg.content)

            self.logger.debug(f"Received payload with {len(payload.get('slots', []))} slots for negotiation")

            self.logger.process_step("negotiate_slots", "Starting negotiation process")

            negotiation: NegotiationResult = self.negotiate_slots(
                slots=[SlotInfo(**s) for s in payload["slots"]],
                participants=payload["participants"],
                schedule=payload["schedule"],
                min_score=0.6,
                previous_strategy=previous_strategy
            )

            self.logger.decision("negotiation_outcome",
                                 f"Negotiation outcome: {negotiation.outcome}",
                                 f"Strategy: {negotiation.strategy_choose}, Reasoning: {negotiation.reasoning}")

            result = negotiation.model_dump_json()

            self.logger.data_out("Coordinator", f"Returning negotiation result with outcome {negotiation.outcome}")

            return Response(
                chat_message=TextMessage(
                    source=self.name,
                    content=result
                )
            )
        except Exception as e:
            self.logger.error(f"Error during negotiation: {str(e)}", exc_info=True)
            raise

    async def on_reset(self, cancellation_token):
        self.logger.info("Agent reset requested")
        return None

    def negotiate_slots(self, slots: list[SlotInfo],
                        participants: list[str],
                        schedule: dict,
                        min_score: float = 0.60,
                        previous_strategy: NegotiationStrategy = NegotiationStrategy.NONE) -> NegotiationResult:
        """
        Executes a negotiation process to determine the optimal schedule for meeting slots
        based on the provided available slots, participants' preferences, and a given minimum
        acceptable score. The outcome is determined following the negotiation strategy, which
        can optionally use results from a prior scheduling strategy.

        :param slots: A list containing SlotInfo objects, each representing an available
                      time slot for the meeting negotiation process.
        :param participants: A list of participant names whose individual preferences
                             and calendars will be included in the negotiation.
        :param schedule: A dictionary representing the initial meeting schedule before
                         the negotiation process begins.
        :param min_score: Optional; A float value representing the minimum required score
                          that a schedule must achieve to be considered acceptable.
        :param previous_strategy: Optional; A NegotiationStrategy enum specifying the
                                  previous negotiation strategy to be taken into account.
        :return: Returns a NegotiationResult object encapsulating the negotiation outcome,
                 which includes the finalized schedule and meeting details.
        """
        self.logger.process_step("negotiate_slots",
                                 f"Negotiating {len(slots)} slots for {len(participants)} participants with strategy {previous_strategy}")

        self.logger.info(f"Min score: {min_score}, Previous strategy: {previous_strategy}")

        if slots:
            slot_info = slots[0]

            self.logger.debug(
                f"First slot example: {slot_info.start_time}-{slot_info.end_time}, confidence: {slot_info.confidence}")

        # convert participants dict back to {name: {"preferences": Pydantic, "calendar": df}}
        self.logger.process_step("data_preparation", "Loading participant data for negotiation")

        participants_data = {}

        for p in participants:
            preferences = get_preference(p)
            calendar = get_person_calendar(p)

            participants_data[p] = {
                "preferences": preferences,
                "calendar": calendar
            }

            self.logger.debug(f"Loaded data for participant {p}")

        self.logger.process_step("create_negotiator", "Creating negotiation specialist")

        meeting_schedule = MeetingSchedule(**schedule)

        self.logger.debug(
            f"Meeting schedule: day {meeting_schedule.schedule_day}, duration: {meeting_schedule.default_duration}m")

        negotiator = NegotiationSpecialistAgent(
            initial_schedule=meeting_schedule
        )

        self.logger.process_step("run_negotiation", "Running negotiation process")

        result = negotiator.negotiate_schedule(
            available_slots=slots,
            participants=participants_data,
            min_score=min_score,
            previous_strategy=previous_strategy
        )

        self.logger.decision("negotiation_complete",
                             f"Negotiation completed with outcome: {result.outcome}",
                             f"Strategy used: {result.strategy_choose}, Reasoning: {result.reasoning}")

        if result.selected_slot:
            self.logger.info(f"Selected slot: {result.selected_slot.start_time}-{result.selected_slot.end_time}")
            self.logger.debug(f"Selected slot confidence: {result.selected_slot.confidence}")

        else:
            self.logger.warning("No slot was selected during negotiation")

        self.logger.info(f"Alternative suggestions: {len(result.alternative_suggestions)}")

        return result