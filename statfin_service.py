from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
import unicodedata

import requests

MUNICIPALITY_CODES = {
    "KU074": "Halsua",
    "KU236": "Kaustinen",
    "KU421": "Lestijärvi",
    "KU849": "Toholampi",
    "KU924": "Veteli",
}

MUNICIPALITIES = ["Halsua", "Kaustinen", "Toholampi", "Lestijärvi", "Veteli"]
MUNICIPALITY_COLORS = {
    "Halsua": "#8884d8",
    "Kaustinen": "#82ca9d",
    "Toholampi": "#ffc658",
    "Lestijärvi": "#ff8042",
    "Veteli": "#a4de6c",
}


@dataclass
class SeriesConfig:
    label_keyword: str
    preferred_labels: tuple[str, ...] = ()


def _get_coords(index: int, sizes: list[int]) -> list[int]:
    remaining = index
    coords = [0] * len(sizes)
    for i in range(len(sizes) - 1, -1, -1):
        coords[i] = remaining % sizes[i]
        remaining //= sizes[i]
    return coords


def _post_jsonstat(url: str, query: dict[str, Any]) -> dict[str, Any] | None:
    try:
        response = requests.post(url, json=query, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def _normalize_label(value: str) -> str:
    base = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", base.lower()).strip()


def _pick_tiedot_index(data: dict[str, Any], dim_name: str, config: SeriesConfig) -> int | None:
    keys = list(data["dimension"][dim_name]["category"]["index"].keys())
    labels = data["dimension"][dim_name]["category"]["label"]

    preferred_norm = [_normalize_label(label) for label in config.preferred_labels]
    keyword_norm = _normalize_label(config.label_keyword)

    contains_candidates: list[tuple[int, str]] = []

    for key in keys:
        label = labels[key]
        label_norm = _normalize_label(label)

        if label_norm in preferred_norm:
            return data["dimension"][dim_name]["category"]["index"][key]

        if keyword_norm and keyword_norm in label_norm:
            score = 0
            if "%" in label:
                score += 1
            if "," in label:
                score += 1
            if "ika" in label_norm or "vuotia" in label_norm:
                score -= 1
            contains_candidates.append((score, key))


    if contains_candidates:
        best_key = sorted(contains_candidates, key=lambda x: x[0], reverse=True)[0][1]
        return data["dimension"][dim_name]["category"]["index"][best_key]

    return None




def _extract_series(data: dict[str, Any], area_dim: str, year_dim: str, config: SeriesConfig):
    dim_ids: list[str] = data["id"]
    sizes: list[int] = data["size"]
    values: list[float | None] = data["value"]

    area_keys = list(data["dimension"][area_dim]["category"]["index"].keys())
    area_labels = data["dimension"][area_dim]["category"]["label"]
    year_keys = list(data["dimension"][year_dim]["category"]["index"].keys())

    tiedot_dim = next((d for d in dim_ids if "tiedot" in d.lower()), None)
    valid_tiedot_idx = _pick_tiedot_index(data, tiedot_dim, config) if tiedot_dim else None

    rows: list[dict[str, Any]] = []
    for i, value in enumerate(values):
        if value is None:
            continue

        coords = _get_coords(i, sizes)
        dim_map = {dim: coords[idx] for idx, dim in enumerate(dim_ids)}

        if tiedot_dim and valid_tiedot_idx is not None and dim_map[tiedot_dim] != valid_tiedot_idx:
            continue

        area_code = area_keys[dim_map[area_dim]]
        municipality = area_labels[area_code]
        if municipality not in MUNICIPALITIES:
            continue

        year = int(year_keys[dim_map[year_dim]])
        rows.append({"year": year, "municipality": municipality, "value": float(value)})

    return rows


def _rows_to_frame(rows):
    import pandas as pd

    if not rows:
        return pd.DataFrame(columns=["year", "municipality", "value"])
    frame = pd.DataFrame(rows)
    frame = frame.groupby(["year", "municipality"], as_index=False)["value"].sum()
    return frame.sort_values(["year", "municipality"]).reset_index(drop=True)


def fetch_population_data():
    url = "https://pxdata.stat.fi/PxWeb/api/v1/fi/Kuntien_avainluvut/2025/kuntien_avainluvut_2025_aikasarja.px"
    query = {
        "query": [
            {"code": "Alue", "selection": {"filter": "item", "values": list(MUNICIPALITY_CODES.keys())}},
            {"code": "Tiedot", "selection": {"filter": "all", "values": ["*"]}},
            {"code": "Vuosi", "selection": {"filter": "item", "values": ["2020", "2021", "2022", "2023", "2024"]}},
        ],
        "response": {"format": "json-stat2"},
    }
    data = _post_jsonstat(url, query)
    if not data:
        return _rows_to_frame([])

    rows = _extract_series(data, "Alue", "Vuosi", SeriesConfig(label_keyword="Väkiluku"))
    return _rows_to_frame(rows)


def fetch_employment_data():
    return _fetch_key_figures_series(
        SeriesConfig(
            label_keyword="työllisyysaste",
            preferred_labels=("Työllisyysaste, %",),
        )
    )


def fetch_unemployment_data():
    return _fetch_key_figures_series(
        SeriesConfig(
            label_keyword="työttömyysaste",
            preferred_labels=("Työttömyysaste, %",),
        )
    )


def fetch_dependency_ratio_data():
    return _fetch_key_figures_series(
        SeriesConfig(
            label_keyword="Väestöllinen huoltosuhde",
            preferred_labels=("Väestöllinen huoltosuhde",),
        )
    )


def _fetch_key_figures_series(config: SeriesConfig):
    url = "https://pxdata.stat.fi/PxWeb/api/v1/fi/Kuntien_avainluvut/2025/kuntien_avainluvut_2025_aikasarja.px"
    query = {
        "query": [
            {"code": "Alue", "selection": {"filter": "item", "values": list(MUNICIPALITY_CODES.keys())}},
            {"code": "Tiedot", "selection": {"filter": "all", "values": ["*"]}},
            {"code": "Vuosi", "selection": {"filter": "item", "values": ["2020", "2021", "2022", "2023", "2024"]}},
        ],
        "response": {"format": "json-stat2"},
    }

    data = _post_jsonstat(url, query)
    if not data:
        return _rows_to_frame([])

    rows = _extract_series(data, "Alue", "Vuosi", config)
    return _rows_to_frame(rows)
