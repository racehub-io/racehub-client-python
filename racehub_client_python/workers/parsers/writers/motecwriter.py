# -*- coding: utf-8 -*-
"""
Created on Sat Oct  9 20:02:44 2021

@author: msansoni
"""

from datetime import datetime
import numpy as np
import os.path as osp
import struct
from racehub_client_python.workers.parsers.writers.basewriter import BaseWriter


class LDMotec:
    def __init__(self, header, event, venue, vehicle, weather, channels):
        self.header, self.event, self.venue = header, event, venue
        self.vehicle, self.weather, self.channels = vehicle, weather, channels

    def to_ld_file(self, output_file):
        self.header.to_ld_file(output_file)
        self.event.to_ld_file(output_file, self.header.event_pointer)
        self.venue.to_ld_file(output_file, self.event.venue_pointer)
        self.vehicle.to_ld_file(output_file, self.venue.vehicle_pointer)
        self.weather.to_ld_file(output_file, self.event.weather_pointer)

        for ch in self.channels:
            self.channels[ch].filepath = output_file
            self.channels[ch].to_ld_file()
        for ch in self.channels:
            self.channels[ch].write_channel_data()
        return

    @staticmethod
    def from_ld_file(filepath):
        event = None
        venue = None
        vehicle = None
        weather = None

        header = LDHeader.from_ld_file(filepath)
        if header.event_pointer > 0:
            event = LDEvent.from_ld_file(filepath, header.event_pointer)
            if event.venue_pointer > 0:
                venue = LDVenue.from_ld_file(filepath, event.venue_pointer)
                if venue.vehicle_pointer > 0:
                    vehicle = LDVehicle.from_ld_file(filepath, venue.vehicle_pointer)

            if event.weather_pointer > 0:
                weather = LDWeather.from_ld_file(filepath, event.weather_pointer)

        channels = {}
        next_channel_pointer = header.meta_pointer
        while next_channel_pointer > 0:
            new_channel = LDChannel.from_ld_file(filepath, next_channel_pointer)
            channels[new_channel.channel_name] = new_channel
            next_channel_pointer = new_channel.next_meta_pointer

        return LDMotec(header, event, venue, vehicle, weather, channels)


class LDHeader:
    fmt = "<" + (
        "I4x"  # ldmarker
        "II"  # chann_meta_ptr chann_data_ptr
        "20x"  # ??
        "I"  # event_ptr
        "24x"  # ??
        "HHH"  # unknown static (?) numbers
        "I"  # device serial
        "8s"  # device type
        "H"  # device version
        "HIHH"  # unknown static (?) numbers
        "16s"  # date
        "16x"  # ??
        "16s"  # time
        "16x"  # ??
        "64s"  # driver
        "64s"  # vehicleid
        "64x"  # engineid
        "64s"  # venue
        "64x"  # ??
        "1024x"  # ??
        "I"  # enable "pro logging" (some magic number?)
        "66x"  # 2 + session
        "64s"  # short comment
        "126x"  # ??
    )

    def __init__(
        self,
        meta_pointer,
        data_pointer,
        event_pointer,
        session_date,
        session_time,
        session_driver,
        vehicle_id,
        venue,
        short_comment,
    ):
        self.meta_pointer, self.data_pointer, self.event_pointer = (
            meta_pointer,
            data_pointer,
            event_pointer,
        )
        self.session_date, self.session_time = session_date, session_time
        self.session_driver, self.vehicleid = session_driver, vehicle_id
        self.venue, self.short_comment = venue, short_comment

        try:
            # first, try to decode datatime with seconds
            self.datetime = datetime.strptime(
                "%s %s" % (session_date, session_time), "%d/%m/%Y %H:%M:%S"
            )
        except ValueError:
            self.datetime = datetime.strptime(
                "%s %s" % (session_date, session_time), "%d/%m/%Y %H:%M"
            )

    @staticmethod
    def from_ld_file(filepath):
        with open(filepath, "rb") as ld_file:
            (
                _,
                meta_pointer,
                data_pointer,
                event_pointer,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                session_date,
                session_time,
                session_driver,
                vehicle_id,
                venue,
                _,
                short_comment,
            ) = struct.unpack(LDHeader.fmt, ld_file.read(struct.calcsize(LDHeader.fmt)))

            (
                session_date,
                session_time,
                session_driver,
                vehicle_id,
                venue,
                short_comment,
            ) = map(
                decode_string,
                [
                    session_date,
                    session_time,
                    session_driver,
                    vehicle_id,
                    venue,
                    short_comment,
                ],
            )

            return LDHeader(
                meta_pointer,
                data_pointer,
                event_pointer,
                session_date,
                session_time,
                session_driver,
                vehicle_id,
                venue,
                short_comment,
            )

    def to_ld_file(self, filepath):
        with open(filepath, "wb") as ld_file:
            ld_file.write(
                struct.pack(
                    LDHeader.fmt,
                    0x40,
                    self.meta_pointer,
                    self.data_pointer,
                    self.event_pointer,
                    0x00,
                    0x4240,
                    0x0F,
                    0x2EE7,
                    "ADL".encode(),
                    0xC8,
                    0x80,
                    0x4E,
                    0x64,
                    0x01,
                    self.session_date.encode(),
                    self.session_time.encode(),
                    self.session_driver.encode(),
                    self.vehicleid.encode(),
                    self.venue.encode(),
                    0xD20822,
                    self.short_comment.encode(),
                )
            )


