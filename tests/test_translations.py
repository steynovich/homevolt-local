"""Tests for translation files."""

import json
from pathlib import Path

import pytest

TRANSLATIONS_PATH = (
    Path(__file__).parent.parent / "custom_components" / "homevolt_local" / "translations"
)
STRINGS_PATH = (
    Path(__file__).parent.parent / "custom_components" / "homevolt_local" / "strings.json"
)

EXPECTED_LANGUAGES = ["de", "en", "nb", "nl", "sv"]


def get_all_keys(d: dict, prefix: str = "") -> set[str]:
    """Recursively get all keys from a nested dictionary."""
    keys = set()
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        keys.add(full_key)
        if isinstance(value, dict):
            keys.update(get_all_keys(value, full_key))
    return keys


class TestTranslationFiles:
    """Test translation file structure and content."""

    def test_all_expected_languages_exist(self) -> None:
        """Test that all expected language files exist."""
        for lang in EXPECTED_LANGUAGES:
            lang_file = TRANSLATIONS_PATH / f"{lang}.json"
            assert lang_file.exists(), f"Missing translation file: {lang}.json"

    def test_strings_json_exists(self) -> None:
        """Test that strings.json exists."""
        assert STRINGS_PATH.exists(), "strings.json not found"

    @pytest.mark.parametrize("lang", EXPECTED_LANGUAGES)
    def test_translation_is_valid_json(self, lang: str) -> None:
        """Test that each translation file is valid JSON."""
        lang_file = TRANSLATIONS_PATH / f"{lang}.json"
        with open(lang_file, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_strings_json_is_valid_json(self) -> None:
        """Test that strings.json is valid JSON."""
        with open(STRINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_english_matches_strings_json(self) -> None:
        """Test that en.json has the same structure as strings.json."""
        with open(STRINGS_PATH, encoding="utf-8") as f:
            strings_data = json.load(f)
        with open(TRANSLATIONS_PATH / "en.json", encoding="utf-8") as f:
            en_data = json.load(f)

        strings_keys = get_all_keys(strings_data)
        en_keys = get_all_keys(en_data)

        assert strings_keys == en_keys, (
            f"Mismatch between strings.json and en.json.\n"
            f"Only in strings.json: {strings_keys - en_keys}\n"
            f"Only in en.json: {en_keys - strings_keys}"
        )

    @pytest.mark.parametrize("lang", EXPECTED_LANGUAGES)
    def test_translation_has_same_keys_as_english(self, lang: str) -> None:
        """Test that each translation has the same keys as English."""
        with open(TRANSLATIONS_PATH / "en.json", encoding="utf-8") as f:
            en_data = json.load(f)
        with open(TRANSLATIONS_PATH / f"{lang}.json", encoding="utf-8") as f:
            lang_data = json.load(f)

        en_keys = get_all_keys(en_data)
        lang_keys = get_all_keys(lang_data)

        assert en_keys == lang_keys, (
            f"Key mismatch in {lang}.json.\n"
            f"Missing keys: {en_keys - lang_keys}\n"
            f"Extra keys: {lang_keys - en_keys}"
        )

    @pytest.mark.parametrize("lang", EXPECTED_LANGUAGES)
    def test_translation_values_not_empty(self, lang: str) -> None:
        """Test that translation values are not empty strings."""
        with open(TRANSLATIONS_PATH / f"{lang}.json", encoding="utf-8") as f:
            data = json.load(f)

        def check_values(d: dict, path: str = "") -> list[str]:
            """Check for empty string values."""
            empty = []
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                if isinstance(value, dict):
                    empty.extend(check_values(value, current_path))
                elif isinstance(value, str) and value == "":
                    empty.append(current_path)
            return empty

        empty_values = check_values(data)
        assert not empty_values, f"Empty values in {lang}.json: {empty_values}"

    @pytest.mark.parametrize("lang", EXPECTED_LANGUAGES)
    def test_translation_preserves_placeholders(self, lang: str) -> None:
        """Test that translations preserve placeholders like {host}."""
        with open(TRANSLATIONS_PATH / "en.json", encoding="utf-8") as f:
            en_data = json.load(f)
        with open(TRANSLATIONS_PATH / f"{lang}.json", encoding="utf-8") as f:
            lang_data = json.load(f)

        def extract_placeholders(s: str) -> set[str]:
            """Extract {placeholder} patterns from a string."""
            import re

            return set(re.findall(r"\{(\w+)\}", s))

        def check_placeholders(en_dict: dict, lang_dict: dict, path: str = "") -> list[str]:
            """Check that placeholders match between translations."""
            mismatches = []
            for key, en_value in en_dict.items():
                current_path = f"{path}.{key}" if path else key
                lang_value = lang_dict.get(key)
                if isinstance(en_value, dict) and isinstance(lang_value, dict):
                    mismatches.extend(check_placeholders(en_value, lang_value, current_path))
                elif isinstance(en_value, str) and isinstance(lang_value, str):
                    en_placeholders = extract_placeholders(en_value)
                    lang_placeholders = extract_placeholders(lang_value)
                    if en_placeholders != lang_placeholders:
                        mismatches.append(
                            f"{current_path}: English has {en_placeholders}, "
                            f"{lang} has {lang_placeholders}"
                        )
            return mismatches

        mismatches = check_placeholders(en_data, lang_data)
        assert not mismatches, f"Placeholder mismatches in {lang}.json:\n" + "\n".join(mismatches)


class TestEntityTranslations:
    """Test entity-specific translations."""

    @pytest.mark.parametrize("lang", EXPECTED_LANGUAGES)
    def test_all_sensors_have_names(self, lang: str) -> None:
        """Test that all sensors have name translations."""
        with open(TRANSLATIONS_PATH / f"{lang}.json", encoding="utf-8") as f:
            data = json.load(f)

        sensors = data.get("entity", {}).get("sensor", {})
        assert sensors, f"No sensor translations in {lang}.json"

        for sensor_key, sensor_data in sensors.items():
            assert "name" in sensor_data, f"Missing name for sensor {sensor_key} in {lang}.json"
            assert sensor_data["name"], f"Empty name for sensor {sensor_key} in {lang}.json"

    def test_schedule_sensor_renamed(self) -> None:
        """Test that schedule_mode sensor is named 'Schedule' (not 'Schedule Mode')."""
        with open(TRANSLATIONS_PATH / "en.json", encoding="utf-8") as f:
            data = json.load(f)

        schedule_name = data["entity"]["sensor"]["schedule_mode"]["name"]
        assert schedule_name == "Schedule", f"Expected 'Schedule', got '{schedule_name}'"
