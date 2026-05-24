"""
DeepSeek 缓存优化器 - 验证脚本
"""

import sys
import os
from pathlib import Path

def print_header(text):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def check_python_version():
    """检查 Python 版本"""
    print("📋 检查 Python 版本...")
    version = sys.version_info
    if version.major < 3 or (version.minor < 8):
        print(f"❌ Python 版本过低: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """检查依赖"""
    print("📦 检查依赖...")
    
    required_packages = [
        "fastapi",
        "mcp",
        "sentence_transformers",
        "dash",
        "plotly",
        "numpy",
        "pandas"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} (未安装)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  缺少以下依赖，请运行: pip install {' '.join(missing)}")
        return False
    
    return True

def check_file_structure():
    """检查文件结构"""
    print("📁 检查文件结构...")
    
    required_files = [
        "README.md",
        "requirements.txt",
        "config/default.yaml",
        "config/trae-config.json",
        "mcp_server/__init__.py",
        "mcp_server/server.py",
        "mcp_server/cache/semantic.py",
        "mcp_server/cache/multi_level.py",
        "mcp_server/cache/adaptive_ttl.py",
        "agent/__init__.py",
        "agent/proxy.py",
        "agent/context.py",
        "agent/decision.py",
        "dashboard/__init__.py",
        "dashboard/app.py",
    ]
    
    base_dir = Path(__file__).parent
    missing = []
    
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} (缺失)")
            missing.append(file_path)
    
    if missing:
        print(f"\n⚠️  缺少 {len(missing)} 个文件")
        return False
    
    return True

def test_imports():
    """测试导入"""
    print("🧪 测试模块导入...")
    
    tests = [
        ("mcp_server.cache.semantic", "SemanticCache"),
        ("mcp_server.cache.multi_level", "MultiLevelCache"),
        ("mcp_server.cache.adaptive_ttl", "AdaptiveTTLManager"),
        ("agent.proxy", "AgentProxy"),
        ("agent.context", "ContextManager"),
        ("agent.decision", "CacheDecisionEngine"),
        ("dashboard.app", "DashboardApp"),
    ]
    
    failed = []
    for module_name, class_name in tests:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"  ✅ {module_name}.{class_name}")
        except Exception as e:
            print(f"  ❌ {module_name}.{class_name}: {e}")
            failed.append((module_name, class_name))
    
    if failed:
        print(f"\n⚠️  {len(failed)} 个模块导入失败")
        return False
    
    return True

def test_basic_functionality():
    """测试基本功能"""
    print("🔧 测试基本功能...")
    
    try:
        # 测试语义缓存
        from mcp_server.cache.semantic import SemanticCache
        cache = SemanticCache(max_entries=10)
        cache.set("test", "response", ttl=60)
        result = cache.get("test")
        assert result is not None
        print("  ✅ 语义缓存")
        
        # 测试智能体代理
        from agent.proxy import AgentProxy
        proxy = AgentProxy()
        result = proxy.process_request("测试查询")
        assert result.cache_key is not None
        print("  ✅ 智能体代理")
        
        # 测试决策引擎
        from agent.decision import CacheDecisionEngine
        engine = CacheDecisionEngine()
        decision = engine.decide("test", cache_hit=True, query_similarity=0.95)
        assert decision.decision is not None
        print("  ✅ 决策引擎")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 功能测试失败: {e}")
        return False

def check_configuration():
    """检查配置"""
    print("⚙️  检查配置...")
    
    import yaml
    
    config_path = Path(__file__).parent / "config" / "default.yaml"
    
    if not config_path.exists():
        print("  ❌ 配置文件不存在")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 检查必要配置项
        required_keys = ['cache', 'agent', 'dashboard']
        for key in required_keys:
            if key in config:
                print(f"  ✅ {key} 配置")
            else:
                print(f"  ❌ {key} 配置缺失")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ 配置解析失败: {e}")
        return False

def print_summary(results):
    """打印总结"""
    print_header("验证结果")
    
    total = len(results)
    passed = sum(results.values())
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 项通过")
    
    if passed == total:
        print("\n🎉 所有检查通过！系统可以正常运行。")
        print("\n下一步:")
        print("  1. 运行 'python -m dashboard.app' 启动监控面板")
        print("  2. 配置 TRAE MCP 服务器")
        print("  3. 开始使用 DeepSeek 缓存优化器！")
        return True
    else:
        print("\n⚠️  部分检查未通过，请修复上述问题。")
        return False

def main():
    """主函数"""
    print_header("DeepSeek 缓存优化器 - 验证脚本")
    
    results = {}
    
    # 运行各项检查
    results["Python 版本"] = check_python_version()
    results["依赖包"] = check_dependencies()
    results["文件结构"] = check_file_structure()
    results["模块导入"] = test_imports()
    results["基本功能"] = test_basic_functionality()
    results["配置文件"] = check_configuration()
    
    # 打印总结
    success = print_summary(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
