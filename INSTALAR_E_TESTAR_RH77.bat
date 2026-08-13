@echo off
python rh7_cli.py bootstrap
python rh7_cli.py doctor
python rh7_cli.py selftest
python rh7_cli.py golden-failure-check
python -m unittest discover -s tests -v
pause
