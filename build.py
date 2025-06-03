import os
import sys
import shutil
import subprocess

def check_pyinstaller():
    """检查PyInstaller是否已安装"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    """安装PyInstaller"""
    print("正在安装PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True
    except subprocess.CalledProcessError:
        print("安装PyInstaller失败，请手动安装: pip install pyinstaller")
        return False

def check_dependencies():
    """检查所有依赖是否已安装"""
    dependencies = ["openai"]
    missing = []
    
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    
    if missing:
        print(f"缺少以下依赖: {', '.join(missing)}")
        print("正在安装缺失的依赖...")
        for dep in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
                print(f"已安装: {dep}")
            except subprocess.CalledProcessError:
                print(f"安装 {dep} 失败，请手动安装: pip install {dep}")
                return False
    
    return True

def build_executable():
    """构建可执行文件"""
    print("\n=== 开始构建可执行文件 ===")
    
    # 清理之前的构建
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # 构建命令
    cmd = [
        "pyinstaller",
        "--name=Minecraft模组汉化工具",
        "--onefile",
        "--add-data=app;app",  # 添加app文件夹
        "--icon=app/icon.ico" if os.path.exists("app/icon.ico") else "",
        "mod_translator.py"
    ]
    
    # 如果没有图标文件，移除图标参数
    if not os.path.exists("app/icon.ico"):
        cmd.pop(-2)
    
    print("执行构建命令: " + " ".join(cmd))
    
    try:
        subprocess.check_call(cmd)
        print("\n=== 构建成功 ===")
        print(f"可执行文件已生成: dist/Minecraft模组汉化工具.exe")
        
        # 复制必要的文件到dist目录
        if os.path.exists("config.json"):
            shutil.copy("config.json", "dist/config.json")
            print("已复制配置文件: config.json")
        
        # 创建空的app目录
        os.makedirs("dist/app", exist_ok=True)
        
        # 复制README文件（如果存在）
        if os.path.exists("README.md"):
            shutil.copy("README.md", "dist/README.md")
            print("已复制说明文件: README.md")
            
        return True
    except subprocess.CalledProcessError as e:
        print(f"构建失败: {e}")
        return False

def create_readme():
    """创建README文件"""
    if not os.path.exists("README.md"):
        with open("README.md", "w", encoding="utf-8") as f:
            f.write("""# Minecraft模组汉化工具

## 简介
这是一个自动提取Minecraft模组中的语言文件并进行翻译的工具。

## 功能
- 选择mod文件（支持多选）
- 提取mod中的语言文件（英文en_us.json和中文zh_cn.json）
- 分析中文翻译的完整性
- 使用AI自动翻译缺失的内容
- 生成完整的翻译资源包

## 使用方法
1. 运行程序
2. 选择mod文件
3. 处理mod文件
4. 使用AI翻译
5. 合并翻译结果

## 配置
首次运行时，程序会要求配置API信息：
- API URL: API服务器地址
- API Key: API密钥
- 模型ID: 使用的AI模型ID
- 等待时间: API请求间隔时间

## 注意事项
- 请确保有足够的磁盘空间
- 翻译结果会保存在TEMP/OUTPUT目录下
- 程序会自动生成翻译资源包ZIP文件
""")
        print("已创建README.md文件")

def main():
    """主函数"""
    print("=== Minecraft模组汉化工具打包程序 ===")
    
    # 检查并安装依赖
    if not check_dependencies():
        print("依赖检查失败，无法继续构建")
        return
    
    # 检查并安装PyInstaller
    if not check_pyinstaller():
        if not install_pyinstaller():
            print("无法安装PyInstaller，构建终止")
            return
    
    # 创建README文件
    create_readme()
    
    # 构建可执行文件
    if build_executable():
        print("\n打包完成！可执行文件已生成在dist目录中。")
    else:
        print("\n打包失败，请检查错误信息。")

if __name__ == "__main__":
    main() 