"""SMARD hourly energy series: MWh per hour; price: EUR/MWh."""
from dataclasses import dataclass

BASE_URL = "https://www.smard.de/app/chart_data"
TIME_ZONE = "Europe/Berlin"
RESOLUTION = "hour"

@dataclass(frozen=True)
class SeriesSpec:
    label: str
    filter_id: int
    region: str = "DE"

SERIES = {
    "biomass": SeriesSpec("Biomass", 4066),
    "hydro": SeriesSpec("Hydropower", 1226),
    "wind_offshore": SeriesSpec("Offshore wind", 1225),
    "wind_onshore": SeriesSpec("Onshore wind", 4067),
    "solar": SeriesSpec("Solar", 4068),
    "other_renewable": SeriesSpec("Other renewables", 1228),
    "lignite": SeriesSpec("Lignite", 1223),
    "hard_coal": SeriesSpec("Hard coal", 4069),
    "gas": SeriesSpec("Natural gas", 4071),
    "pumped_storage": SeriesSpec("Pumped storage", 4070),
    "other_conventional": SeriesSpec("Other conventional", 1227),
    "grid_load": SeriesSpec("Grid load", 410),
    "price": SeriesSpec("Day-ahead price", 4169),
}
RENEWABLE = ("biomass", "hydro", "wind_offshore", "wind_onshore", "solar", "other_renewable")
CONVENTIONAL = ("lignite", "hard_coal", "gas", "pumped_storage", "other_conventional")
GENERATION = RENEWABLE + CONVENTIONAL
COLORS = {
    "biomass": "#52BE91", "hydro": "#48C5CC", "wind_offshore": "#5A7BF3",
    "wind_onshore": "#66B6ED", "solar": "#F3C566", "other_renewable": "#9AD685",
    "lignite": "#AC8474", "hard_coal": "#75839A", "gas": "#9F9BA9",
    "pumped_storage": "#60788A", "other_conventional": "#647182",
    "price": "#AF96FA", "grid_load": "#E6EDF8"
}
