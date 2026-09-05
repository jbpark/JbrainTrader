@echo off
rem ==============================================================================
rem [사용법] 백테스트 실행 스크립트 (Single & Dual 지원)
rem
rem 1. 단일 종목 백테스트:
rem    backtest.bat --ticker 005930 --strategy SCALP_01 --start 2026-03-19 --end 2026-03-19
rem
rem 2. 듀얼 ETF 스프레드 백테스트 (교차일 지원):
rem    backtest.bat --ticker QQQ,SQQQ --strategy DUAL_US_QQQ_SQQQ --start 2026-03-18 --end 2026-03-19
rem
rem 3. 파라미터 강제 적용 (웹 설정과 동일하게 맞출 때):
rem    backtest.bat --ticker QQQ,SQQQ --strategy DUAL_US_QQQ_SQQQ --start 2026-03-17 --threshold 1.5 --cash 50000 --end 2026-03-17
rem
rem 4. 상세 로그 출력 (Verbose):
rem    backtest.bat --ticker QQQ,SQQQ --strategy DUAL_US_QQQ_SQQQ --start 2026-03-19 --end 2026-03-19 -v
rem
rem 5. 국내 듀얼 ETF (KODEX 200/KODEX 200선물인버스 2X):
rem    backtest.bat --ticker 069500,252670 --strategy DUAL_KODEX200_2X_INVERSE --start 2026-03-20 --end 2026-03-20
rem
rem 6. 국내 듀얼 ETF (KODEX 레버리지/KODEX 200선물인버스 2X):
rem    backtest.bat --ticker 122630,252670 --strategy DUAL_KODEX_LEVERAGE_2X_INVERSE --start 2026-03-20 --end 2026-03-20
rem
rem 7. 전체 구간 백테스트 (날짜 생략 시 DB 내 모든 가용 데이터 자동 테스트 및 요약):
rem    backtest.bat --ticker 122630,252670 --strategy DUAL_KODEX_LEVERAGE_2X_INVERSE
rem
rem 8. 국내 듀얼 ETF (KODEX 200/KODEX 인버스 1X):
rem    backtest.bat --ticker 069500,114800 --strategy DUAL_200_1X_INVERSE
rem
rem 9. 미국 듀얼 ETF (QQQ/PSQ 1X 인버스):
rem    backtest.bat --ticker QQQ,PSQ --strategy DUAL_US_QQQ_PSQ --start 2026-03-24 --end 2026-03-26
rem
rem 10. 미국 듀얼 ETF (SPY/SH 1X 인버스):
rem    backtest.bat --ticker SPY,SH --strategy DUAL_US_SPY_SH --start 2026-03-24 --end 2026-03-26
rem ==============================================================================

python backtest.py %*
