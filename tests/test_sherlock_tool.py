from tools.sherlock_tool import SherlockTool


def test_sherlock_rejects_whitespace_without_index_error() -> None:
    assert SherlockTool()._run("   ") == (
        "FAILED|Username kosong / cuma karakter terlarang"
    )
