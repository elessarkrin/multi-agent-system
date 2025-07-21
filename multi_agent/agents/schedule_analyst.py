from datetime import datetime, time, timedelta
from typing import Any, Optional

import pandas as pd
import logging as python_logging

from multi_agent.config.models import SlotInfo
from multi_agent.logger.AgentLogger import AgentLogger


class ScheduleAnalystAgent:
    """
    Analyzes calendars and proposes meeting slots.
    Takes 2-3 calendars with busy slots loaded as pandas DataFrames.
    """

    def __init__(self, working_hours: tuple = ('09:00', '17:00'), timezone: str = 'UTC',
                 min_slot_duration: int = 30, logger: Optional[AgentLogger] = None):
        """
        Args:
            working_hours: Tuple of ('HH:MM', 'HH:MM') for working hours in 24-hour format
            timezone: Timezone string for scheduling
            min_slot_duration: Minimum meeting duration in minutes
            logger: Optional AgentLogger instance for logging
        """
        self.working_hours = working_hours
        self.timezone = timezone
        self.min_slot_duration = min_slot_duration

        self.logger = logger or AgentLogger(agent_name="ScheduleAnalyst", log_level=python_logging.INFO)
        self.logger.info(f"Initialized ScheduleAnalyst with working hours {working_hours}, timezone {timezone}")
        self.logger.debug(f"Min slot duration: {min_slot_duration} minutes")

    def _parse_time(self, tstr: str) -> time:
        """Parse 'HH:MM' string to a time object."""
        return datetime.strptime(tstr, '%H:%M').time()

    def find_free_slots(self,
                        participants_data: dict[str, dict],
                        meeting_duration: int = 60,
                        schedule_day: datetime = None
                        ) -> list[SlotInfo]:
        """
        Find available meeting slots across multiple calendars.

        Args:
            participants_data: Dictionary of participant data including calendars and preferences
            meeting_duration: Duration in minutes
            schedule_day: Day to schedule for (defaults to today)

        Returns:
            List of proposed meeting slots
        """
        self.logger.process_step("find_free_slots", "Finding available meeting slots")
        self.logger.data_in("Main", f"Received data for {len(participants_data)} participants")
        self.logger.debug(f"Meeting duration: {meeting_duration} minutes")

        start_hour, end_hour = self.working_hours
        start_time_obj = self._parse_time(start_hour)
        end_time_obj = self._parse_time(end_hour)

        # Set default date range if not provided
        if schedule_day is None:
            start_date = datetime.now()
            self.logger.debug("No schedule day provided, using current date")
        else:
            start_date = schedule_day
            self.logger.debug(f"Using provided schedule day: {start_date.strftime('%Y-%m-%d')}")

        start_date = start_date.replace(hour=start_time_obj.hour, minute=start_time_obj.minute, second=0, microsecond=0)
        end_date = start_date.replace(hour=end_time_obj.hour, minute=end_time_obj.minute, second=0, microsecond=0)

        self.logger.debug(
            f"Search period: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')}")

        # Load and combine all calendar data
        self.logger.process_step("calendar_processing", "Processing participant calendars")

        all_busy_slots = []

        for participant, participant_data in participants_data.items():
            calendar_df = participant_data['calendar']

            self.logger.debug(
                f"Processing calendar for {participant} with {len(calendar_df) if not calendar_df.empty else 0} entries")

            all_busy_slots.append(calendar_df)

        # Combine all busy slots
        combined_busy = pd.concat(all_busy_slots, ignore_index=True) if all_busy_slots else pd.DataFrame()

        self.logger.info(f"Combined calendar has {len(combined_busy)} busy slots")

        # Generate potential time slots, from schedule day and next day (only working days)
        self.logger.process_step("slot_generation", "Generating potential time slots")

        potential_slots = self._generate_time_slots(start_date, end_date, meeting_duration)

        self.logger.info(f"Generated {len(potential_slots)} potential time slots")

        # Filter out conflicting slots
        self.logger.process_step("slot_filtering", "Filtering out conflicting slots")

        available_slots = self._filter_available_slots(
            potential_slots=potential_slots,
            busy_df=combined_busy
        )

        self.logger.info(f"Found {len(available_slots)} available slots after filtering conflicts")

        # Score and rank slots
        self.logger.process_step("slot_scoring", "Scoring and ranking available slots")

        scored_slots = self._score_slots(
            available_slots=available_slots,
            participants_data=participants_data,
            duration=meeting_duration
        )

        self.logger.info(f"Scored {len(scored_slots)} slots based on participant preferences")

        # Log top slots
        if scored_slots:
            top_slots = scored_slots[:3] if len(scored_slots) >= 3 else scored_slots

            self.logger.info(f"Top slot has confidence score of {top_slots[0].confidence:.2f}")

            for i, slot in enumerate(top_slots):
                self.logger.debug(f"Slot {i + 1}: {slot.start_time} - {slot.end_time} (Score: {slot.score:.2f})")
        else:
            self.logger.warning("No available slots found after analysis")

        self.logger.data_out("Main", f"Returning {len(scored_slots)} scored slots")

        return scored_slots

    def _generate_time_slots(self, start_date: datetime, end_date: datetime, duration: int) -> list[
        tuple[datetime, datetime]]:
        """
        Generates a list of time slots within the specified date range and duration. The method skips weekends,
        ensuring time slot generation occurs from Monday to Friday only. Each generated time slot starts at
        a given time and lasts for the specified duration. Time slots are created at specified intervals
        and fit within the overall provided range.

        :param start_date: The starting datetime for time slot generation.
        :type start_date: datetime
        :param end_date: The ending datetime for time slot generation.
        :type end_date: datetime
        :param duration: The duration of each time slot in minutes.
        :type duration: int
        :return: A list of tuples where each tuple contains the start and end datetime for each time slot.
        :rtype: list[tuple[datetime, datetime]]
        """
        self.logger.debug(f"Generating time slots from {start_date} to {end_date} with duration {duration} minutes")

        slots = []
        current_time = start_date

        while current_time < end_date:

            if current_time.weekday() < 5:  # Monday = 0, Friday = 4

                while current_time + timedelta(minutes=duration) <= end_date:
                    slots.append((current_time, current_time + timedelta(minutes=self.min_slot_duration)))
                    current_time += timedelta(minutes=self.min_slot_duration)

            else:
                self.logger.debug(f"Skipping weekend day: {current_time.strftime('%Y-%m-%d')}")

                break

        self.logger.debug(f"Generated {len(slots)} potential time slots")

        return slots

    def _filter_available_slots(self, potential_slots: list[tuple[datetime, datetime]],
                                busy_df: pd.DataFrame) -> list[tuple[datetime, datetime]]:
        """
        Filters the list of potential time slots by excluding those that conflict with busy periods
        defined in the provided DataFrame. This method checks the overlap between the provided
        time slots and the busy periods to return only the available slots.

        :param potential_slots: A list of tuples, where each tuple contains a start and end time
            (datetime, datetime) representing the potential time slots to check.
        :param busy_df: A pandas DataFrame that contains busy time periods with 'start_time'
            and 'end_time' columns representing the start and end time of each busy period.
        :return: A list of tuples, where each tuple contains a start and end time
            (datetime, datetime) representing the available slots that do not conflict with
            the busy periods.
        """
        self.logger.debug(
            f"Filtering {len(potential_slots)} potential slots against {len(busy_df) if not busy_df.empty else 0} busy periods")

        if busy_df.empty:
            self.logger.debug("No busy slots found, all potential slots are available")

            return potential_slots

        available_slots = []

        for slot_start, slot_end in potential_slots:
            # Check for conflicts
            conflicts = busy_df[(busy_df['start_time'] < slot_end) & (busy_df['end_time'] > slot_start)]

            if conflicts.empty:
                available_slots.append((slot_start, slot_end))

        self.logger.debug(f"Found {len(available_slots)} slots without conflicts")

        return available_slots

    def _score_slots(
            self,
            available_slots: list[tuple[datetime, datetime]],
            participants_data: dict[str, dict],
            duration: int,
    ) -> list[SlotInfo]:
        """
        Evaluates and scores available time slots for scheduling based on participant data
        and slot duration. Each slot is annotated with calculated scores, notes, and
        additional metadata for scheduling optimization.

        :param available_slots: A list of tuples representing the available time slots.
            Each tuple contains two datetime objects: the start and end of the slot.
        :param participants_data: A dictionary where keys are participant names (str) and values
            are dictionaries containing participant-specific data necessary for score calculation.
        :param duration: An integer representing the desired duration of the event in minutes.
        :return: A list of SlotInfo objects, each representing a scored and annotated time
            slot, sorted in descending order of score.
        """
        self.logger.debug(f"Scoring {len(available_slots)} available slots")

        scored_slots = []

        for slot_start, slot_end in available_slots:
            self.logger.trace(
                f"Scoring slot: {slot_start.strftime('%Y-%m-%d %H:%M')} - {slot_end.strftime('%Y-%m-%d %H:%M')}")

            participant_scores = []
            participant_notes = {}

            for participant, participant_data in participants_data.items():

                score, notes = self._calculate_slot_score_with_notes(
                    slot_start=slot_start,
                    slot_end=slot_end,
                    duration=duration,
                    participant_name=participant,
                    participant_data=participant_data
                )

                participant_scores.append(score)
                participant_notes[participant] = notes

                self.logger.trace(f"Participant {participant} score: {score:.2f}")

            avg_score = sum(participant_scores) / len(participant_scores) if participant_scores else 0.0

            self.logger.trace(f"Average score for slot: {avg_score:.2f}")

            slot_info = SlotInfo(
                start_time=slot_start.strftime('%Y-%m-%d %H:%M'),
                end_time=slot_end.strftime('%Y-%m-%d %H:%M'),
                duration_minutes=duration,
                confidence=min(avg_score, 1.0),
                participants=list(participants_data.keys()),
                participant_scores=participant_scores,
                participant_notes=participant_notes,
                notes=self._generate_slot_notes(slot_start, avg_score),
                day_of_week=slot_start.strftime('%A'),
                score=avg_score
            )

            scored_slots.append(slot_info)

        scored_slots.sort(key=lambda x: x.score, reverse=True)

        self.logger.debug(f"Sorted {len(scored_slots)} slots by score")

        return scored_slots

    def _calculate_slot_score_with_notes(
            self,
            slot_start: datetime,
            slot_end: datetime,
            duration: int,
            participant_name: str,
            participant_data: dict[str, Any]
    ) -> tuple[float, list[str]]:
        """
        Calculates the suitability score and notes for a meeting slot for a specified participant
        based on their preferences and existing schedule.

        The function evaluates several aspects of the participant's preferences, including time constraints,
        preferred meeting times, preferred meeting durations, avoidance of lunch hours, and maximum number of
        meetings per day. It also considers the participant's calendar for conflicting meetings and busy periods.
        Each factor influences the overall score, which is clamped between 0.0 and 1.0. Additionally,
        detailed notes are generated to explain how each preference is respected or violated.

        :param slot_start: The starting time of the proposed meeting slot.
        :type slot_start: datetime
        :param slot_end: The ending time of the proposed meeting slot.
        :type slot_end: datetime
        :param duration: The duration of the meeting slot in minutes.
        :type duration: int
        :param participant_name: The name of the participant being assessed.
        :type participant_name: str
        :param participant_data: Information about the participant, including preferences and schedule.
        :type participant_data: dict[str, Any]
        :return: A tuple containing the final suitability score (float) and a list of explanatory notes (list[str]).
        :rtype: tuple[float, list[str]]
        """

        self.logger.trace(f"Calculating score for {participant_name} at {slot_start.strftime('%H:%M')}")

        score = 0.5  # Base score
        notes = []
        prefs = participant_data['preferences']
        calendar = participant_data['calendar']

        # Respect no_meetings_before and no_meetings_after
        if prefs.no_meetings_before:

            before = int(prefs.no_meetings_before.split(':')[0]) if isinstance(prefs.no_meetings_before, str) else int(
                prefs.no_meetings_before)

            if slot_start.hour < before:
                score -= 0.3
                notes.append(
                    f"[{participant_name}] Slot starts at {slot_start.hour}:00, but prefers no meetings before {prefs.no_meetings_before}")

                self.logger.trace(f"{participant_name}: Violated no_meetings_before preference")

            else:
                notes.append(
                    f"[{participant_name}] Slot respects no-meetings-before preference of {prefs.no_meetings_before}")

        if prefs.no_meetings_after:
            after = int(prefs.no_meetings_after.split(':')[0]) if isinstance(prefs.no_meetings_after, str) else int(
                prefs.no_meetings_after)

            if slot_end.hour > after:
                score -= 0.3
                notes.append(
                    f"[{participant_name}] Slot ends at {slot_end.hour}:00, but prefers no meetings after {prefs.no_meetings_after}")

                self.logger.trace(f"{participant_name}: Violated no_meetings_after preference")

            else:
                notes.append(
                    f"[{participant_name}] Slot respects no-meetings-after preference of {prefs.no_meetings_after}")

        # Prefer morning/afternoon
        if prefs.prefer_morning:

            if 6 <= slot_start.hour < 12:
                score += 0.2
                notes.append(f"[{participant_name}] Slot aligns with morning preference")

                self.logger.trace(f"{participant_name}: Morning preference satisfied")

            else:
                notes.append(f"[{participant_name}] Slot does not align with morning preference")

                self.logger.trace(f"{participant_name}: Morning preference not satisfied")

        if prefs.prefer_afternoon:

            if 13 <= slot_start.hour < 18:
                score += 0.2
                notes.append(f"[{participant_name}] Slot aligns with afternoon preference")

                self.logger.trace(f"{participant_name}: Afternoon preference satisfied")

            else:
                notes.append(f"[{participant_name}] Slot does not align with afternoon preference")

                self.logger.trace(f"{participant_name}: Afternoon preference not satisfied")

        # Avoid lunch time
        if prefs.avoid_lunch_time:

            if 12 <= slot_start.hour < 13 or 12 < slot_end.hour <= 13:
                score -= 0.2
                notes.append(f"[{participant_name}] Slot conflicts with lunch time avoidance preference")

                self.logger.trace(f"{participant_name}: Lunch time conflict detected")

            else:
                notes.append(f"[{participant_name}] Slot respects lunch time avoidance preference")

        # Preferred duration
        if prefs.preferred_max_duration:

            if duration <= prefs.preferred_max_duration:
                score += 0.1
                notes.append(
                    f"[{participant_name}] Meeting duration {duration} minutes is within preferred maximum of {prefs.preferred_max_duration} minutes")

                self.logger.trace(f"{participant_name}: Duration preference satisfied")

            else:
                notes.append(
                    f"[{participant_name}] Meeting duration {duration} minutes exceeds preferred maximum of {prefs.preferred_max_duration} minutes")

                self.logger.trace(f"{participant_name}: Duration exceeds preference")

        # Check calendar for busy periods
        if calendar is not None and not calendar.empty:
            slot_date = slot_start.date()
            same_day_meetings = calendar[calendar['start_time'].dt.date == slot_date]

            meeting_count = len(same_day_meetings)

            if prefs.max_meetings_per_day and meeting_count >= prefs.max_meetings_per_day:
                score -= 0.3
                notes.append(
                    f"[{participant_name}] Already has {meeting_count} meetings on this day, reaching maximum limit of {prefs.max_meetings_per_day}")

                self.logger.trace(f"{participant_name}: Max meetings per day reached ({meeting_count})")

            elif meeting_count >= 4:
                score -= 0.2
                notes.append(
                    f"[{participant_name}] Already has {meeting_count} meetings on this day, which is quite busy")

                self.logger.trace(f"{participant_name}: Has {meeting_count} meetings (quite busy)")

            elif meeting_count >= 2:
                score -= 0.1
                notes.append(f"[{participant_name}] Already has {meeting_count} meetings on this day, moderately busy")

                self.logger.trace(f"{participant_name}: Has {meeting_count} meetings (moderately busy)")

            elif meeting_count == 1:
                notes.append(f"[{participant_name}] Has {meeting_count} other meeting on this day, manageable schedule")

                self.logger.trace(f"{participant_name}: Has 1 meeting (manageable)")

            else:
                notes.append(f"[{participant_name}] No other meetings scheduled on this day")

                self.logger.trace(f"{participant_name}: No other meetings this day")


            # Check for meetings close to this slot
            buffer_minutes = 15

            close_meetings = calendar[
                ((calendar['end_time'] > slot_start - timedelta(minutes=buffer_minutes)) &
                 (calendar['end_time'] <= slot_start)) |
                ((calendar['start_time'] >= slot_end) &
                 (calendar['start_time'] < slot_end + timedelta(minutes=buffer_minutes)))
                ]

            if not close_meetings.empty:
                score -= 0.1
                notes.append(
                    f"[{participant_name}] Has meetings within {buffer_minutes} minutes of this slot, creating back-to-back scheduling")

                self.logger.trace(f"{participant_name}: Has back-to-back meetings")

            else:
                notes.append(f"[{participant_name}] Has adequate buffer time around this slot")

        # Add a general time assessment
        hour = slot_start.hour
        if 10 <= hour <= 11:
            notes.append("Time slot is in optimal mid-morning period")

        elif 14 <= hour <= 15:
            notes.append("Time slot is in good early afternoon period")

        elif hour == 9:
            notes.append("Time slot is early morning")

        elif hour >= 16:
            notes.append("Time slot is in late afternoon")

        elif hour < 9:
            notes.append("Time slot is very early morning")

        # Clamp score between 0 and 1
        final_score = max(0.0, min(score, 1.0))

        self.logger.trace(f"Final score for {participant_name}: {final_score:.2f}")

        # Add final assessment
        if final_score > 0.8:
            notes.append("Overall assessment: Excellent fit for this participant")

        elif final_score > 0.6:
            notes.append("Overall assessment: Good fit for this participant")

        elif final_score > 0.4:
            notes.append("Overall assessment: Acceptable fit for this participant")

        else:
            notes.append("Overall assessment: Poor fit for this participant")

        return final_score, notes

    def _generate_slot_notes(self, slot_time: datetime, score: float) -> str:
        """Generate general explanatory notes for a time slot."""
        self.logger.trace(f"Generating notes for slot at {slot_time.strftime('%H:%M')} with score {score:.2f}")

        notes = []

        hour = slot_time.hour

        if 10 <= hour <= 11:
            notes.append("Optimal mid-morning time")

        elif 14 <= hour <= 15:
            notes.append("Good early afternoon slot")

        elif hour == 9:
            notes.append("Early morning - may suit early risers")

        elif hour >= 16:
            notes.append("Late afternoon slot")

        weekday = slot_time.weekday()

        if weekday in [1, 2, 3]:
            notes.append("Mid-week scheduling")

        elif weekday == 0:
            notes.append("Monday scheduling")

        elif weekday == 4:
            notes.append("Friday scheduling")

        if score > 0.8:
            notes.append("High confidence slot")

        elif score > 0.6:
            notes.append("Good availability")

        else:
            notes.append("Available but suboptimal timing")

        return "; ".join(notes) if notes else "Available time slot"
