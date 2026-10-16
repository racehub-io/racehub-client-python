from .packetheader import PacketHeader
from .packetmotiondata import PacketMotionData
from .packetsessiondata import PacketSessionData
from .packetlapdata import PacketLapData
from .packeteventdata import PacketEventData
from .packetparticipantsdata import PacketParticipantsData
from .packetcarsetupdata import PacketCarSetupData
from .packetcartelemetrydata import PacketCarTelemetryData
from .packetcarstatusdata import PacketCarStatusData
from .packetfinalclassification import PacketFinalClassificationData
from .packetlobbyinfodata import PacketLobbyInfoData
from .packetcardamagedata import PacketCarDamageData
from .packetsessionhistorydata import PacketSessionHistoryData
from .packettyresetsdata import PacketTyreSetsData
from .packetmotionexdata import PacketMotionExData

from .f12023parser import F12023Parser


def get_column_types():
    return {
        **PacketCarDamageData().columns(),
        **PacketCarSetupData().columns(),
        **PacketCarStatusData().columns(),
        **PacketCarTelemetryData().columns(),
        # **PacketEventData().columns(),
        **PacketFinalClassificationData().columns(),
        **PacketLapData().columns(),
        **PacketLobbyInfoData().columns(),
        **PacketMotionData().columns(),
        **PacketMotionExData().columns(),
        **PacketParticipantsData().columns(),
        **PacketSessionData().columns(),
        **PacketSessionHistoryData().columns(),
        **PacketTyreSetsData().columns(),
    }
