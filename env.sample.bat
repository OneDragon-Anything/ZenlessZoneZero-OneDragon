@echo off
chcp 65001
rem 本脚本用于设置脚本运行所需的环境变量 以下是一键安装所使用的路径
rem 如果使用conda配置的环境变量请改为: %~dp0.conda\pythonw.exe
set PYTHON=%~dp0.venv\Scripts\pythonw.exe
rem 使用pythonw可以不显示命令行
