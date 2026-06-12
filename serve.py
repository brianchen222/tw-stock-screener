#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
靜態預覽伺服器(給 report.html 用)。

為什麼不用 `python -m http.server`:
  http.server 在 __main__ 的 argparse 會呼叫 os.getcwd() 當預設值,
  而本專案位於 OneDrive 目錄,該 cwd 在沙箱下被拒(PermissionError: Operation not permitted),
  於是伺服器一啟動就崩潰。
本腳本改為:傳入「要服務的絕對目錄」,先 os.chdir 到該(可存取)目錄,
並用 directory= 指定 handler 根目錄,全程不呼叫 os.getcwd(),即可避開該錯誤。
"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# 服務目錄與埠號由參數傳入(務必傳絕對路徑,避免任何相對路徑觸發 os.getcwd())
DIRECTORY = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(__file__) + "/output"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8770

os.chdir(DIRECTORY)  # 切到可存取的絕對目錄


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # 重畫後立即看到新圖
        super().end_headers()

    def log_message(self, *args):
        pass  # 安靜


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving {DIRECTORY} at http://127.0.0.1:{PORT}/report.html", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
