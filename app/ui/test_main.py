"""
ui/test_main.py
Minimal UI execution test (menus/buttons/plugin integration)
"""
# dearpygui requires an interactive GUI environment for full tests
# this test checks that main.py runs without immediate crash
import subprocess


def test_ui_main():
    result = subprocess.run(['python', 'app/ui/main.py'], capture_output=True)
    assert result.returncode == 0


if __name__ == '__main__':
    test_ui_main()
    print('ui main test passed')