class LDEvent:
    fmt = "<" + (
        "64s"  # event
        "64s"  # session
        "1024s"  # event comment
        "II"  # venue_pointer, weather_pointer
        "1996x"  # padding to venue
    )

    def __init__(self, event, session, comment, venue_pointer, weather_pointer):
        self.event, self.session, self.comment = event, session, comment
        self.venue_pointer, self.weather_pointer = venue_pointer, weather_pointer

    @staticmethod
    def from_ld_file(filepath, event_pointer):
        with open(filepath, "rb") as ld_file:
            ld_file.seek(event_pointer)
            event, session, comment, venue_pointer, weather_pointer = struct.unpack(
                LDEvent.fmt, ld_file.read(struct.calcsize(LDEvent.fmt))
            )

            event, session, comment = map(decode_string, [event, session, comment])

            return LDEvent(event, session, comment, venue_pointer, weather_pointer)

    def to_ld_file(self, filepath, event_pointer):
        with open(filepath, "ab") as ld_file:
            ld_file.seek(event_pointer)
            ld_file.write(
                struct.pack(
                    LDEvent.fmt,
                    self.event.encode(),
                    self.session.encode(),
                    self.comment.encode(),
                    self.venue_pointer,
                    self.weather_pointer,
                )
            )


class LDVenue:
    fmt = "<" + (
        "64s"  # track name
        "2xI"  # track length
        "1028x"  # padding
        "I"  # vehicle_pointer
        "32s"  # category
        "1968x"  # padding to vehicle
    )

    def __init__(self, venue, track_length, vehicle_pointer):
        self.venue, self.track_length, self.vehicle_pointer = (
            venue,
            track_length,
            vehicle_pointer,
        )

    @staticmethod
    def from_ld_file(filepath, venue_pointer):
        with open(filepath, "rb") as ld_file:
            ld_file.seek(venue_pointer)
            venue, track_length, vehicle_pointer, _ = struct.unpack(
                LDVenue.fmt, ld_file.read(struct.calcsize(LDVenue.fmt))
            )

            venue = decode_string(venue)

            return LDVenue(venue, vehicle_pointer)

    def to_ld_file(self, filepath, venue_pointer):
        with open(filepath, "ab") as ld_file:
            ld_file.seek(venue_pointer)
            ld_file.write(
                struct.pack(
                    LDVenue.fmt,
                    self.venue.encode(),
                    self.track_length,
                    self.vehicle_pointer,
                    "".encode(),
                )
            )


