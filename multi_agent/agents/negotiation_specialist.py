from datetime import datetime, time, timedelta
from typing import Any, Optional

import pandas as pd
import logging

from multi_agent.config.models import MeetingSchedule, NegotiationResult, ParticipantPreferences, NegotiationOutcome, \
    SlotInfo, NegotiationStrategy
from multi_agent.logger.AgentLogger import AgentLogger


class NegotiationSpecialistAgent:
    """
    Resolves scheduling conflicts across participants by:
      1) validating slots vs. explicit ParticipantPreferences
      2) iteratively relaxing / modifying MeetingSchedule fields
      3) emitting an outcome (optimal, compromise, impossible)
    """

    def __init__(self, initial_schedule: MeetingSchedule, logger: Optional[AgentLogger] = None):
        self.initial = initial_schedule
        self.logger = logger or AgentLogger(agent_name="NegotiationSpecialist")
        self.logger.info("Initialized negotiation specialist agent")
        self.logger.debug(f"Initial schedule: {initial_schedule}")

    def negotiate_schedule(
            self,
            available_slots: list[SlotInfo],
            participants: dict[str, dict[str, Any]],
            min_score: float = 0.60,
            previous_strategy: NegotiationStrategy = NegotiationStrategy.NONE
    ) -> NegotiationResult:

        self.logger.process_step("negotiate_schedule", "Starting negotiation process")
        self.logger.data_in("ScheduleAnalyst", f"Received {len(available_slots)} available slots")
        self.logger.data_in("Participants", f"Received preferences for {len(participants)} participants")
        self.logger.debug(f"Min score: {min_score}, Previous strategy: {previous_strategy}")

        # split inputs
        self.logger.process_step("preference_processing", "Processing participant preferences")

        prefs: dict[str, ParticipantPreferences] = {
            p: (d["preferences"]
                if isinstance(d["preferences"], ParticipantPreferences)
                else ParticipantPreferences(**d["preferences"]))
            for p, d in participants.items()
        }

        calendars: dict[str, pd.DataFrame] = {p: d["calendar"] for p, d in participants.items()}

        self.logger.debug(f"Processed preferences for participants: {list(prefs.keys())}")

        self.logger.process_step("strict_filter", "Filtering slots by strict preferences")

        # Filter slots using preferences
        ok_slots = [s for s in available_slots if self._slot_respects_all(s, prefs, calendars)]

        self.logger.info(f"Found {len(ok_slots)} slots respecting all preferences")

        # already have acceptable slots?
        if ok_slots:
            ok_slots.sort(key=lambda s: s.confidence, reverse=True)
            best = ok_slots[0] # Slot with best confidence

            outcome = NegotiationOutcome.OPTIMAL_FOUND if best.confidence >= min_score else NegotiationOutcome.COMPROMISE_PROPOSED

            self.logger.decision("slot_selection",
                                 f"Selected slot with confidence {best.confidence}",
                                 f"Outcome: {outcome}")

            result = NegotiationResult(
                outcome=outcome,
                proposed_schedule=self.initial,
                selected_slot=best,
                reasoning="Found slot complying with every explicit preference.",
                alternative_suggestions=ok_slots[1:3]
            )

            self.logger.data_out("Coordinator",
                                 f"Returning {outcome} result with {len(result.alternative_suggestions)} alternatives")

            # Nothing else to check just returns the slot
            return result

        # No Good one, we need to compromise
        self.logger.process_step("iterative_negotiation", "No exact match found, starting iterative negotiation")
        result: Optional[NegotiationResult] = None

        # The strategies are ordered by magnitude of impact, so a stronger strategy continues after the last one, when ALTERNATIVE_DAY is reach all lesser strategies are tested again

        # =======================================================================
        # Duration Adjustment
        # =======================================================================
        if previous_strategy < NegotiationStrategy.DURATION_ADJUSTMENT or previous_strategy >= NegotiationStrategy.ALTERNATIVE_DAY:
            self.logger.process_step("strategy_duration", "Trying duration adjustment strategy")
            result = self._strategy_duration_adjust(available_slots, prefs)

            if result:
                self.logger.decision("strategy_selection", "Duration adjustment successful")
                self.logger.data_out("Coordinator", f"Returning result with strategy {result.strategy_choose}")

                return result

            self.logger.info("Duration adjustment strategy failed to find a solution")

        # =======================================================================
        # Time-of-day Shifting
        # =======================================================================
        if previous_strategy < NegotiationStrategy.TOD_SHIFTING or previous_strategy >= NegotiationStrategy.ALTERNATIVE_DAY:
            self.logger.process_step("strategy_tod", "Trying time-of-day shifting strategy")

            result = self._strategy_time_shift(available_slots, prefs)

            if result:
                self.logger.decision("strategy_selection", "Time-of-day shifting successful")
                self.logger.data_out("Coordinator", f"Returning result with strategy {result.strategy_choose}")

                return result

            self.logger.info("Time-of-day shifting strategy failed to find a solution")

        # =======================================================================
        # Alternative day
        # =======================================================================
        if previous_strategy < NegotiationStrategy.ALTERNATIVE_DAY:
            self.logger.process_step("strategy_alt_day", "Trying alternative day strategy")

            result = self._strategy_alternative_day(available_slots, prefs, calendars)

            if result:
                self.logger.decision("strategy_selection", "Alternative day strategy successful")
                self.logger.data_out("Coordinator", f"Returning result with strategy {result.strategy_choose}")

                return result

            self.logger.info("Alternative day strategy failed to find a solution")

        # =======================================================================
        # Relax constraints
        # =======================================================================
        if previous_strategy < NegotiationStrategy.RELAX_CONSTRAINTS:
            self.logger.process_step("strategy_relax", "Trying constraint relaxation strategy")

            result = self._strategy_relax_hours(available_slots, prefs)

            if result:
                self.logger.decision("strategy_selection", "Constraint relaxation successful")
                self.logger.data_out("Coordinator", f"Returning result with strategy {result.strategy_choose}")

                return result

            self.logger.info("Constraint relaxation strategy failed to find a solution")

        # if still None → impossible
        self.logger.decision("negotiation_outcome", "All strategies exhausted, no solution found")

        result = NegotiationResult(
            outcome=NegotiationOutcome.IMPOSSIBLE,
            proposed_schedule=None,
            selected_slot=None,
            reasoning="Exhausted negotiation rounds – no viable solution.",
            alternative_suggestions=[]
        )

        self.logger.data_out("Coordinator", "Returning IMPOSSIBLE result")

        return result

    def _slot_respects_all(
            self,
            slot: SlotInfo,
            prefs: dict[str, ParticipantPreferences],
            calendars: dict[str, pd.DataFrame]
    ) -> bool:
        """
        Checks if a given time slot respects all participant preferences and constraints.

        This method evaluates a specified time slot against various preferences and
        calendar constraints of all participants. These include time-window prohibitions,
        preferred time of day (morning/afternoon), avoidance of lunch-time meetings, maximum
        meeting duration, and daily meeting caps. If the time slot violates any of these
        criteria for any participant, it is rejected.

        :param slot: The SlotInfo object representing the time slot to evaluate.
        :param prefs: A dictionary where keys are participant IDs (str) and values are
            ParticipantPreferences objects defining constraints and preferences for each
            participant.
        :param calendars: A dictionary where keys are participant IDs (str) and values
            are pandas DataFrame objects representing their schedules, with start times
            of meetings.

        :return: True if the slot respects all preferences and constraints; False otherwise.
        :rtype: bool
        """
        st = datetime.strptime(slot.start_time, "%Y-%m-%d %H:%M")
        et = datetime.strptime(slot.end_time, "%Y-%m-%d %H:%M")
        dur = slot.duration_minutes

        slot_desc = f"{slot.start_time}-{slot.end_time}"
        self.logger.trace(f"Checking slot {slot_desc} against all preferences")

        # lunch interval (12-13)
        lunch = (time(12, 0), time(13, 0))

        for p, pr in prefs.items():
            # time-window prohibitions
            if pr.no_meetings_before and st.time() < pr.no_before():
                self.logger.trace(
                    f"Slot {slot_desc} rejected: before {p}'s no_meetings_before ({pr.no_meetings_before})")

                return False

            if pr.no_meetings_after and et.time() > pr.no_after():
                self.logger.trace(f"Slot {slot_desc} rejected: after {p}'s no_meetings_after ({pr.no_meetings_after})")

                return False

            # morning / afternoon preference
            if pr.prefer_morning and not (6 <= st.hour < 12):
                self.logger.trace(f"Slot {slot_desc} rejected: not morning for {p} who prefers morning")

                return False

            if pr.prefer_afternoon and not (13 <= st.hour < 18):
                self.logger.trace(f"Slot {slot_desc} rejected: not afternoon for {p} who prefers afternoon")

                return False

            # avoid lunch
            if pr.avoid_lunch_time and (lunch[0] <= st.time() < lunch[1] or lunch[0] < et.time() <= lunch[1]):
                self.logger.trace(f"Slot {slot_desc} rejected: overlaps lunch time for {p}")

                return False

            # max duration
            if pr.preferred_max_duration and dur > pr.preferred_max_duration:
                self.logger.trace(f"Slot {slot_desc} rejected: duration {dur} exceeds {p}'s max {pr.preferred_max_duration}")

                return False

            # daily meeting cap
            if pr.max_meetings_per_day:
                df = calendars.get(p)

                if df is not None and not df.empty:
                    day_start = st.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)

                    day_start_dt = pd.to_datetime(day_start.timestamp() * 1000, unit='ms')
                    day_end_dt = pd.to_datetime(day_end.timestamp() * 1000, unit='ms')

                    todays = ((df["start_time"] >= day_start_dt) & (df["start_time"] < day_end_dt))

                    if todays.sum() >= pr.max_meetings_per_day:
                        self.logger.trace(f"Slot {slot_desc} rejected: {p} already has max meetings for the day")

                        return False

        self.logger.trace(f"Slot {slot_desc} ACCEPTED: respects all preferences")

        return True

    # =======================================================================
    # STRATEGIES
    # =======================================================================
    def _strategy_duration_adjust(
            self,
            slots: list[SlotInfo],
            prefs: dict[str, ParticipantPreferences]
    ) -> Optional[NegotiationResult]:
        """
        Adjusts the meeting duration strategy based on the minimum preferred duration
        among participants. This method evaluates the smallest preferred maximum
        duration and determines if the meeting schedule and slots should be adjusted
        to accommodate participants' preferences.

        If no participant specifies a shorter preferred maximum duration, or if all
        available slots are incompatible with the reduced duration, this method
        returns None, indicating no adjustment is needed.

        :param slots: List of available meeting slots with metadata.
            Only slots meeting the smallest allowed duration are considered.
        :type slots: list[SlotInfo]
        :param prefs: Dictionary mapping participant identifiers to their preferences.
        :type prefs: dict[str, ParticipantPreferences]
        :return: The result of the negotiation, including the proposed adjusted
            schedule, selected slot, alternative slot suggestions, and reasoning.
            Returns None if no adjustment is necessary or feasible.
        :rtype: Optional[NegotiationResult]
        """
        self.logger.process_step("duration_adjust", "Attempting duration adjustment strategy")

        # determine smallest allowed duration among participants
        caps = [p.preferred_max_duration for p in prefs.values() if p.preferred_max_duration]

        if not caps:
            self.logger.debug("No participants specified a preferred max duration")

            return None  # nobody needs a shorter meeting

        smallest_cap = min(caps)
        self.logger.debug(f"Smallest preferred max duration: {smallest_cap} minutes")

        if smallest_cap >= self.initial.default_duration:
            self.logger.debug(f"Current duration ({self.initial.default_duration}) already within cap")

            return None  # current duration already within caps

        # Generate new schedule
        new_sched = self.initial.model_copy(deep=True)
        new_sched.default_duration = smallest_cap

        self.logger.info(f"Adjusting duration from {self.initial.default_duration} to {smallest_cap} minutes")

        compat = [
            SlotInfo(**{**s.model_dump(), "duration_minutes": smallest_cap})
            for s in slots
            if s.duration_minutes >= smallest_cap  # slot is long enough
        ]

        self.logger.debug(f"Found {len(compat)} compatible slots with adjusted duration")

        if not compat:
            self.logger.debug("No compatible slots found with adjusted duration")

            return None

        compat.sort(key=lambda s: s.confidence, reverse=True)

        best_slot = compat[0]

        self.logger.info(
            f"Selected best slot: {best_slot.start_time}-{best_slot.end_time} (confidence: {best_slot.confidence})")

        return NegotiationResult(
            outcome=NegotiationOutcome.COMPROMISE_PROPOSED,
            proposed_schedule=new_sched,
            selected_slot=best_slot,
            strategy_choose=NegotiationStrategy.DURATION_ADJUSTMENT,
            reasoning=f"Reduced duration to {smallest_cap} min to respect "
                      "participants' preferred_max_duration.",
            alternative_suggestions=compat[1:3]
        )


    def _strategy_time_shift(
            self,
            slots: list[SlotInfo],
            prefs: dict[str, ParticipantPreferences]
    ) -> Optional[NegotiationResult]:
        """
        Attempts to find a viable slot for scheduling by relaxing certain participant
        preferences such as "prefer morning" or "prefer afternoon". This strategy evaluates
        each given slot by verifying that it adheres to the non-negotiable preferences of
        all participants, while disregarding softer preferences like preferred times of
        the day.

        If a compliant slot is found, the method proposes a new schedule and returns the
        result. The method sorts slots based on confidence, selects the most suitable slot,
        and optionally provides up to two alternative suggestions if available.

        :param slots: List of available time slots to evaluate.
        :param prefs: Dictionary mapping participant identifiers to their scheduling
                      preferences.
        :return: An instance of `NegotiationResult` containing details about the proposed
                 schedule and reasoning for the adjustment. If no compliant slot is found,
                 `None` is returned.
        """
        self.logger.process_step("time_shift", "Attempting time-of-day preference relaxation")
        self.logger.debug(f"Evaluating {len(slots)} slots for time-of-day flexibility")

        # find participants who prefer morning/afternoon
        def ok(slot: SlotInfo) -> bool:
            st = datetime.strptime(slot.start_time, "%Y-%m-%d %H:%M")
            et = datetime.strptime(slot.start_time, "%Y-%m-%d %H:%M")

            lunch = (time(12, 0), time(13, 0))

            for pr in prefs.values():

                if pr.no_meetings_before and st.time() < pr.no_before():
                    return False

                if pr.no_meetings_after and et.time() > pr.no_after():
                    return False

                if pr.avoid_lunch_time and (lunch[0] <= st.time() < lunch[1] or lunch[0] < et.time() <= lunch[1]):
                    return False

                if pr.preferred_max_duration and slot.duration_minutes > pr.preferred_max_duration:
                    return False
            return True

        viable = [s for s in slots if ok(s)]

        self.logger.info(f"Found {len(viable)} viable slots after relaxing time-of-day preferences")

        if not viable:
            self.logger.debug("No viable slots found after relaxing time-of-day preferences")

            return None

        viable.sort(key=lambda s: s.confidence, reverse=True)
        best_slot = viable[0]

        self.logger.debug(f"Best slot: {best_slot.start_time}-{best_slot.end_time} (confidence: {best_slot.confidence})")


        # Generate a new schedule
        new_sched = self.initial.model_copy(deep=True)
        new_sched.schedule_day = datetime.strptime(viable[0].start_time, "%Y-%m-%d %H:%M")

        self.logger.info(f"Adjusted schedule day to {new_sched.schedule_day}")

        return NegotiationResult(
            outcome=NegotiationOutcome.COMPROMISE_PROPOSED,
            proposed_schedule=new_sched,
            selected_slot=viable[0],
            strategy_choose=NegotiationStrategy.TOD_SHIFTING,
            reasoning="Relaxed morning/afternoon *preference* to fit an otherwise compliant slot.",
            alternative_suggestions=viable[1:3]
        )

    def _strategy_alternative_day(
            self,
            slots: list[SlotInfo],
            prefs: dict[str, ParticipantPreferences],
            calendars: dict[str, pd.DataFrame]
    ) -> Optional[NegotiationResult]:
        """
        Attempts to propose an alternative day for meeting scheduling based on participant
        preferences, avoiding weekends, and respecting the maximum number of meetings per
        day for each participant. The function iterates through possible alternative days
        around a base day up to a maximum range defined in the initial configuration.

        :param slots: A list of `SlotInfo` objects that define the available slots for
            scheduling.
        :type slots: list[SlotInfo]
        :param prefs: A dictionary mapping participant names (as strings) to their
            `ParticipantPreferences`.
        :type prefs: dict[str, ParticipantPreferences]
        :param calendars: A dictionary mapping participant names (as strings) to their
            individual calendars represented as pandas DataFrames.
        :type calendars: dict[str, pd.DataFrame]
        :return: A `NegotiationResult` object encapsulating the proposed schedule,
            reasoning, and alternative suggestions, or `None` if no suitable alternative day
            is found within the specified constraints.
        :rtype: Optional[NegotiationResult]
        """
        self.logger.process_step("alternative_day", "Attempting to find an alternative day")

        if self.initial.max_alternative_days == 0:
            self.logger.debug("Alternative days strategy disabled (max_alternative_days=0)")

            return None

        base_day = self.initial.schedule_day

        self.logger.info(f"Searching for alternative days around {base_day.strftime('%Y-%m-%d')}")
        self.logger.debug(f"Max alternative days: {self.initial.max_alternative_days}")

        for offset in range(1, self.initial.max_alternative_days + 1):

            for sign in (+1, -1):
                day = base_day + timedelta(days=sign * offset)

                self.logger.debug(f"Evaluating day: {day.strftime('%Y-%m-%d')} (offset: {sign * offset})")

                if day.weekday() >= 5:  # skip weekends
                    self.logger.debug(f"Skipping weekend day: {day.strftime('%Y-%m-%d')}")

                    continue

                # check max_meetings_per_day for each participant
                day_ok = True

                for p, pref in prefs.items():

                    if not pref.max_meetings_per_day:  # no cap
                        continue

                    df = calendars.get(p)

                    if df is None or df.empty:  # no meetings stored
                        continue

                    start_ms = day.timestamp() * 1000
                    end_ms = (day + timedelta(days=1)).timestamp() * 1000
                    day_start_dt = pd.to_datetime(start_ms, unit='ms')
                    day_end_dt = pd.to_datetime(end_ms, unit='ms')
                    todays = ((df["start_time"] >= day_start_dt) & (df["start_time"] < day_end_dt)).sum()

                    if todays >= pref.max_meetings_per_day:
                        self.logger.debug(f"Participant {p} already has {todays} meetings on {day.strftime('%Y-%m-%d')}")
                        day_ok = False

                        break

                if not day_ok:
                    self.logger.debug(f"Day {day.strftime('%Y-%m-%d')} exceeds meeting caps for at least one participant")

                    continue

                # Generate new schedule
                new_sched = self.initial.model_copy(deep=True)
                new_sched.schedule_day = day

                self.logger.decision("alternative_day",
                                     f"Selected alternative day: {day.strftime('%Y-%m-%d')}",
                                     f"Offset from original: {sign * offset} days")

                return NegotiationResult(
                    outcome=NegotiationOutcome.COMPROMISE_PROPOSED,
                    proposed_schedule=new_sched,
                    selected_slot=None,
                    strategy_choose=NegotiationStrategy.ALTERNATIVE_DAY,
                    reasoning=f"Suggest switching to {day.strftime('%Y-%m-%d')} "
                              "to respect daily-meeting caps.",
                    alternative_suggestions=[]
                )

        self.logger.info(f"No suitable alternative day found within {self.initial.max_alternative_days} days")

        return None


    def _strategy_relax_hours(
            self,
            slots: list[SlotInfo],
            prefs: dict[str, ParticipantPreferences],
    ) -> Optional[NegotiationResult]:
        """
        Implements a strategy to relax constraints and extend corporate working hours slightly
        to accommodate a meeting slot that adheres to participant preferences.

        This function evaluates a list of meeting slots and determines which ones satisfy
        the given participant preferences. It modifies the working hours to extend by 30 minutes
        at both the start and end of the day to accommodate a suitable slot if available. The strategy
        relies on filtering out slots that violate explicit preferences such as maximum
        duration, no-meeting times, or lunch-time avoidance.

        :param slots: List of SlotInfo objects representing meeting time slots.
        :param prefs: Dictionary mapping participant identifiers to their corresponding
                      ParticipantPreferences.
        :return:
            Returns a NegotiationResult object containing the outcome, a proposed schedule,
            the selected slot, the strategy used, and alternative slot suggestions if any
            slots meet the criteria. If no slots are suitable, returns None.
        """
        self.logger.process_step("relax_hours", "Attempting to relax working hours constraints")
        self.logger.debug(f"Evaluating {len(slots)} slots with relaxed working hours")

        widened_slots = []

        for s in slots:
            st = datetime.strptime(s.start_time, "%Y-%m-%d %H:%M")
            et = datetime.strptime(s.end_time, "%Y-%m-%d %H:%M")

            # Accept everything except explicit before/after caps & lunch
            allowed = True
            lunch = (time(12, 0), time(13, 0))

            for pr in prefs.values():

                if pr.no_meetings_before and st.time() < pr.no_before():
                    allowed = False

                    break

                if pr.no_meetings_after and et.time() > pr.no_after():
                    allowed = False

                    break

                if pr.avoid_lunch_time and (lunch[0] <= st.time() < lunch[1] or
                                            lunch[0] < et.time() <= lunch[1]):
                    allowed = False

                    break

                if pr.preferred_max_duration and s.duration_minutes > pr.preferred_max_duration:
                    allowed = False

                    break

            if allowed:
                self.logger.trace(f"Slot {s.start_time}-{s.end_time} accepted with relaxed working hours")
                widened_slots.append(s)

        self.logger.info(f"Found {len(widened_slots)} viable slots with relaxed working hours")

        if not widened_slots:
            self.logger.debug("No viable slots found even with relaxed working hours")

            return None

        widened_slots.sort(key=lambda s: s.confidence, reverse=True)
        best_slot = widened_slots[0]

        self.logger.debug(
            f"Best slot: {best_slot.start_time}-{best_slot.end_time} (confidence: {best_slot.confidence})")


        begin = datetime.strptime(self.initial.working_hours_start, "%H:%M")
        end = datetime.strptime(self.initial.working_hours_end, "%H:%M")

        new_start = (begin - timedelta(minutes=30)).strftime("%H:%M")
        new_end = (end + timedelta(minutes=30)).strftime("%H:%M")

        # Generate new schedule
        new_sched = self.initial.model_copy(deep=True)
        new_sched.working_hours_start = new_start
        new_sched.working_hours_end = new_end

        self.logger.info(
            f"Extended working hours: {self.initial.working_hours_start}-{self.initial.working_hours_end} → {new_start}-{new_end}")

        return NegotiationResult(
            outcome=NegotiationOutcome.COMPROMISE_PROPOSED,
            proposed_schedule=new_sched,
            selected_slot=widened_slots[0],
            strategy_choose=NegotiationStrategy.RELAX_CONSTRAINTS,
            reasoning="Extended corporate working hours by 30 min to accommodate a slot "
                      "respecting all hard preferences.",
            alternative_suggestions=widened_slots[1:3]
        )