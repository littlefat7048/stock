@echo off
title Taiwan Stock Analysis System
echo ======================================================
echo   Starting Taiwan Stock Analysis System...
echo   URL: http://localhost:8501
echo ======================================================
cd /d E:\antigravity\STOCK
start http://localhost:8501
C:\Users\SOHO\AppData\Local\Programs\Python\Python311\Scripts\streamlit.exe run app.py --server.port 8501 --server.headless true
pause