class LDVehicle:
    fmt = "<" + (
        "64s"  # vehicleid
        "64s"  # vehicledesc
        "64s"  # vehicleengineid
        "HH"  # weight, tank capacity * 10
        "32s32s"  # vehicletype, vehicle drive type
        "HHHHHHHHHHHHH"  # diff ratio, 10 gears, vehicle track, wheelbase
        "2x1024s"  # vehicle comment
        "4x32s"  # vehicle number
        "1968x"  # padding to weather
    )

    def __init__(self, vehicle_id, weight, vehicle_type, comment, vehicle_number):
        self.vehicle_id, self.weight, self.vehicle_type = (
            vehicle_id,
            weight,
            vehicle_type,
        )
        self.comment, self.vehicle_number = comment, vehicle_number

    @staticmethod
    def from_ld_file(filepath, vehicle_pointer):
        with open(filepath, "rb") as ld_file:
            ld_file.seek(vehicle_pointer)
            (
                vehicle_id,
                _,
                _,
                weight,
                _,
                vehicle_type,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                _,
                comment,
                vehicle_number,
            ) = struct.unpack(
                LDVehicle.fmt, ld_file.read(struct.calcsize(LDVehicle.fmt))
            )

            vehicle_id, vehicle_type, comment, vehicle_number = map(
                decode_string, [vehicle_id, vehicle_type, comment, vehicle_number]
            )

            return LDVehicle(vehicle_id, weight, vehicle_type, comment, vehicle_number)

    def to_ld_file(self, filepath, vehicle_pointer):
        with open(filepath, "ab") as ld_file:
            ld_file.seek(vehicle_pointer)
            ld_file.write(
                struct.pack(
                    LDVehicle.fmt,
                    self.vehicle_id.encode(),
                    "".encode(),
                    "".encode(),
                    self.weight,
                    0x0,
                    self.vehicle_type.encode(),
                    "".encode(),
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    0x0,
                    self.comment.encode(),
                    self.vehicle_number.encode(),
                )
            )


class LDWeather:
    fmt = "<" + (
        "64s"  # sky
        "16s8s"  # air temp, unit
        "16s8s"  # track temp, unit
        "16s8s"  # baro pressure, unit
        "16s8s"  # relative humidity, unit
        "16s8s"  # wind speed, unit
        "64s"  # wind direction
        "1024s"  # wind comment
        "776x"
    )

    def __init__(
        self,
        sky,
        air_temp,
        air_unit,
        track_temp,
        track_unit,
        pressure,
        pressure_unit,
        humidity,
        humidity_unit,
        wind_speed,
        wind_unit,
        wind_direction,
        wind_comment,
    ):
        self.sky = sky
        self.air_temp, self.air_unit = air_temp, air_unit
        self.track_temp, self.track_unit = track_temp, track_unit
        self.pressure, self.pressure_unit = pressure, pressure_unit
        self.humidity, self.humidity_unit = humidity, humidity_unit
        self.wind_speed, self.wind_unit, self.wind_direction, self.wind_comment = (
            wind_speed,
            wind_unit,
            wind_direction,
            wind_comment,
        )

    @staticmethod
    def from_ld_file(filepath, weather_pointer):
        with open(filepath, "rb") as ld_file:
            ld_file.seek(weather_pointer)
            (
                sky,
                air_temp,
                air_unit,
                track_temp,
                track_unit,
                pressure,
                pressure_unit,
                humidity,
                humidity_unit,
                wind_speed,
                wind_unit,
                wind_direction,
                wind_comment,
            ) = struct.unpack(
                LDWeather.fmt, ld_file.read(struct.calcsize(LDWeather.fmt))
            )
            (
                sky,
                air_temp,
                air_unit,
                track_temp,
                track_unit,
                pressure,
                pressure_unit,
                humidity,
                humidity_unit,
                wind_speed,
                wind_unit,
                wind_direction,
                wind_comment,
            ) = map(
                decode_string,
                [
                    sky,
                    air_temp,
                    air_unit,
                    track_temp,
                    track_unit,
                    pressure,
                    pressure_unit,
                    humidity,
                    humidity_unit,
                    wind_speed,
                    wind_unit,
                    wind_direction,
                    wind_comment,
                ],
            )

            return LDWeather(
                sky,
                air_temp,
                air_unit,
                track_temp,
                track_unit,
                pressure,
                pressure_unit,
                humidity,
                humidity_unit,
                wind_speed,
                wind_unit,
                wind_direction,
                wind_comment,
            )

    def to_ld_file(self, filepath, weather_pointer):
        with open(filepath, "ab") as ld_file:
            ld_file.seek(weather_pointer)
            ld_file.write(
                struct.pack(
                    LDWeather.fmt,
                    self.sky.encode(),
                    self.air_temp.encode(),
                    self.air_unit.encode(),
                    self.track_temp.encode(),
                    self.track_unit.encode(),
                    self.pressure.encode(),
                    self.pressure_unit.encode(),
                    self.humidity.encode(),
                    self.humidity_unit.encode(),
                    self.wind_speed.encode(),
                    self.wind_unit.encode(),
                    self.wind_direction.encode(),
                    self.wind_comment.encode(),
                )
            )


