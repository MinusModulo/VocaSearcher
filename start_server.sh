#!/bin/bash

echo "正在安装 Python 依赖..."
pip install -r requirements.txt

echo ""
echo "启动 API 服务器..."
cd src
python api.py
