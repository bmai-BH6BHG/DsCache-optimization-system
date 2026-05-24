"""
DeepSeek 缓存优化器 - 安装脚本
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def print_banner():
    """打印安装横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           🚀 DeepSeek 缓存命中率优化方案                      ║
║                                                              ║
║   智能体 + MCP 服务 + 可视化面板                             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def check_python_version():
    """检查 Python 版本"""
    print("📋 检查 Python 版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 需要 Python 3.8 或更高版本")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")


def install_dependencies():
    """安装依赖"""
    print("\n📦 安装依赖...")
    
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ 未找到 requirements.txt")
        return False
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(requirements_file)
        ])
        print("✅ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False


def create_directories():
    """创建必要的目录"""
    print("\n📁 创建目录结构...")
    
    dirs = [
        "data",
        "logs",
        "data/cache_l3"
    ]
    
    for dir_name in dirs:
        dir_path = Path(__file__).parent / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"  📂 {dir_name}/")
    
    print("✅ 目录创建完成")


def setup_trae_integration():
    """设置 TRAE 集成"""
    print("\n🔧 配置 TRAE 集成...")
    
    config_source = Path(__file__).parent / "config" / "trae-config.json"
    
    print("""
要将 DeepSeek 缓存优化器集成到 TRAE，请按以下步骤操作：

1. 打开 TRAE 设置
2. 找到 MCP 服务器配置
3. 将以下内容添加到配置中：
    """)
    
    if config_source.exists():
        with open(config_source, 'r', encoding='utf-8') as f:
            config = json.load(f)
            print(json.dumps(config, indent=2, ensure_ascii=False))
    
    print("""
4. 保存配置并重启 TRAE
5. 在 TRAE 中启用 DeepSeek 缓存优化器 MCP 服务器

或者，你可以手动复制配置文件：
  - 源文件: config/trae-config.json
  - 目标: TRAE 的 MCP 配置目录
    """)


def create_startup_scripts():
    """创建启动脚本"""
    print("\n📝 创建启动脚本...")
    
    base_dir = Path(__file__).parent
    
    # Windows 批处理脚本
    windows_script = base_dir / "start.bat"
    with open(windows_script, 'w', encoding='utf-8') as f:
        f.write("""@echo off
chcp 65001 >nul
echo 🚀 启动 DeepSeek 缓存优化器...
echo.

echo 📊 启动可视化面板...
start "Dashboard" cmd /k "python -m dashboard.app"

echo.
echo ✅ 服务已启动！
echo 📊 面板地址: http://localhost:8050
echo.
pause
""")
    
    # PowerShell 脚本
    ps_script = base_dir / "start.ps1"
    with open(ps_script, 'w', encoding='utf-8') as f:
        f.write("""# DeepSeek 缓存优化器启动脚本

Write-Host "🚀 启动 DeepSeek 缓存优化器..." -ForegroundColor Green
Write-Host ""

# 启动可视化面板
Write-Host "📊 启动可视化面板..." -ForegroundColor Cyan
$dashboardJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m dashboard.app
}

Write-Host ""
Write-Host "✅ 服务已启动！" -ForegroundColor Green
Write-Host "📊 面板地址: http://localhost:8050" -ForegroundColor Yellow
Write-Host ""
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Gray

# 等待用户输入
while ($true) {
    Start-Sleep -Seconds 1
}
""")
    
    print(f"  ✅ {windows_script.name}")
    print(f"  ✅ {ps_script.name}")


def print_usage():
    """打印使用说明"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                      🎉 安装完成！                            ║
╚══════════════════════════════════════════════════════════════╝

📖 快速开始:

1. 启动可视化面板:
   python -m dashboard.app
   
   或双击 start.bat (Windows)

2. 在 TRAE 中配置 MCP 服务器:
   - 复制 config/trae-config.json 的内容到 TRAE 设置
   - 重启 TRAE

3. 访问监控面板:
   http://localhost:8050

📚 文档:
   - README.md - 项目说明
   - config/default.yaml - 配置文件

🔧 常用命令:
   # 启动 MCP 服务
   python -m mcp_server.server
   
   # 启动可视化面板
   python -m dashboard.app
   
   # 查看统计信息
   python -c "from mcp_server.cache.semantic import SemanticCache; c = SemanticCache(); print(c.get_stats())"

💡 提示:
   - 首次运行会下载语义模型，可能需要几分钟
   - 默认配置已针对 DeepSeek 优化
   - 可通过 config/default.yaml 调整参数

🐛 遇到问题?
   查看 logs/ 目录下的日志文件
   或提交 Issue 到项目仓库

═══════════════════════════════════════════════════════════════
    """)


def main():
    """主函数"""
    print_banner()
    
    # 检查 Python 版本
    check_python_version()
    
    # 安装依赖
    if not install_dependencies():
        print("\n❌ 安装失败，请检查错误信息")
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 设置 TRAE 集成
    setup_trae_integration()
    
    # 创建启动脚本
    create_startup_scripts()
    
    # 打印使用说明
    print_usage()


if __name__ == "__main__":
    main()
