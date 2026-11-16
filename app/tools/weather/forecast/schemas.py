from enum import StrEnum

from pydantic import BaseModel, Field


class Granularity(StrEnum):
    daily = "daily"
    hourly = "hourly"


class WeatherVariable(StrEnum):
    temperature_2m = "temperature_2m"
    apparent_temperature = "apparent_temperature"
    precipitation_probability = "precipitation_probability"
    precipitation = "precipitation"
    wind_speed_10m = "wind_speed_10m"
    relative_humidity_2m = "relative_humidity_2m"
    shortwave_radiation = "shortwave_radiation"
    cloud_cover = "cloud_cover"
    uv_index = "uv_index"


class WeatherInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    days: int = Field(default=3, ge=1, le=7)
    granularity: Granularity = Granularity.daily
    variables: list[WeatherVariable] | None = None
    timezone: str = Field(default="Europe/Madrid", min_length=1, max_length=64)


class WeatherPoint(BaseModel):
    time: str
    values: dict[str, float | int | None]


class Location(BaseModel):
    latitude: float
    longitude: float
    elevation: float | None
    timezone: str


class WeatherOutput(BaseModel):
    location: Location
    granularity: Granularity
    points: list[WeatherPoint]
