@echo off

:: 检查conda环境是否存在
conda env list | findstr /i "groupbin" >nul
if %errorlevel% neq 0 (
    echo 创建conda环境...
    conda env create -f environment.yml
)

:: 激活环境
call conda activate groupbin

:: 检查并创建uploads目录
if not exist "uploads" mkdir uploads

:: 加载环境变量
if exist .env (
    for /f "delims=" %%x in (.env) do set "%%x"
)

:: 启动应用
flask run --host=0.0.0.0 --port=5000

pause
set FLASK_APP=run.py
set FLASK_ENV=development
if exist .env (
    for /f "delims=" %%x in (.env) do set "%%x"
)
flask run --host=0.0.0.0 --port=5000