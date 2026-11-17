@echo off
title Trader Dashboard Pro Terminal
echo ===================================================
echo     Launching Trader Dashboard (Laptop ^& Mobile)
echo ===================================================
echo.

python -m pip show streamlit >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing required packages ^(first run only^)...
    python -m pip install -r requirements.txt
)

python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Streamlit start failed. Trying with py launcher:
    py -m pip install -r requirements.txt
    py -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
)

pause
