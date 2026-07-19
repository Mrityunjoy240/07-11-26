from src.registry import CapabilityManifest, CapabilityRegistry


class TestCapabilityRegistry:
    def test_register_and_get(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="admission", version="1.0.0", description="Admission guidance"))
        cap = reg.get("admission")
        assert cap is not None
        assert cap.name == "admission"

    def test_get_nonexistent(self):
        reg = CapabilityRegistry()
        assert reg.get("nonexistent") is None

    def test_contains(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="placement", version="1.0.0", description="Placement info"))
        assert "placement" in reg
        assert "fees" not in reg

    def test_all_empty(self):
        reg = CapabilityRegistry()
        assert reg.all() == []

    def test_all_with_entries(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="a", description="desc a"))
        reg.register(CapabilityManifest(name="b", description="desc b"))
        assert len(reg.all()) == 2

    def test_find_with_handler(self):
        reg = CapabilityRegistry()
        handler = _DummyCapability("admission")
        reg.register(CapabilityManifest(name="admission", description="Admission", handler=handler))
        results = reg.find("admission")
        assert len(results) == 1
        assert results[0].name == "admission"

    def test_find_no_match(self):
        reg = CapabilityRegistry()
        handler = _DummyCapability("placement")
        reg.register(CapabilityManifest(name="placement", description="Placement", handler=handler))
        results = reg.find("admission")
        assert len(results) == 0

    def test_register_twice_versioned(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="x", version="1.0.0", description="first"))
        reg.register(CapabilityManifest(name="x", version="2.0.0", description="second"))
        assert reg.get("x").description == "second"


class _DummyCapability:
    def __init__(self, name: str):
        self.name = name
        self.description = f"Dummy {name}"

    def can_handle(self, intent: str, context=None) -> bool:
        return intent == self.name

    def execute(self, context=None):
        return {"handled": self.name}
