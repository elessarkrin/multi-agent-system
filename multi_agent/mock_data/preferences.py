import random

import pandas as pd

from multi_agent.config.models import ParticipantPreferences


def load_preferences(tsv_file: str) -> dict[str, ParticipantPreferences]:
    """
    Parses a TSV file to load participant preferences into a dictionary indexed by the
    participant's name. Each participant's preferences are modeled as a
    `ParticipantPreferences` instance. This function reads the TSV file, processes its
    rows, and instantiates `ParticipantPreferences` objects for storing preferences.

    :param tsv_file: The path to the TSV file containing participant preferences, where
        the first column is 'person' and subsequent columns represent preference attributes.
    :return: A dictionary where the keys are participant names (str) and the values are
        `ParticipantPreferences` instances with parsed preference data.
    :rtype: dict
    """
    df = pd.read_csv(tsv_file, sep='\t')
    preferences_dict = {}

    for _, row in df.iterrows():
        person = row['person']

        # Convert pandas NaN to None and handle data types
        prefs_data = {}
        for col in df.columns:
            if col == 'person':
                continue

            value = row[col]

            # Convert pandas NaN to None
            if pd.isna(value):
                prefs_data[col] = None
            else:
                prefs_data[col] = value

        # Create Pydantic model instance
        preferences_dict[person] = ParticipantPreferences(**prefs_data)

    return preferences_dict

__preferences = load_preferences(tsv_file='../data/participant_preferences.tsv')

def get_preference(name: str) -> ParticipantPreferences:
    """
    Retrieve the preferences associated with a specific participant.

    This function takes the name of a participant and retrieves the
    associated preferences from a predefined dictionary of preferences.

    :param name: The name of the participant whose preferences
                 are being retrieved.
    :type name: str

    :return: The preferences corresponding to the provided participant name.
    :rtype: ParticipantPreferences
    """
    return __preferences[name]

def get_random_participants(max_number: int = 3) -> list[str]:
    """
    Selects a random subset of participants from a list based on the maximum number allowed.
    The function generates a random number of participants between 2 and the specified maximum
    number, and then selects that quantity randomly from the available participants.

    :param max_number: Maximum number of participants that may be selected.
    :type max_number: int
    :return: A list of randomly selected participants' identifiers.
    :rtype: list[str]
    """
    return random.sample(list(__preferences.keys()), random.randint(2, max_number))