class LDChannel:
    fmt = "<" + (
        "IIII"  # prev_addr next_addr data_ptr n_data
        "H"  # channel_index
        "HHH"  # datatype datatype rec_freq
        "hHHH"  # shift scale_mult scale_div dec_places
        "32s"  # name
        "8s"  # short name
        "12s"  # unit
        "ii"  # max_value min_value
        "32x"  # padding
    )

    def __init__(
        self,
        channel_meta_pointer,
        previous_meta_pointer,
        next_meta_pointer,
        data_pointer,
        sample_count,
        channel_index,
        dtype_a,
        dtype,
        freq,
        shift,
        scale_mult,
        scale_div,
        decimal_places,
        channel_name,
        channel_short_name,
        channel_unit,
        max_value,
        min_value,
        filepath,
    ):
        (
            self.channel_meta_pointer,
            self.previous_meta_pointer,
            self.next_meta_pointer,
        ) = (channel_meta_pointer, previous_meta_pointer, next_meta_pointer)
        self.data_pointer, self.sample_count, self.channel_index = (
            data_pointer,
            sample_count,
            channel_index,
        )
        self.dtype_a, self.dtype = dtype_a, dtype
        self.freq, self.shift, self.scale_mult, self.scale_div, self.decimal_places = (
            freq,
            shift,
            scale_mult,
            scale_div,
            decimal_places,
        )
        self.channel_name, self.channel_short_name, self.channel_unit = (
            channel_name,
            channel_short_name,
            channel_unit,
        )
        self.max_value, self.min_value = max_value, min_value
        self.filepath = filepath
        self.samples = []
        self.raw_data = []

    @staticmethod
    def from_ld_file(filepath, meta_pointer):
        with open(filepath, "rb") as ld_file:
            ld_file.seek(meta_pointer)
            (
                previous_meta_pointer,
                next_meta_pointer,
                data_pointer,
                sample_count,
                channel_index,
                dtype_a,
                dtype,
                freq,
                shift,
                scale_mult,
                scale_div,
                decimal_places,
                channel_name,
                channel_short_name,
                channel_unit,
                max_value,
                min_value,
            ) = struct.unpack(
                LDChannel.fmt, ld_file.read(struct.calcsize(LDChannel.fmt))
            )

            channel_name, channel_short_name, channel_unit = map(
                decode_string, [channel_name, channel_short_name, channel_unit]
            )

            return LDChannel(
                meta_pointer,
                previous_meta_pointer,
                next_meta_pointer,
                data_pointer,
                sample_count,
                channel_index,
                dtype_a,
                dtype,
                freq,
                shift,
                scale_mult,
                scale_div,
                decimal_places,
                channel_name,
                channel_short_name,
                channel_unit,
                max_value,
                min_value,
                filepath,
            )

    def to_ld_file(self):
        with open(self.filepath, "ab") as ld_file:
            ld_file.seek(self.channel_meta_pointer)

            # TODO: Fix bugfix for decimal places on fuel load going to -30 for some reason
            if self.decimal_places < 0:
                self.decimal_places = 0

            ld_file.write(
                struct.pack(
                    LDChannel.fmt,
                    self.previous_meta_pointer,
                    self.next_meta_pointer,
                    self.data_pointer,
                    self.sample_count,
                    self.channel_index,
                    self.dtype_a,
                    self.dtype,
                    self.freq,
                    self.shift,
                    self.scale_mult,
                    self.scale_div,
                    self.decimal_places,
                    self.channel_name.encode(),
                    self.channel_short_name.encode(),
                    self.channel_unit.encode(),
                    self.max_value,
                    self.min_value,
                )
            )

    def read_channel_data(self):
        if self.dtype_a in [0, 0x03]:
            data_type = [None, np.int8, np.int16][self.dtype]
        elif self.dtype_a in [0x05]:
            data_type = [np.int32][self.dtype - 4]
        else:
            raise ValueError("DataType %i not recognised!" % self.dtype_a)

        with open(self.filepath, "rb") as ld_file:
            ld_file.seek(self.data_pointer)
            try:
                channel_data = np.fromfile(
                    ld_file, count=self.sample_count, dtype=data_type
                )
                self.raw_data = channel_data
                channel_data = channel_data * (
                    self.scale_mult / self.scale_div / (10 ** (self.decimal_places))
                )
                channel_data = channel_data + self.shift
                self.samples = channel_data
                if len(self.samples) != self.sample_count:
                    raise ValueError("Sample count did not match samples read!")
            except ValueError:
                pass

    def write_channel_data(self):
        with open(self.filepath, "ab") as ld_file:
            ld_file.seek(self.data_pointer)
            ld_file.write(
                b"".join(
                    sample.to_bytes(self.dtype, byteorder="little", signed=True)
                    for sample in self.raw_data
                )
            )


