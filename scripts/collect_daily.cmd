@echo off
rem Full-sample DART collection, run every 2 hours by Windows Task Scheduler. The task deletes itself when collection completes.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -u -W ignore -m src.collect >> "data\collect_run.log" 2>&1
