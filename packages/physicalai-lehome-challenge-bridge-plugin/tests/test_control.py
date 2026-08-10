from __future__ import annotations

from physicalai_lehome_challenge_bridge_plugin.control import ControlCommand, ControlInbox, get_default_control


class TestControlCommand:
    def test_reset_command(self) -> None:
        command = ControlCommand(kind="reset")
        assert command.kind == "reset"
        assert command.name is None

    def test_switch_command(self) -> None:
        command = ControlCommand(kind="switch", name="Top_Long_Seen_3")
        assert command.kind == "switch"
        assert command.name == "Top_Long_Seen_3"

    def test_next_command(self) -> None:
        command = ControlCommand(kind="next")
        assert command.kind == "next"


class TestControlInbox:
    def test_push_and_drain_fifo(self) -> None:
        inbox = ControlInbox()
        inbox.push(ControlCommand(kind="reset"))
        inbox.push(ControlCommand(kind="next"))
        drained = inbox.drain()
        assert [c.kind for c in drained] == ["reset", "next"]

    def test_drain_empty(self) -> None:
        inbox = ControlInbox()
        assert inbox.drain() == []

    def test_update_state(self) -> None:
        inbox = ControlInbox()
        inbox.update_state(garment="Top_Long_Seen_0", index=0, num_garments=10)
        assert inbox.current_garment == "Top_Long_Seen_0"
        assert inbox.garment_index == 0
        assert inbox.num_garments == 10


class TestDefaultControl:
    def test_singleton(self) -> None:
        first = get_default_control()
        second = get_default_control()
        assert first is second