def decode_string(byte_seq):
    try:
        return byte_seq.decode("ascii").strip().rstrip("\0").strip()
    except Exception as e:
        return ""


def build_ldx_file(laps, ldx_details):
    beacon_lines = []
    laps[["start_time", "end_time"]] = laps[["start_time", "end_time"]]
    # Need to have different start time depending on quali or race

    session_start_time = laps["start_time"].iloc[0]

    for index, lap in laps.iterrows():
        beacon_lines.append(
            '     <Marker Version="100" ClassName="BCN" Name="{lap_no:.0f}, id=99" Flags="13" Time="{micro_seconds_end_time_from_start:.18e}"/>'.format(
                lap_no=lap["number"],
                micro_seconds_end_time_from_start=(
                    lap["end_time"] * 1e6 - session_start_time * 1e6
                ),
            )
        )

    ldx_file = [
        '<?xml version="1.0"?>',
        '<LDXFile Locale="English_United Kingdom.1252" DefaultLocale="C" Version="1.6">',
        " <Layers>",
        "  <Layer>",
        "   <MarkerBlock>",
        '    <MarkerGroup Name="Beacons" Index="2">',
    ]

    ldx_file.extend(beacon_lines)
    ldx_file.extend(
        ["    </MarkerGroup>", "   </MarkerBlock>", "   <RangeBlock/>", "  </Layer>"]
    )

    lap_count = len(laps) + 1

    ldx_file.extend(
        ["  <Details>", '   <String Id="Total Laps" Value="%d"/>' % lap_count]
    )
    laps["lap_time"] = laps["end_time"] - laps["start_time"]
    if lap_count > 2:
        # valid_laps = laps[(laps['End Time'] - laps > 0) & (~laps['in_lap']) & (~laps['out_lap'])]
        valid_laps = laps
        fastest_lap = valid_laps[
            valid_laps["lap_time"] == valid_laps["lap_time"].min()
        ].iloc[0]

        fastest_lap_time = fastest_lap["lap_time"]
        fastest_lap_number = fastest_lap["number"] - 1

        mm, ss = divmod(fastest_lap_time, 60)

        int_ss = int(ss)
        fff = int((ss - int_ss) * 1000)

        ldx_file.extend(
            [
                f'   <String Id="Fastest Time" Value="{int(mm)}:{int_ss:02}.{fff:03}"/>',
                f'   <String Id="Fastest Lap" Value="{int(fastest_lap_number)}"/>',
            ]
        )

    for ldx_detail in ldx_details:
        node_type = "String" if ldx_detail["type"] == "string" else "Numeric"

        ldx_file.extend(
            [
                '<{} Id="{}" Value="{}" Units="{}" DPs="{}"/>'.format(
                    node_type,
                    ldx_detail["name"],
                    ldx_detail["value"],
                    ldx_detail["unit"],
                    ldx_detail["decimals"],
                )
            ]
        )

    ldx_file.extend(["  </Details>", " </Layers>", "</LDXFile>"])

    return ldx_file


def max_digits_for_int32(max_value, min_value):
    max_f = 2**31 - 1
    f = max(abs(max_value), abs(min_value))

    if f == 0:
        return 0

    return int(np.floor(np.log10(max_f / f)))


