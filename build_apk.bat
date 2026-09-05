@echo off
chcp 65001 > nul
echo ============================================
echo   Flutter APK 빌드 시작
echo ============================================
echo.

cd /d %~dp0trading_app

echo [1/3] flutter clean 실행 중...
call flutter clean
if %errorlevel% neq 0 (
    echo [오류] flutter clean 실패
    pause
    exit /b 1
)

echo.
echo [추가] Gradle 데몬 중지 및 캐시 삭제 중...
cd android
call .\gradlew --stop
if exist ".gradle" (
    echo .gradle 폴더 삭제 중...
    rmdir /s /q .gradle
)
cd ..

echo.
echo [2/3] flutter pub get 실행 중...
call flutter pub get
if %errorlevel% neq 0 (
    echo [오류] flutter pub get 실패
    pause
    exit /b 1
)

echo.
echo [3/3] APK 빌드 중 (release)...
call flutter build apk --release
if %errorlevel% neq 0 (
    echo [오류] APK 빌드 실패
    pause
    exit /b 1
)

echo.
echo ============================================
echo   빌드 완료!
echo ============================================
echo.
echo APK 파일 위치:
echo   %~dp0trading_app\build\app\outputs\flutter-apk\app-release.apk
echo.

:: APK 파일이 있으면 탐색기로 열기
set APK_DIR=%~dp0trading_app\build\app\outputs\flutter-apk
if exist "%APK_DIR%\app-release.apk" (
    echo APK 파일이 정상적으로 생성되었습니다.
    echo 탐색기에서 폴더를 열겠습니다...
    explorer "%APK_DIR%"
) else (
    echo [경고] APK 파일을 찾을 수 없습니다.
)

echo.
pause
