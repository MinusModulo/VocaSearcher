@echo off
echo =====================================
echo SongScraper API 服务器启动脚本
echo =====================================

echo [1/3] 检查 Python 环境...
python --version
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python，请先安装 Python 3.7+
    pause
    exit /b 1
)

echo.
echo [2/3] 安装 Python 依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo 警告: 依赖安装可能有问题，但继续尝试启动服务器...
)

echo.
echo [3/3] 启动 API 服务器...
echo 服务器将在 http://localhost:5000 上启动
echo 按 Ctrl+C 停止服务器
echo.

cd src
python api.py

echo.
echo 服务器已停止
pause
