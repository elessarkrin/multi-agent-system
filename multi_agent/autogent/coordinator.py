import json
from collections import Counter
from datetime import datetime
from typing import Optional, Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import TextMessage, UserMessage, BaseChatMessage
from autogen_core import CancellationToken
from autogen_core.models import SystemMessage, ChatCompletionClient

from multi_agent.autogent.analyst_tool import AnalystAgentAutogen
from multi_agent.autogent.negotiatior_tool import NegotiatorAgentAutogen
from multi_agent.config.models import MeetingSchedule
from multi_agent.logger.AgentLogger import AgentLogger


class CoordinatorAgent(AssistantAgent):
    """Simple coordinator: triggers analyst → negotiator,
    then emits the chosen slot."""

    def __init__(self,  model_client: ChatCompletionClient, analyst_agent: AnalystAgentAutogen,
                 negotiator_agent: NegotiatorAgentAutogen,
                 initial_meeting_schedule=MeetingSchedule(), max_negotiation_rounds=5,
                 logger: Optional[AgentLogger] = None):
        super().__init__(
            name="coordinator",
            model_client=model_client,
            system_message="You are a professional meeting scheduler providing clear, concise updates."
        )

        self.initial_meeting_schedule = initial_meeting_schedule
        self.negotiator_agent = negotiator_agent
        self.analyst_agent = analyst_agent
        self.max_negotiation_rounds = max_negotiation_rounds
        self.logger = logger or AgentLogger(agent_name="Coordinator")

        self.logger.info("Coordinator agent initialized")
        self.logger.debug(f"Initial meeting schedule: {initial_meeting_schedule}")
        self.logger.debug(f"Max negotiation rounds: {max_negotiation_rounds}")

    def reduce_meeting_dict_for_llm(self, meeting_data: dict) -> dict:
        """
        Ultra-minimal version focusing only on the most critical information.
        """
        selected = meeting_data.get('selected_slot', {})

        reduced = {
            'outcome': meeting_data.get('outcome'),
            'selected_time': f"{selected.get('start_time', 'N/A')} - {selected.get('end_time', 'N/A')}",
            'confidence': selected.get('confidence'),
            'duration_minutes': selected.get('duration_minutes'),
            'reasoning': meeting_data.get('reasoning'),
            'alternatives_count': len(meeting_data.get('alternative_suggestions', [])),
            'participant_assessments': {
                participant: notes[-1] if notes else 'No assessment'
                for participant, notes in selected.get('participant_notes', {}).items()
            }
        }

        self.logger.debug(f"Reduced meeting data: outcome={reduced['outcome']}, time={reduced['selected_time']}")

        return reduced

    async def _generate_tailored_response(self, outcome, best_slot, participants, negotiation_rounds, history):
        """Generate a tailored response using the LLM client"""
        self.logger.process_step("generate_response", "Generating tailored response with LLM")
        self.logger.debug(
            f"Response parameters: outcome={outcome}, participants={len(participants)}, rounds={negotiation_rounds}")

        context = f"""
Based on a meeting scheduling negotiation:
- Participants: {', '.join(participants)}
- Outcome: {outcome}
- Best slot found:  {best_slot.get('start_time', 'N/A')} - {best_slot.get('end_time', 'N/A')}
- Negotiation rounds: {negotiation_rounds}
- History: {json.dumps([self.reduce_meeting_dict_for_llm(meeting_data=h) for h in history], indent=2)}

Generate a professional, concise response that summarizes the scheduling outcome.
Handle these scenarios:
1. If optimal slot found, be positive and congratulatory
2. If fallback applied, acknowledge the compromise but remain optimistic  
3. If no meeting could be scheduled (best_slot is None), express regret and suggest alternatives like:
   - Extending the search timeframe
   - Being more flexible with preferences
   - Considering virtual meetings
   - Scheduling multiple shorter sessions

Keep the response professional and helpful in all cases.
        """

        self.logger.debug("Sending prompt to LLM for response generation")

        # Use the model client to generate a tailored response
        try:
            response = await self._model_client.create([
                SystemMessage(content="You are a professional meeting scheduler providing clear, concise updates."),
                UserMessage(content=context, source="coordinator")
            ])

            self.logger.debug("Received response from LLM")

            return response.content

        except Exception as e:
            self.logger.error(f"Error generating response with LLM: {str(e)}", exc_info=True)

            # Provide a fallback response in case of LLM failure
            if outcome == "OPTIMAL_FOUND":
                return f"Meeting scheduled successfully for {best_slot.get('start_time', 'N/A')} - {best_slot.get('end_time', 'N/A')} with all participants."

            elif best_slot:
                return f"Meeting scheduled with compromises for {best_slot.get('start_time', 'N/A')} - {best_slot.get('end_time', 'N/A')}."

            else:
                return "Unable to schedule a meeting with the current constraints. Please consider extending the timeframe or adjusting preferences."

    async def on_messages(
            self,
            messages: Sequence[BaseChatMessage],
            cancellation_token: CancellationToken,
    ) -> Response:
        """
        Handles the messages asynchronously and processes a negotiation sequence for scheduling a meeting
        between participants. Uses external agents (analyst and negotiator) to evaluate and optimize
        a proposed schedule, adjusts the schedule iteratively, and determines an optimal slot if possible.

        :param messages: List of TextMessage objects where the last message contains the "participants" list.
        :type messages: list
        :param cancellation_token: Token that allows the ongoing async process to be cancelled.
        :type cancellation_token: Any
        :return: A response containing the negotiation outcome, best slot found (if any), history of
            negotiations, and the total number of negotiation rounds.
        :rtype: Response
        """
        self.logger.process_step("on_messages", "Starting coordination process")

        # Expect the first user TextMessage to contain "participants" list.
        user_msg = messages[-1]
        assert isinstance(user_msg, TextMessage)

        self.logger.data_in("User", "Received scheduling request", user_msg.content)

        try:
            payload = json.loads(user_msg.content)
            participants = payload["participants"]

            self.logger.info(f"Processing request for {len(participants)} participants: {participants}")

            schedule = self.initial_meeting_schedule

            self.logger.debug(f"Initial schedule: {schedule}")

            if 'schedule_date' in payload:
                try:
                    self.logger.debug(f"Parsing schedule date: {payload['schedule_date']}")

                    schedule.schedule_day = datetime.strptime(payload['schedule_date'], '%Y-%m-%d')

                    self.logger.info(f"Set schedule day to {schedule.schedule_day}")
                except ValueError as e:
                    error_msg = f"Error parsing schedule date: Invalid date format. Expected YYYY-MM-DD, got '{payload['schedule_date']}'"

                    self.logger.error(error_msg)

                    return Response(
                        chat_message=TextMessage(
                            source=self.name,
                            content=error_msg
                        ))
                except Exception as e:
                    error_msg = f"Error processing schedule date: {str(e)}"

                    self.logger.error(error_msg, exc_info=True)

                    return Response(
                        chat_message=TextMessage(
                            source=self.name,
                            content=error_msg
                        ))

            negotiation_history = []
            round_num = 0
            optimal_found = False
            best_slot = None
            all_suggestions = []
            inner_messages = []

            self.logger.process_step("negotiation_loop", "Starting negotiation rounds")

            while round_num < self.max_negotiation_rounds and not optimal_found:

                self.logger.info(f"{'-' * 80}")
                self.logger.process_step(f"round_{round_num + 1}",
                                         f"Starting negotiation round {round_num + 1}/{self.max_negotiation_rounds}")
                self.logger.info(f"{'-' * 80}")

                # Call Analyst
                self.logger.process_step("analyst_call", "Requesting available slots from analyst")

                analyst_payload = json.dumps({
                    'participants': participants,
                    'schedule': schedule.model_dump()
                })

                self.logger.data_out("AnalystAgent", "Sending request for available slots")

                analyst_result = await self.analyst_agent.run(task=analyst_payload)
                inner_messages.append(analyst_result.messages[-1])

                slots = json.loads(analyst_result.messages[-1].content)

                self.logger.data_in("AnalystAgent", f"Received {len(slots)} available slots")
                self.logger.debug(f"First slot (if available): {slots[0] if slots else 'No slots'}")

                # Call Negotiator
                self.logger.process_step("negotiator_call", "Requesting negotiation for slots")

                negotiator_prompt = json.dumps({
                    "slots": slots,
                    "participants": participants,
                    "schedule": schedule.model_dump()
                })
                self.logger.data_out("NegotiatorAgent", "Sending slots for negotiation")

                neg_result = await self.negotiator_agent.run(task=negotiator_prompt)
                inner_messages.append(neg_result.messages[-1])

                negotiation = json.loads(neg_result.messages[-1].content)

                self.logger.data_in("NegotiatorAgent",
                                    f"Received negotiation result with outcome: {negotiation.get('outcome')}")

                negotiation_history.append(negotiation)

                self.logger.debug(f"Negotiation round {round_num + 1} outcome: {negotiation.get('outcome')}")

                if 'selected_slot' in negotiation and negotiation['selected_slot'] is not None:
                    all_suggestions.append(negotiation['selected_slot'])

                    self.logger.debug(
                        f"Selected slot: {negotiation['selected_slot'].get('start_time')}-{negotiation['selected_slot'].get('end_time')}")

                # Collect all alternative suggestions
                suggestions = negotiation.get("alternative_suggestions", [])

                if suggestions:
                    all_suggestions.extend(suggestions)

                    self.logger.debug(f"Added {len(suggestions)} alternative suggestions")

                if negotiation.get("outcome") == 'optimal_found':
                    self.logger.decision("negotiation_outcome", "Optimal slot found, ending negotiation",
                                         f"Found in round {round_num + 1}/{self.max_negotiation_rounds}")

                    optimal_found = True
                    best_slot = negotiation.get("selected_slot")

                    break

                self.logger.process_step("schedule_update", "Updating schedule for next round")

                schedule = MeetingSchedule(**negotiation.get('proposed_schedule'))

                self.logger.debug(f"Updated schedule: {schedule}")

                round_num += 1

            # If no optimal found, pick the best from history
            if not optimal_found:
                self.logger.process_step("fallback_selection", "No optimal solution found, selecting best alternative")

                if all_suggestions:
                    self.logger.debug(f"Selecting from {len(all_suggestions)} collected suggestions")

                    # Convert dictionaries to JSON strings for counting
                    suggestion_strings = [json.dumps(suggestion, sort_keys=True) for suggestion in all_suggestions]

                    # Find the most common suggestion

                    most_common_json, count = Counter(suggestion_strings).most_common(1)[0]
                    most_common = json.loads(most_common_json)

                    self.logger.debug(f"Most common suggestion appeared {count} times")

                    confidence_sorted = sorted(all_suggestions, key=lambda x: x['confidence'], reverse=True)
                    highest_confidence = confidence_sorted[0]

                    self.logger.debug(f"Highest confidence suggestion: {highest_confidence['confidence']}")

                    best_slot = most_common if most_common['confidence'] > highest_confidence[
                        'confidence'] else highest_confidence

                    self.logger.decision("fallback_selection",
                                         f"Selected slot with confidence {best_slot['confidence']}",
                                         "Used frequency/confidence comparison")
                else:
                    self.logger.warning("No suggestions available, unable to select a slot")

                    best_slot = None

            self.logger.process_step("response_generation", "Generating final response")

            outcome_type = "OPTIMAL_FOUND" if optimal_found else "FALLBACK" if best_slot else "IMPOSSIBLE"

            self.logger.info(f"Final outcome: {outcome_type} after {round_num} rounds")

            tailored_response = await self._generate_tailored_response(
                outcome=outcome_type,
                best_slot=best_slot or {},
                participants=participants,
                negotiation_rounds=round_num,
                history=negotiation_history
            )

            self.logger.data_out("User", "Sending final scheduling response")

            return Response(
                chat_message=TextMessage(
                    source=self.name,
                    content=tailored_response
                ),
                inner_messages=inner_messages
            )

        except Exception as e:
            self.logger.error(f"Error in coordinator processing: {str(e)}", exc_info=True)
            raise

    async def on_reset(self, cancellation_token):
        self.logger.info("Agent reset requested")
        return None