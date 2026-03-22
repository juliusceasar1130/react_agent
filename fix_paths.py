import sys
import subprocess
from importlib.metadata import distributions

def fix_env():
    print("🔍 正在扫描此环境中带有命令行的包...")
    packages_to_reinstall = []
    
    # 遍历所有安装的包，找出带有 console_scripts（命令控制台入口）的包
    for dist in distributions():
        try:
            entry_points = dist.entry_points
            if any(ep.group == 'console_scripts' for ep in entry_points):
                pkg_name = dist.metadata.get('Name') or dist.name
                pkg_version = dist.version
                # 严格锁定版本号
                packages_to_reinstall.append(f"{pkg_name}=={pkg_version}")
        except Exception:
            continue

    if not packages_to_reinstall:
        print("✅ 没有找到需要修复的命令行工具。")
        return

    # 去重
    packages_to_reinstall = list(set(packages_to_reinstall))
    print(f"🎯 找到 {len(packages_to_reinstall)} 个需要修复启动路径的包（已锁定当前绝对版本）：")
    for pkg in packages_to_reinstall:
        print(f" - {pkg}")
    print("\n🚀 开始无依赖极速重装，确保版本 100% 一致...")
    
    # 执行极速重装命令
    cmd = [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps"] + packages_to_reinstall
    subprocess.run(cmd)
    print("\n🎉 当前环境的所有命令行工具路径修复完成，并且版本没有任何变化！")

if __name__ == "__main__":
    fix_env()
