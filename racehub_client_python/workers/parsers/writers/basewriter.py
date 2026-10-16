import pandas as pd
from racehub_client_python.workers.parsers.writers.sessiondetails import SessionDetails


class BaseWriter(object):
    def __init__(self, filepath, *args, **kwargs):
        self._filepath = filepath
        self._session_details = SessionDetails()
        self._laps = pd.DataFrame()
        self._data = pd.DataFrame()

    @property
    def filepath(self):
        return self._filepath

    @property
    def session_details(self):
        return self._session_details

    @session_details.setter
    def session_details(self, session_details):
        self._session_details = session_details

    @property
    def laps(self):
        return self._laps

    @laps.setter
    def laps(self, laps):
        self._laps = laps

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
