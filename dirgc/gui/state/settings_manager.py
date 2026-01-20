
import json
import os

GUI_SETTINGS_PATH = os.path.join("config", "gui_settings.json")
MAX_RECENT_EXCEL = 8

class SettingsManager:
    @staticmethod
    def load():
        try:
            with open(GUI_SETTINGS_PATH, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def save(data):
        os.makedirs(os.path.dirname(GUI_SETTINGS_PATH), exist_ok=True)
        with open(GUI_SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    @staticmethod
    def update_recent_excels(current_list, new_path):
        normalized = os.path.normpath(new_path)
        if not normalized:
            return current_list
        
        updated = [
            item
            for item in current_list
            if os.path.normpath(item) != normalized
        ]
        updated.insert(0, normalized)
        return updated[:MAX_RECENT_EXCEL]
