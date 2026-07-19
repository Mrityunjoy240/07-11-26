from src.registry import CapabilityManifest, CapabilityRegistry


class TestRegistryV2:
    def test_register_and_get_latest(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="admission", version="1.0.0"))
        m = reg.get("admission")
        assert m is not None
        assert m.version == "1.0.0"

    def test_get_specific_version(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="test", version="1.0.0"))
        reg.register(CapabilityManifest(name="test", version="2.0.0"))
        v1 = reg.get("test", "1.0.0")
        v2 = reg.get("test", "2.0.0")
        assert v1.version == "1.0.0"
        assert v2.version == "2.0.0"

    def test_get_latest_version(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="x", version="1.0.0"))
        reg.register(CapabilityManifest(name="x", version="2.0.0"))
        assert reg.get("x").version == "2.0.0"

    def test_get_nonexistent(self):
        reg = CapabilityRegistry()
        assert reg.get("nope") is None

    def test_versions_list(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="v", version="1.0.0"))
        reg.register(CapabilityManifest(name="v", version="2.0.0"))
        assert reg.versions("v") == ["1.0.0", "2.0.0"]

    def test_contains(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="admission", version="1.0.0"))
        assert "admission" in reg
        assert "fees" not in reg

    def test_all_returns_latest(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(name="a", version="1.0.0"))
        reg.register(CapabilityManifest(name="a", version="2.0.0"))
        reg.register(CapabilityManifest(name="b", version="1.0.0"))
        all_caps = reg.all()
        assert len(all_caps) == 2
        assert all_caps[0].version == "2.0.0"

    def test_find_with_handler(self):
        reg = CapabilityRegistry()
        handler = _TestHandler("x")
        reg.register(CapabilityManifest(name="x", handler=handler))
        results = reg.find("x")
        assert len(results) == 1

    def test_find_no_match(self):
        reg = CapabilityRegistry()
        handler = _TestHandler("placement")
        reg.register(CapabilityManifest(name="p", handler=handler))
        results = reg.find("fees")
        assert len(results) == 0

    def test_register_manifest_with_metadata(self):
        reg = CapabilityRegistry()
        reg.register(CapabilityManifest(
            name="fees", version="1.0.0",
            description="Fee structure queries",
            metadata={"required_info": ["category"]},
            dependencies=["admission"],
        ))
        m = reg.get("fees")
        assert m.description == "Fee structure queries"
        assert m.metadata["required_info"] == ["category"]
        assert "admission" in m.dependencies


class _TestHandler:
    def __init__(self, intent: str):
        self._intent = intent

    def can_handle(self, intent: str, context=None) -> bool:
        return intent == self._intent

    def execute(self, context=None):
        return {"handled": self._intent}
