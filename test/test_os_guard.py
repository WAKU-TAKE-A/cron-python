import sys
import unittest.mock
import pytest

def test_os_guard_aborts_on_non_windows():
    from cron_python import main
    with unittest.mock.patch("os.name", "posix"):
        with unittest.mock.patch("sys.stderr.write") as mock_write:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            mock_write.assert_called_with("Error: This tool is Windows-only. Linux/macOS is not supported.\n")
