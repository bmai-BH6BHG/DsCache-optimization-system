
import sys
import os

# 重定向输出到日志文件
log_file = open("relay_server.log", "w", encoding="utf-8")
sys.stdout = log_file
sys.stderr = log_file

print("Starting relay server...")

# 现在执行 relay_server.py 的内容
exec(open("relay_server.py", encoding="utf-8").read())
