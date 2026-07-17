
from src.prompts.manager import PromptManager


def test_prompt_manager_basic():
    mgr = PromptManager()
    assert mgr.get_system_prompt("nonexistent") == ""
    assert mgr.get_template("nonexistent") == ""


def test_prompt_manager_register():
    mgr = PromptManager()
    mgr.register_prompt("test_prompt", "Hello {name}")
    result = mgr.get_template("test_prompt", name="World")
    assert result == "Hello World"


def test_prompt_manager_file_loading(tmp_path):
    system_dir = tmp_path / "system"
    system_dir.mkdir()
    (system_dir / "supervisor.txt").write_text("You are a helpful counselor.")

    mgr = PromptManager(prompts_dir=tmp_path)
    content = mgr.get_system_prompt("supervisor")
    assert content == "You are a helpful counselor."
