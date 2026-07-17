import json
from pathlib import Path
from typing import Any


class PromptManager:
    def __init__(self, prompts_dir: str | Path | None = None):
        self._prompts_dir = Path(prompts_dir or Path(__file__).parent)
        self._cache: dict[str, str] = {}

    def get_system_prompt(self, agent_name: str) -> str:
        key = f"system:{agent_name}"
        if key in self._cache:
            return self._cache[key]

        path = self._prompts_dir / "system" / f"{agent_name}.txt"
        if not path.exists():
            path = self._prompts_dir / "system" / f"{agent_name}.md"

        if path.exists():
            content = path.read_text(encoding="utf-8")
            self._cache[key] = content
            return content

        return ""

    def get_template(self, template_name: str, **kwargs: Any) -> str:
        key = f"template:{template_name}"
        if key in self._cache:
            template = self._cache[key]
        elif template_name in self._cache:
            template = self._cache[template_name]
        else:
            path = self._prompts_dir / "templates" / f"{template_name}.txt"
            if not path.exists():
                path = self._prompts_dir / "templates" / f"{template_name}.md"
            if path.exists():
                template = path.read_text(encoding="utf-8")
                self._cache[key] = template
            else:
                template = ""

        if kwargs and template:
            return template.format(**kwargs)
        return template

    def register_prompt(self, name: str, content: str) -> None:
        self._cache[name] = content

    def load_prompts_from_json(self, path: str | Path) -> None:
        with open(path, encoding="utf-8") as f:
            prompts = json.load(f)
        for name, content in prompts.items():
            self._cache[name] = content

    def clear_cache(self) -> None:
        self._cache.clear()

    def export_to_json(self, path: str | Path) -> None:
        entry: dict[str, str] = {}
        for path_obj in (self._prompts_dir / "system").glob("*"):
            entry[f"system:{path_obj.stem}"] = path_obj.read_text(encoding="utf-8")
        for path_obj in (self._prompts_dir / "templates").glob("*"):
            entry[f"template:{path_obj.stem}"] = path_obj.read_text(encoding="utf-8")
        entry.update(self._cache)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