class MotecWriter(BaseWriter):
    def __init__(self, filepath, *args, **kwargs):
        BaseWriter.__init__(self, filepath, *args, **kwargs)

    def write(self, df, parameters, laps, session_details, ldx_details, frequency=25):
        self.data = df
        self.parameters = parameters
        self.laps = laps
        self.session_details = session_details

        [filename, ext] = osp.splitext(self.filepath)

        records = self.process_df(
            df,
            parameters,
        )

        ld = self.create_motec(records, frequency)

        ld.to_ld_file(self.filepath)

        with open("{}.ldx".format(filename), "w") as ldx_file:
            ldx_file.writelines(
                ["%s\n" % line for line in build_ldx_file(laps, ldx_details)]
            )

    def process_df(self, df, parameters):
        records = {}

        for parameter_name in df.columns:
            series = df[parameter_name]
            is_integer = series.dtype.kind in "iu"  # integer, unsigned integer
            decimal_places = (
                0 if is_integer else max_digits_for_int32(series.max(), series.min())
            )
            scaled_values = (series * 10**decimal_places).astype(int)
            max_value = scaled_values.max()
            min_value = scaled_values.min()

            bit_size = 16 if max(abs(min_value), abs(max_value)) < 2**15 else 32

            record = {
                "values": series.values,
                "name": parameter_name,
                "short_name": parameter_name,
                "unit": parameters[parameter_name]["unit"],
                "precision": (
                    series.diff().abs().min() if len(series.unique()) > 1 else 1
                ),
                "is_integer": is_integer,
                "decimal_places": decimal_places,
                "raw_values": scaled_values.tolist(),
                "bit_size": bit_size,
                "max_value": max_value,
                "min_value": min_value,
                "valid": max(abs(min_value), abs(max_value)) - 2**bit_size - 1 < 0,
            }

            record["unit"] = record["unit"] if isinstance(record["unit"], str) else ""

            records[parameter_name] = record

        return records

    def create_motec(self, records, frequency):
        session_details = self.session_details

        channel_size = struct.calcsize(LDChannel.fmt)

        event_pointer = struct.calcsize(LDHeader.fmt)
        venue_pointer = struct.calcsize(LDEvent.fmt) + event_pointer
        vehicle_pointer = struct.calcsize(LDVenue.fmt) + venue_pointer
        weather_pointer = struct.calcsize(LDVehicle.fmt) + vehicle_pointer
        meta_pointer = struct.calcsize(LDWeather.fmt) + weather_pointer

        data_pointer = channel_size * len(records) + meta_pointer

        channel_list = []
        channel_meta = meta_pointer
        channel_data = data_pointer

        for index, record in enumerate(records.values()):
            max_value = record["max_value"]
            min_value = record["min_value"]
            raw_values = record["raw_values"]

            channel = LDChannel(
                channel_meta,
                (0 if index == 0 else channel_meta - channel_size),
                (
                    0
                    if channel_size + 1 == len(records)
                    else channel_meta + channel_size
                ),
                channel_data,
                len(record["values"]),
                index + 1,
                (0x05 if record["bit_size"] == 32 else 0x03),
                (0x04 if record["bit_size"] == 32 else 0x02),
                frequency,
                0,
                1,
                1,
                record["decimal_places"],
                record["name"],
                record["short_name"],
                record["unit"],
                max_value,
                min_value,
                "",
            )

            channel.raw_data = raw_values
            channel_list.append(channel)
            channel_meta = channel_meta + channel_size
            channel_data = channel_data + channel.sample_count * channel.dtype

        session_date = session_details.session_timestamp.strftime("%d/%m/%Y")
        session_time = session_details.session_timestamp.strftime("%H:%M:%S")

        driver_name = session_details.driver_name
        driver_number = session_details.driver_number
        driver_nationality = session_details.driver_nationality
        vehicle_type = session_details.vehicle_type
        vehicle_comment = session_details.vehicle_comment
        track_name = session_details.track_name
        track_length = session_details.track_length

        event_name = session_details.event_name
        session_name = session_details.session_name
        vehicle_weight = 0
        team_name = session_details.team_name
        air_temp = session_details.air_temp
        track_temp = session_details.track_temp

        driver_name = (
            "{driver_name} {team_name} {driver_number} {driver_nationality}".format(
                driver_name=driver_name,
                team_name=team_name,
                driver_number=driver_number,
                driver_nationality=driver_nationality,
            )
        )

        header = LDHeader(
            meta_pointer,
            data_pointer,
            event_pointer,
            session_date,
            session_time,
            driver_name,
            "",
            track_name,
            "RaceHub-Motec",
        )
        event = LDEvent(event_name, session_name, "", venue_pointer, weather_pointer)
        venue = LDVenue(track_name, track_length, vehicle_pointer)
        vehicle = LDVehicle(
            "",
            vehicle_weight,
            vehicle_type,
            vehicle_comment,
            "{0:.0f}".format(driver_number),
        )
        weather = LDWeather(
            "",
            "{0:.0f}".format(air_temp),
            "C",
            "{0:.0f}".format(track_temp),
            "C",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )

        return LDMotec(
            header,
            event,
            venue,
            vehicle,
            weather,
            channels={ch.channel_name: ch for ch in channel_list},
        )
