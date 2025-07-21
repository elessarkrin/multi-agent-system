from typing import Union

import pandas as pd

__calendars = pd.read_csv('data/calendar_data.tsv', sep='\t')


def get_person_calendar(person_name: Union[int, str], start_date=None, end_date=None) -> pd.DataFrame:
    """
    Retrieve a calendar of events for a specific person within an optional date range.

    This function filters and returns a DataFrame containing calendar events for the
    specified person (`person_name`) and optionally within a provided date range defined
    by `start_date` and `end_date`. If `person_name` does not exist in the dataset, an
    empty DataFrame with the same structure as the source dataset is returned.

    :param person_name: The identifier for the person, which can be either an integer
        or a string. If it is not prefixed with "Person_", the function will automatically
        append the prefix.
    :type person_name: Union[int, str]
    :param start_date: Optional start date for filtering events. Events starting on or
        after this date will be included in the result. Defaults to None.
    :type start_date: Union[datetime, str, None]
    :param end_date: Optional end date for filtering events. Events starting on or
        before this date will be included in the result. Defaults to None.
    :type end_date: Union[datetime, str, None]
    :return: A filtered DataFrame containing calendar events for the specified person
        within the optional date range. If no events are found, an empty DataFrame
        with the same structure is returned.
    :rtype: pd.DataFrame
    """

    # Convert datetime columns if they're strings
    if __calendars['start_time'].dtype == 'object':
        __calendars['start_time'] = pd.to_datetime(__calendars['start_time'])
        __calendars['end_time'] = pd.to_datetime(__calendars['end_time'])

    if isinstance(person_name, int):
        person_name = str(person_name)

    if not person_name.startswith('Person_'):
        person_name = 'Person_' + person_name

    # Filter by person
    person_calendar = __calendars[__calendars['person'] == person_name].copy()

    # If person doesn't exist, return empty DataFrame with same structure
    if person_calendar.empty:
        return pd.DataFrame(columns=__calendars.columns)

    # Apply date filters if provided
    if start_date:
        person_calendar = person_calendar[person_calendar['start_time'] >= pd.to_datetime(start_date)]
    if end_date:
        person_calendar = person_calendar[person_calendar['start_time'] <= pd.to_datetime(end_date)]

    # Sort by start time
    person_calendar = person_calendar.sort_values('start_time').reset_index(drop=True)

    return person_calendar
