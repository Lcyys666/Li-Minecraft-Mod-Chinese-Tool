import os
import json
import shutil
import zipfile
import tkinter as tk
from tkinter import filedialog
import re
import copy
import math
import time
from pathlib import Path
import datetime
import threading
import sys
import subprocess
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("警告: requests库未安装，检查更新功能将不可用。请运行 'pip install requests' 安装")
    REQUESTS_AVAILABLE = False
try:
    from openai import OpenAI
except ImportError:
    print("警告: OpenAI库未安装，请运行 'pip install openai' 安装")

# 版本信息
VERSION_INFO = {
    "version": "1.1.0",
    "release_date": "2025-06-08",
    "update_url": "https://gh-proxy.com/https://github.com/Lcyys666/Li-Minecraft-Mod-Chinese-Tool/raw/refs/heads/main/version.exe",
    "changelog": "新增功能：\n- 添加已有翻译资源包过滤功能\n- 添加检查更新功能\n- 修复若干bug"
}

# 云端版本信息URL
VERSION_CHECK_URL = "https://raw.kkgithub.com/Lcyys666/Li-Minecraft-Mod-Chinese-Tool/main/version.json"

def download_file(url, save_path, progress_callback=None):
    """下载文件到指定路径
    
    Args:
        url: 文件URL
        save_path: 保存路径
        progress_callback: 进度回调函数，接收(current, total)参数
        
    Returns:
        bool: 下载是否成功
    """
    if not REQUESTS_AVAILABLE:
        print("无法下载更新：requests库未安装")
        return False
    
    try:
        # 发送流式请求
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code != 200:
            print(f"下载失败：HTTP错误 {response.status_code}")
            return False
        
        # 获取文件大小
        total_size = int(response.headers.get('content-length', 0))
        
        # 创建临时文件路径
        temp_path = f"{save_path}.downloading"
        
        # 确保下载目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # 下载文件
        downloaded = 0
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)
        
        # 下载完成后重命名
        if os.path.exists(save_path):
            os.remove(save_path)
        os.rename(temp_path, save_path)
        return True
        
    except Exception as e:
        print(f"下载文件时出错: {str(e)}")
        # 清理临时文件
        if os.path.exists(f"{save_path}.downloading"):
            try:
                os.remove(f"{save_path}.downloading")
            except:
                pass
        return False

def restart_with_new_version(new_version_path):
    """使用新版本重启程序
    
    Args:
        new_version_path: 新版本程序路径
    """
    try:
        # 获取当前程序路径
        current_path = sys.executable
        # 如果是通过Python解释器运行的脚本
        if os.path.basename(current_path).lower().startswith('python'):
            current_path = os.path.abspath(__file__)
            # 确定当前是脚本文件还是exe
            is_script = True
        else:
            is_script = False
        
        # 如果是相同路径且都是exe或都是脚本，不需要替换
        if os.path.abspath(new_version_path) == os.path.abspath(current_path) and os.path.splitext(new_version_path)[1] == os.path.splitext(current_path)[1]:
            print("更新文件与当前程序相同，无需替换")
            return
        
        # 获取当前程序的目录和文件名
        current_dir = os.path.dirname(current_path)
        current_filename = os.path.basename(current_path)
        
        # 创建替换批处理文件
        bat_path = os.path.join(current_dir, "update.bat")
        with open(bat_path, 'w', encoding='gbk') as f:
            f.write('@echo off\n')
            f.write('echo 正在更新，请稍候...\n')
            f.write('timeout /t 2 /nobreak > nul\n')
            
            # 检查是否是通过python运行的脚本
            if is_script:
                # 如果是脚本文件，仅复制文件内容
                f.write(f'copy /y "{new_version_path}" "{current_path}"\n')
            else:
                # 如果是exe，需要检查进程
                f.write(f'taskkill /f /im "{current_filename}" 2>nul\n')
                f.write('timeout /t 1 /nobreak > nul\n')
                
                # 直接复制到当前目录，使用原名称
                f.write(f'copy /y "{new_version_path}" "{current_path}"\n')
            
            # 删除下载的更新文件
            f.write(f'del "{new_version_path}"\n')
            
            # 如果是exe，启动新版本
            if not is_script:
                f.write(f'start "" "{current_path}"\n')
            else:
                # 如果是脚本，使用python启动
                f.write(f'start "" "{sys.executable}" "{current_path}"\n')
            
            # 自删除批处理
            f.write('timeout /t 1 /nobreak > nul\n')
            f.write('del "%~f0"\n')
        
        print("更新文件已下载，程序将重启以完成更新...")
        
        # 启动批处理
        subprocess.Popen(['cmd', '/c', 'start', '/min', bat_path], shell=True)
        
        # 等待一会儿后退出程序
        time.sleep(1.5)
        sys.exit(0)
        
    except Exception as e:
        print(f"准备更新时出错: {str(e)}")
        print("请手动更新：关闭程序后，将下载的文件复制到程序目录并重命名为当前程序名")

def check_for_updates(silent=False, auto_update=False):
    """检查是否有更新可用
    
    Args:
        silent: 是否静默检查（不显示"已是最新版本"的消息）
        auto_update: 是否自动下载更新
        
    Returns:
        bool: 是否有更新可用
    """
    if not REQUESTS_AVAILABLE:
        if not silent:
            print("无法检查更新：requests库未安装")
        return False
    
    try:
        # 获取云端版本信息
        response = requests.get(VERSION_CHECK_URL, timeout=10)
        if response.status_code != 200:
            if not silent:
                print(f"检查更新失败：HTTP错误 {response.status_code}")
            return False
        
        # 解析云端版本信息
        cloud_version_info = response.json()
        local_version = VERSION_INFO["version"]
        cloud_version = cloud_version_info.get("version")
        
        if not cloud_version:
            if not silent:
                print("检查更新失败：无法获取云端版本号")
            return False
        
        # 比较版本号
        local_parts = [int(x) for x in local_version.split(".")]
        cloud_parts = [int(x) for x in cloud_version.split(".")]
        
        # 确保两个列表长度相同
        while len(local_parts) < len(cloud_parts):
            local_parts.append(0)
        while len(cloud_parts) < len(local_parts):
            cloud_parts.append(0)
        
        # 比较每一部分
        has_update = False
        for i in range(len(local_parts)):
            if cloud_parts[i] > local_parts[i]:
                has_update = True
                break
            elif cloud_parts[i] < local_parts[i]:
                break
        
        if has_update:
            update_url = cloud_version_info.get("update_url", VERSION_INFO["update_url"])
            
            print("\n=== 发现新版本 ===")
            print(f"当前版本: {local_version}")
            print(f"最新版本: {cloud_version}")
            print(f"发布日期: {cloud_version_info.get('release_date', '未知')}")
            print("\n更新内容:")
            print(cloud_version_info.get("changelog", "无更新说明"))
            
            if auto_update:
                # 自动更新
                print(f"\n正在自动下载更新...")
                
                # 确定下载路径 - 使用时间戳避免文件冲突
                timestamp = int(time.time())
                download_dir = os.path.dirname(os.path.abspath(__file__))
                download_path = os.path.join(download_dir, f"update_{timestamp}.exe")
                
                # 显示下载进度的回调函数
                def show_progress(downloaded, total):
                    if total > 0:
                        percent = min(100, int(downloaded * 100 / total))
                        # 计算进度条长度
                        bar_len = 20
                        filled_len = int(bar_len * percent / 100)
                        bar = '█' * filled_len + '░' * (bar_len - filled_len)
                        # 使用\r回到行首，更新进度条
                        sys.stdout.write(f"\r下载进度: [{bar}] {percent}% ({downloaded/1024/1024:.1f}MB/{total/1024/1024:.1f}MB)")
                        sys.stdout.flush()
                
                # 下载更新
                if download_file(update_url, download_path, show_progress):
                    print("\n\n下载完成！正在安装更新...")
                    restart_with_new_version(download_path)
                else:
                    print("\n\n下载失败，请手动更新")
                    print(f"下载地址: {update_url}")
            else:
                # 询问用户是否更新
                choice = input(f"\n是否现在下载并更新？(Y/n): ").strip().lower()
                if choice != 'n':
                    print(f"\n正在下载更新...")
                    
                    # 确定下载路径 - 使用时间戳避免文件冲突
                    timestamp = int(time.time())
                    download_dir = os.path.dirname(os.path.abspath(__file__))
                    download_path = os.path.join(download_dir, f"update_{timestamp}.exe")
                    
                    # 显示下载进度的回调函数
                    def show_progress(downloaded, total):
                        if total > 0:
                            percent = min(100, int(downloaded * 100 / total))
                            # 计算进度条长度
                            bar_len = 20
                            filled_len = int(bar_len * percent / 100)
                            bar = '█' * filled_len + '░' * (bar_len - filled_len)
                            # 使用\r回到行首，更新进度条
                            sys.stdout.write(f"\r下载进度: [{bar}] {percent}% ({downloaded/1024/1024:.1f}MB/{total/1024/1024:.1f}MB)")
                            sys.stdout.flush()
                    
                    # 下载更新
                    if download_file(update_url, download_path, show_progress):
                        print("\n\n下载完成！正在安装更新...")
                        restart_with_new_version(download_path)
                    else:
                        print("\n\n下载失败，请手动更新")
                        print(f"下载地址: {update_url}")
                else:
                    print(f"\n下载地址: {update_url}")
            
            return True
        elif not silent:
            print(f"您使用的已经是最新版本 ({local_version})")
        
        return False
    
    except Exception as e:
        if not silent:
            print(f"检查更新时出错: {str(e)}")
        return False

class Config:
    """配置管理类"""
    def __init__(self):
        self.config_file = "config.json"
        self.default_config = {
            "api_url": "",
            "api_key": "",
            "model_id": "",
            "wait_time": 3,
            "batch_size": 40,  # 每个翻译文件的最大条目数
            "auto_check_update": True,  # 自动检查更新
            "auto_update": False  # 自动下载安装更新
        }
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件，如果不存在则创建新的配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 检查是否有缺失的配置项，如果有则使用默认值
                for key, value in self.default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            except Exception as e:
                print(f"读取配置文件时出错: {str(e)}")
                return self.create_new_config()
        else:
            return self.create_new_config()
    
    def create_new_config(self):
        """创建新的配置文件"""
        print("\n=== 首次运行配置 ===")
        print("请填写以下配置信息：")
        
        config = self.default_config.copy()
        
        # API URL
        while True:
            api_url = input("API URL: ").strip()
            if api_url:
                if api_url.startswith('http://') or api_url.startswith('https://'):
                    config['api_url'] = api_url
                    break
                print("请输入有效的URL（以http://或https://开头）")
            else:
                print("API URL不能为空")
        
        # API Key
        while True:
            api_key = input("API Key: ").strip()
            if api_key:
                config['api_key'] = api_key
                break
            print("API Key不能为空")
        
        # 模型ID
        while True:
            model_id = input("模型ID: ").strip()
            if model_id:
                config['model_id'] = model_id
                break
            print("模型ID不能为空")
        
        # 等待时间
        while True:
            try:
                wait_time = input(f"请求等待时间（秒）[{config['wait_time']}]: ").strip()
                if not wait_time:
                    break
                wait_time = float(wait_time)
                if wait_time > 0:
                    config['wait_time'] = wait_time
                    break
                print("等待时间必须大于0")
            except ValueError:
                print("请输入有效的数字")
        
        # 自动检查更新
        auto_check = input(f"是否自动检查更新？(Y/n): ").strip().lower()
        config['auto_check_update'] = auto_check != 'n'
        
        # 自动更新
        if config['auto_check_update']:
            auto_update = input(f"是否自动下载安装更新？(y/N): ").strip().lower()
            config['auto_update'] = auto_update == 'y'
        
        # 保存配置
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            print("\n配置已保存到", self.config_file)
        except Exception as e:
            print(f"保存配置文件时出错: {str(e)}")
        
        return config
    
    def get(self, key, default=None):
        """获取配置项的值"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置项的值"""
        self.config[key] = value
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件时出错: {str(e)}")

def load_json_with_comments(file_path):
    """加载可能包含注释的JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除单行注释 (// 注释)
        content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
        
        # 移除多行注释 (/* 注释 */)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # 尝试解析JSON
        return json.loads(content)
    except Exception as e:
        print(f"警告: 解析JSON文件 {file_path} 时出错: {str(e)}")
        print("尝试使用更宽松的方式解析...")
        
        try:
            # 如果上面的方法失败，尝试使用更宽松的方式解析
            import json5
            with open(file_path, 'r', encoding='utf-8') as f:
                return json5.load(f)
        except ImportError:
            print("警告: json5模块未安装，无法使用更宽松的解析方式")
            # 如果json5模块未安装，返回空字典
            return {}
        except Exception as e2:
            print(f"错误: 无法解析JSON文件 {file_path}: {str(e2)}")
            return {}

def split_json_file(json_data, output_dir, base_filename, items_per_file=40):
    """将JSON数据分割成多个文件，每个文件包含指定数量的项目"""
    if not json_data:
        return []
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取所有键
    all_keys = list(json_data.keys())
    
    # 计算需要分割的文件数
    total_files = math.ceil(len(all_keys) / items_per_file)
    
    split_files = []
    
    # 分割JSON数据并写入文件
    for i in range(total_files):
        start_idx = i * items_per_file
        end_idx = min((i + 1) * items_per_file, len(all_keys))
        
        # 创建当前分片的数据
        current_data = {}
        for key in all_keys[start_idx:end_idx]:
            current_data[key] = json_data[key]
        
        # 生成输出文件名
        if total_files > 1:
            output_filename = f"{base_filename}_{i+1}.json"
        else:
            output_filename = f"{base_filename}.json"
        
        output_path = os.path.join(output_dir, output_filename)
        
        # 写入JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, ensure_ascii=False, indent=4)
        
        split_files.append(output_path)
    
    return split_files

class ModTranslator:
    def __init__(self):
        # 加载配置
        self.config = Config()
        
        # 启用Windows长路径支持
        self._enable_long_paths()
        
        self.temp_dir = os.path.join(os.getcwd(), "TEMP")
        self.mod_dir = os.path.join(self.temp_dir, "mod")
        self.fanyi_dir = os.path.join(self.temp_dir, "fanyi")
        self.fanyi_ok_dir = os.path.join(self.temp_dir, "fanyi_ok")
        self.output_dir = os.path.join(self.temp_dir, "OUTPUT")
        self.resourcepacks_dir = os.path.join(self.temp_dir, "resourcepacks")
        self.mod_json_path = os.path.join(self.mod_dir, "mod.json")
        self.selected_mods = []
        self.selected_resource_packs = []
        self.extracted_translations = {}  # 用于存储从资源包中提取的翻译
        
        # 创建隐藏的tkinter根窗口，用于文件选择对话框
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏窗口
        
        # 确保翻译结果目录存在
        os.makedirs(self.fanyi_ok_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.resourcepacks_dir, exist_ok=True)
        
        # 如果配置允许，在后台检查更新
        if self.config.get('auto_check_update', True) and REQUESTS_AVAILABLE:
            auto_update = self.config.get('auto_update', False)
            threading.Thread(target=lambda: check_for_updates(silent=True, auto_update=auto_update), daemon=True).start()
    
    def _enable_long_paths(self):
        """尝试启用Windows长路径支持"""
        try:
            import ctypes
            # 260是Windows默认的MAX_PATH限制
            # 0x8000是FILE_FLAG_BACKUP_SEMANTICS
            # 0x00010000是FILE_FLAG_POSIX_SEMANTICS，允许长路径
            ctypes.windll.kernel32.SetFileAttributesW(".", 0x00010000)
        except Exception:
            print("警告: 无法启用长路径支持，可能会遇到路径长度限制问题")
    
    def _sanitize_folder_name(self, name):
        """清理文件夹名称，避免过长和特殊字符"""
        # 移除方括号及其内容
        name = re.sub(r'\[.*?\]\s*', '', name)
        # 移除非字母数字字符
        name = re.sub(r'[^\w\-\.]', '_', name)
        # 限制长度
        if len(name) > 50:
            # 保留文件名开头和扩展名
            base, ext = os.path.splitext(name)
            name = base[:45] + ext if ext else base[:50]
        return name
    
    def clean_temp_folder(self):
        """清理TEMP文件夹"""
        if os.path.exists(self.temp_dir):
            # 询问用户是否也清理资源包翻译
            keep_resource_packs = False
            if self.extracted_translations:
                print("\n注意: 已有提取的资源包翻译数据")
                choice = input("是否保留资源包翻译数据? (Y/n): ").strip().lower()
                keep_resource_packs = choice != 'n'
            
            if keep_resource_packs and self.extracted_translations:
                # 保存资源包目录内容
                resource_packs_backup = self.extracted_translations.copy()
                
                # 删除TEMP目录（除了resourcepacks）
                for item in os.listdir(self.temp_dir):
                    item_path = os.path.join(self.temp_dir, item)
                    if item != "resourcepacks":
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                
                # 恢复提取的翻译
                self.extracted_translations = resource_packs_backup
                print("已清理临时文件夹（保留资源包翻译数据）")
            else:
                # 完全清理，包括资源包
                shutil.rmtree(self.temp_dir)
                self.extracted_translations = {}
                self.selected_resource_packs = []
                print("已完全清理临时文件夹（包括资源包翻译数据）")
        
        # 创建必要的目录
        os.makedirs(self.mod_dir, exist_ok=True)
        os.makedirs(self.fanyi_dir, exist_ok=True)
        os.makedirs(self.fanyi_ok_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.resourcepacks_dir, exist_ok=True)
    
    def select_mods_interactively(self):
        """使用文件选择对话框选择mod文件"""
        print("\n=== 选择mod文件 ===")
        
        files = filedialog.askopenfilenames(
            title="选择Mod文件",
            filetypes=[("Mod文件", "*.jar"), ("Zip文件", "*.zip"), ("所有文件", "*.*")]
        )
        
        if not files:
            print("未选择任何文件")
            return False
        
        # 将选择的文件添加到列表
        self.selected_mods = list(files)
        
        print(f"\n已选择 {len(self.selected_mods)} 个mod文件:")
        for mod in self.selected_mods:
            print(f"  - {mod}")
        
        return len(self.selected_mods) > 0

    def select_resource_packs_interactively(self):
        """使用文件选择对话框选择翻译资源包"""
        print("\n=== 选择翻译资源包（可选）===")
        print("请选择已有的翻译资源包，这些资源包中的翻译内容将被用于过滤")
        print("如果不需要使用资源包进行过滤，可以直接关闭文件选择对话框")
        
        files = filedialog.askopenfilenames(
            title="选择翻译资源包（可选）",
            filetypes=[("资源包文件", "*.zip"), ("所有文件", "*.*")]
        )
        
        if not files:
            print("未选择任何资源包，将不使用资源包过滤")
            # 清空之前可能已有的选择
            self.selected_resource_packs = []
            self.extracted_translations = {}
            return False
        
        # 将选择的文件添加到列表
        self.selected_resource_packs = list(files)
        
        print(f"\n已选择 {len(self.selected_resource_packs)} 个翻译资源包:")
        for pack in self.selected_resource_packs:
            print(f"  - {pack}")
        
        # 解压资源包并提取翻译
        self._extract_resource_packs()
        
        return len(self.selected_resource_packs) > 0
    
    def _extract_resource_packs(self):
        """解压所选资源包并提取翻译文件"""
        if not self.selected_resource_packs:
            return
        
        print("\n=== 提取资源包翻译 ===")
        
        # 清空资源包目录
        if os.path.exists(self.resourcepacks_dir):
            shutil.rmtree(self.resourcepacks_dir)
        os.makedirs(self.resourcepacks_dir, exist_ok=True)
        
        # 重置翻译字典
        self.extracted_translations = {}
        
        # 遍历每个资源包
        for pack_path in self.selected_resource_packs:
            pack_name = os.path.basename(pack_path)
            print(f"正在提取 {pack_name} 的翻译...")
            
            try:
                with zipfile.ZipFile(pack_path, 'r') as zip_ref:
                    # 查找中文语言文件
                    for file_info in zip_ref.infolist():
                        if '/lang/' in file_info.filename and file_info.filename.endswith('zh_cn.json'):
                            # 提取文件
                            relative_path = os.path.dirname(file_info.filename)
                            extract_path = os.path.join(self.resourcepacks_dir, file_info.filename)
                            
                            # 确保目标目录存在
                            os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                            
                            # 提取文件
                            source = zip_ref.open(file_info)
                            with open(extract_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                            source.close()
                            
                            # 读取JSON内容
                            try:
                                zh_data = load_json_with_comments(extract_path)
                                if zh_data:
                                    # 将路径标准化以便于后续比较
                                    normalized_path = relative_path.replace('\\', '/').rstrip('/')
                                    
                                    # 存储提取的翻译
                                    if normalized_path not in self.extracted_translations:
                                        self.extracted_translations[normalized_path] = {}
                                    
                                    # 合并翻译
                                    self.extracted_translations[normalized_path].update(zh_data)
                                    print(f"  - 已提取 {relative_path} 的翻译，包含 {len(zh_data)} 个条目")
                            except Exception as e:
                                print(f"  - 警告: 读取翻译文件 {file_info.filename} 时出错: {str(e)}")
                
                print(f"完成提取 {pack_name}")
            
            except Exception as e:
                print(f"提取资源包 {pack_name} 时出错: {str(e)}")
        
        # 统计提取的翻译
        total_paths = len(self.extracted_translations)
        total_entries = sum(len(entries) for entries in self.extracted_translations.values())
        
        if total_paths > 0:
            print(f"\n共从 {len(self.selected_resource_packs)} 个资源包中提取了 {total_paths} 个路径的 {total_entries} 个翻译条目")
        else:
            print("\n未从资源包中找到任何中文翻译文件")
    
    def process_mods(self):
        """处理所有选定的mod文件"""
        if not self.selected_mods:
            print("错误: 没有选择mod文件")
            return False
        
        # 清理并创建TEMP文件夹，但保留resourcepacks目录中的内容
        if os.path.exists(self.temp_dir):
            # 保存资源包目录内容
            resource_packs_backup = None
            if os.path.exists(self.resourcepacks_dir) and self.extracted_translations:
                resource_packs_backup = self.extracted_translations.copy()
            
            # 删除TEMP目录（除了resourcepacks）
            for item in os.listdir(self.temp_dir):
                item_path = os.path.join(self.temp_dir, item)
                if item != "resourcepacks" or not self.extracted_translations:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
            
            # 恢复提取的翻译
            if resource_packs_backup:
                self.extracted_translations = resource_packs_backup
        
        # 创建必要的目录
        os.makedirs(self.mod_dir, exist_ok=True)
        os.makedirs(self.fanyi_dir, exist_ok=True)
        os.makedirs(self.fanyi_ok_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.resourcepacks_dir, exist_ok=True)
        
        mod_info = []
        stats = {
            "processed": 0,         # 成功处理的mod数量
            "no_lang_files": 0,     # 没有语言文件的mod数量
            "no_en_us": 0,          # 没有英文语言文件的mod数量
            "complete_zh_cn": 0,    # 已有完整中文翻译的mod数量
            "partial_zh_cn": 0,     # 有不完整中文翻译的mod数量
            "no_zh_cn": 0           # 完全没有中文翻译的mod数量
        }
        
        resource_packs_info = ""
        if self.extracted_translations:
            total_paths = len(self.extracted_translations)
            total_entries = sum(len(entries) for entries in self.extracted_translations.values())
            resource_packs_info = f"，将使用 {total_paths} 个路径的 {total_entries} 个翻译条目进行过滤"
        
        print(f"\n开始处理 {len(self.selected_mods)} 个mod文件{resource_packs_info}...")
        
        # 提取每个mod的语言文件
        for mod_path in self.selected_mods:
            mod_name = os.path.basename(mod_path)
            
            try:
                # 先检查mod中的语言文件情况
                lang_check_result = self._check_lang_files(mod_path)
                
                if not lang_check_result["has_lang_files"]:
                    print(f"跳过 {mod_name} - 未包含语言文件")
                    stats["no_lang_files"] += 1
                    continue
                
                # 检查是否有英文语言文件
                if not lang_check_result["has_en_us"]:
                    print(f"跳过 {mod_name} - 未包含英文语言文件")
                    stats["no_en_us"] += 1
                    continue
                
                # 检查中文翻译情况
                if lang_check_result["has_zh_cn"]:
                    # 如果启用了深度检查，检查中文翻译是否完整
                    if self._should_check_translation_completeness():
                        completeness = self._check_translation_completeness(mod_path)
                        if completeness["is_complete"]:
                            print(f"跳过 {mod_name} - 已包含完整的中文语言文件 (完整率: {completeness['percentage']:.1f}%)")
                            stats["complete_zh_cn"] += 1
                            continue
                        else:
                            print(f"处理 {mod_name} - 中文翻译不完整 (完整率: {completeness['percentage']:.1f}%)")
                            stats["partial_zh_cn"] += 1
                    else:
                        # 不启用深度检查，只要有中文文件就跳过
                        print(f"跳过 {mod_name} - 已包含中文语言文件")
                        stats["complete_zh_cn"] += 1
                        continue
                else:
                    # 完全没有中文翻译
                    print(f"处理 {mod_name} - 无中文翻译")
                    stats["no_zh_cn"] += 1
                
                # 清理文件夹名称，避免过长路径
                clean_name = self._sanitize_folder_name(mod_name.split('.')[0])
                mod_extract_dir = os.path.join(self.mod_dir, clean_name)
                os.makedirs(mod_extract_dir, exist_ok=True)
                
                print(f"正在提取 {mod_name} 的语言文件...")
                
                # 提取语言文件
                lang_files = self._extract_lang_files(mod_path, mod_extract_dir, lang_check_result["has_zh_cn"])
                
                if lang_files:
                    # 记录mod信息
                    mod_info.append({
                        "name": mod_name,
                        "path": mod_extract_dir,
                        "original_path": mod_path,
                        "lang_files": lang_files,
                        "has_partial_zh_cn": lang_check_result["has_zh_cn"],
                        "translation_status": "partial" if lang_check_result["has_zh_cn"] else "none"
                    })
                    print(f"成功提取 {mod_name} 的语言文件，共 {len(lang_files)} 个")
                    stats["processed"] += 1
                else:
                    # 这种情况应该不会发生，因为我们已经预先检查了
                    print(f"警告: 在 {mod_name} 中未找到可用的语言文件，跳过")
                    # 删除创建的空文件夹
                    if os.path.exists(mod_extract_dir):
                        shutil.rmtree(mod_extract_dir)
            except Exception as e:
                print(f"错误: 处理 {mod_name} 时出错: {str(e)}")
        
        # 创建mod.json
        if mod_info:
            with open(self.mod_json_path, 'w', encoding='utf-8') as f:
                json.dump(mod_info, f, ensure_ascii=False, indent=4)
            
            # 整理翻译文件
            has_to_translate = self._organize_translation_files(mod_info)
            
            # 显示统计信息
            print("\n=== 处理统计 ===")
            print(f"成功处理: {stats['processed']} 个mod文件")
            print(f"  - 无中文翻译: {stats['no_zh_cn']} 个")
            print(f"  - 不完整中文翻译: {stats['partial_zh_cn']} 个")
            print(f"跳过: {stats['no_lang_files'] + stats['no_en_us'] + stats['complete_zh_cn']} 个mod文件")
            print(f"  - 无语言文件: {stats['no_lang_files']} 个")
            print(f"  - 无英文语言文件: {stats['no_en_us']} 个")
            print(f"  - 已有完整中文翻译: {stats['complete_zh_cn']} 个")
            print(f"\nmod信息已保存到 {self.mod_json_path}")
            
            if has_to_translate:
                print(f"整理后的翻译文件已保存到 {self.fanyi_dir}")
                return True
            else:
                print("\n所有内容已通过资源包翻译或mod自身翻译，无需进一步翻译")
                return False
        else:
            print("\n没有找到需要处理的mod文件")
            if stats["complete_zh_cn"] > 0:
                print(f"{stats['complete_zh_cn']} 个mod已包含完整中文翻译")
            if stats["no_lang_files"] > 0:
                print(f"{stats['no_lang_files']} 个mod不包含语言文件")
            if stats["no_en_us"] > 0:
                print(f"{stats['no_en_us']} 个mod不包含英文语言文件")
            return False
    
    def _organize_translation_files(self, mod_info):
        """整理翻译文件，保持原始的assets路径结构"""
        print("\n开始整理翻译文件...")
        
        # 用于存储合并后的翻译内容
        merged_translations = {}
        
        # 用于统计资源包过滤的条目
        total_filtered = 0
        filtered_by_mod = {}
        
        # 遍历所有mod
        for mod in mod_info:
            mod_name = mod["name"]
            filtered_by_mod[mod_name] = 0
            
            # 遍历mod中的语言文件
            for lang_file in mod["lang_files"]:
                if lang_file["language"] == "en_us":
                    # 读取英文语言文件
                    en_path = lang_file["extracted_path"]
                    try:
                        # 使用支持注释的JSON加载器
                        en_data = load_json_with_comments(en_path)
                        
                        # 查找对应的中文文件（如果有）
                        zh_data = {}
                        for zh_file in mod["lang_files"]:
                            if zh_file["language"] == "zh_cn" and os.path.dirname(zh_file["path"]) == os.path.dirname(lang_file["path"]):
                                # 使用支持注释的JSON加载器
                                zh_data = load_json_with_comments(zh_file["extracted_path"])
                                break
                        
                        # 获取语言文件的相对路径（不包括语言代码和扩展名）
                        rel_path = os.path.dirname(lang_file["path"])
                        normalized_path = rel_path.replace('\\', '/').rstrip('/')
                        
                        # 检查该路径是否在资源包翻译中存在
                        resource_pack_translations = {}
                        # 只有当资源包翻译不为空时才进行查找
                        if self.extracted_translations:
                            for rp_path, rp_data in self.extracted_translations.items():
                                # 检查路径是否匹配或者是否包含mod ID
                                if normalized_path.endswith(rp_path) or rp_path.endswith(normalized_path):
                                    resource_pack_translations.update(rp_data)
                                # 检查是否是特定mod的翻译
                                elif '/assets/' in normalized_path:
                                    mod_id = normalized_path.split('/assets/')[1].split('/')[0]
                                    if f'/assets/{mod_id}/' in rp_path:
                                        resource_pack_translations.update(rp_data)
                        
                        # 如果这个路径还没有在合并字典中，初始化它
                        if rel_path not in merged_translations:
                            merged_translations[rel_path] = {
                                "en_us": {},
                                "zh_cn": {},
                                "to_translate": {},
                                "mods": []
                            }
                        
                        # 记录这个文件来自哪个mod
                        if mod_name not in merged_translations[rel_path]["mods"]:
                            merged_translations[rel_path]["mods"].append(mod_name)
                        
                        # 合并英文内容
                        for key, value in en_data.items():
                            merged_translations[rel_path]["en_us"][key] = value
                            
                            # 首先检查资源包中是否有这个键的翻译
                            if key in resource_pack_translations and resource_pack_translations[key]:
                                # 如果资源包中有翻译，使用资源包的翻译
                                merged_translations[rel_path]["zh_cn"][key] = resource_pack_translations[key]
                                filtered_by_mod[mod_name] += 1
                                total_filtered += 1
                            # 如果资源包中没有，检查mod自身的中文翻译
                            elif key not in zh_data or not zh_data[key]:
                                # 如果mod中也没有翻译，添加到待翻译列表
                                merged_translations[rel_path]["to_translate"][key] = value
                        
                        # 合并mod自身的中文内容
                        for key, value in zh_data.items():
                            if value and key not in merged_translations[rel_path]["zh_cn"]:  # 只合并非空的翻译，且不覆盖资源包的翻译
                                merged_translations[rel_path]["zh_cn"][key] = value
                    
                    except Exception as e:
                        print(f"警告: 处理 {en_path} 时出错: {str(e)}")
        
        # 显示过滤统计
        if total_filtered > 0:
            print("\n=== 资源包翻译过滤统计 ===")
            print(f"共使用资源包中的翻译跳过了 {total_filtered} 个条目")
            for mod_name, count in filtered_by_mod.items():
                if count > 0:
                    print(f"  - {mod_name}: {count} 个条目")
        
        # 将整理后的翻译文件写入翻译目录
        for rel_path, content in merged_translations.items():
            # 只有当有待翻译的内容时才创建翻译文件
            if content["to_translate"]:
                # 创建翻译目录
                output_dir = os.path.join(self.fanyi_dir, rel_path)
                os.makedirs(output_dir, exist_ok=True)
                
                # 将待翻译的内容分割成多个文件
                base_filename = "to_translate"
                split_files = split_json_file(
                    content["to_translate"], 
                    output_dir, 
                    base_filename,
                    self.config.get("batch_size", 40)
                )
                
                if split_files:
                    print(f"已创建翻译文件: {rel_path} ({len(content['to_translate'])} 个条目，分成 {len(split_files)} 个文件)")
        
        # 创建索引文件
        index = {"paths": []}
        for rel_path, content in merged_translations.items():
            if content["to_translate"]:  # 只包含有待翻译内容的路径
                # 获取该路径下的所有分割文件
                path_dir = os.path.join(self.fanyi_dir, rel_path)
                split_files = []
                if os.path.exists(path_dir):
                    for f in os.listdir(path_dir):
                        if f.startswith("to_translate") and f.endswith(".json"):
                            split_files.append(f)
                
                if split_files:
                    index["paths"].append({
                        "path": rel_path,
                        "mods": content["mods"],
                        "split_files": sorted(split_files)
                    })
        
        # 写入索引文件
        index_path = os.path.join(self.fanyi_dir, "index.json")
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=4)
        
        # 保存合并的英文和已有中文翻译，用于后续合并
        for rel_path, content in merged_translations.items():
            # 创建输出目录
            output_dir = os.path.join(self.fanyi_dir, rel_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存英文原文
            en_path = os.path.join(output_dir, "en_us.json")
            with open(en_path, 'w', encoding='utf-8') as f:
                json.dump(content["en_us"], f, ensure_ascii=False, indent=4)
            
            # 保存已有的中文翻译
            if content["zh_cn"]:
                zh_path = os.path.join(output_dir, "zh_cn.json")
                with open(zh_path, 'w', encoding='utf-8') as f:
                    json.dump(content["zh_cn"], f, ensure_ascii=False, indent=4)
        
        # 返回是否有需要翻译的内容
        has_to_translate = any(len(content["to_translate"]) > 0 for content in merged_translations.values())
        return has_to_translate
    
    def _should_check_translation_completeness(self):
        """是否检查翻译完整性（可以根据需要修改）"""
        # 默认启用完整性检查
        return True
    
    def _check_translation_completeness(self, zip_path):
        """检查中文翻译是否完整"""
        result = {
            "is_complete": False,
            "en_keys": 0,
            "zh_keys": 0,
            "percentage": 0.0
        }
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 查找英文和中文语言文件
                en_file = None
                zh_file = None
                
                for file_info in zip_ref.infolist():
                    if '/lang/' in file_info.filename and file_info.filename.endswith('.json'):
                        if file_info.filename.endswith('/en_us.json'):
                            en_file = file_info
                        elif file_info.filename.endswith('/zh_cn.json'):
                            zh_file = file_info
                
                if not en_file or not zh_file:
                    return result
                
                # 读取英文和中文语言文件
                try:
                    with zip_ref.open(en_file) as f_en:
                        content_en = f_en.read().decode('utf-8')
                        # 移除注释
                        content_en = re.sub(r'//.*?$', '', content_en, flags=re.MULTILINE)
                        content_en = re.sub(r'/\*.*?\*/', '', content_en, flags=re.DOTALL)
                        en_data = json.loads(content_en)
                    
                    with zip_ref.open(zh_file) as f_zh:
                        content_zh = f_zh.read().decode('utf-8')
                        # 移除注释
                        content_zh = re.sub(r'//.*?$', '', content_zh, flags=re.MULTILINE)
                        content_zh = re.sub(r'/\*.*?\*/', '', content_zh, flags=re.DOTALL)
                        zh_data = json.loads(content_zh)
                except json.JSONDecodeError:
                    # 如果标准JSON解析失败，尝试使用更宽松的方式
                    try:
                        import json5
                        with zip_ref.open(en_file) as f_en:
                            en_data = json5.loads(f_en.read().decode('utf-8'))
                        with zip_ref.open(zh_file) as f_zh:
                            zh_data = json5.loads(f_zh.read().decode('utf-8'))
                    except ImportError:
                        print("警告: json5模块未安装，无法使用更宽松的解析方式")
                        return result
                    except Exception:
                        print("错误: 无法解析语言文件")
                        return result
                
                # 计算翻译完整度
                en_keys = set(en_data.keys())
                zh_keys = set(zh_data.keys())
                result["en_keys"] = len(en_keys)
                result["zh_keys"] = len(zh_keys)
                
                if len(en_keys) > 0:
                    # 计算中文键占英文键的百分比
                    common_keys = en_keys.intersection(zh_keys)
                    result["percentage"] = len(common_keys) / len(en_keys) * 100
                    
                    # 如果中文翻译覆盖了95%以上的英文键，认为是完整的
                    result["is_complete"] = result["percentage"] >= 95
                
                return result
        except Exception as e:
            print(f"检查翻译完整性时出错: {str(e)}")
            return result
    
    def _check_lang_files(self, zip_path):
        """检查mod中的语言文件情况"""
        result = {
            "has_lang_files": False,
            "has_en_us": False,
            "has_zh_cn": False,
            "lang_files": []
        }
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if '/lang/' in file_info.filename and file_info.filename.endswith('.json'):
                        result["has_lang_files"] = True
                        lang_name = os.path.basename(file_info.filename).split('.')[0]
                        result["lang_files"].append(lang_name)
                        
                        # 检查是否包含英文语言文件
                        if lang_name == 'en_us':
                            result["has_en_us"] = True
                        # 检查是否包含中文语言文件
                        elif lang_name == 'zh_cn':
                            result["has_zh_cn"] = True
            
            return result
        except Exception:
            # 如果无法读取zip文件，默认返回False
            return result
    
    def _extract_lang_files(self, zip_path, extract_dir, extract_zh_cn=False):
        """提取语言文件，保持正确的路径结构"""
        lang_files = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 查找所有语言文件
            for file_info in zip_ref.infolist():
                # 跳过目录
                if file_info.filename.endswith('/'):
                    continue
                
                # 检查是否是语言文件
                if '/lang/' in file_info.filename and file_info.filename.endswith('.json'):
                    # 获取语言代码
                    lang_code = os.path.basename(file_info.filename).split('.')[0]
                    
                    # 只提取英文和中文(如果需要)语言文件
                    if lang_code == 'en_us' or (extract_zh_cn and lang_code == 'zh_cn'):
                        try:
                            # 提取文件
                            source = zip_ref.open(file_info)
                            target_path = os.path.join(extract_dir, file_info.filename)
                            
                            # 确保目标目录存在
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            
                            # 写入文件
                            with open(target_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                            source.close()
                            
                            # 记录语言文件信息
                            lang_file_info = {
                                "path": file_info.filename,
                                "extracted_path": target_path,
                                "language": lang_code
                            }
                            lang_files.append(lang_file_info)
                        except Exception as e:
                            print(f"警告: 无法提取语言文件 {file_info.filename}: {e}")
        
        return lang_files

    def translate_with_ai(self):
        """使用AI翻译待翻译的JSON文件"""
        if not os.path.exists(self.fanyi_dir):
            print("错误: 翻译文件夹不存在，请先处理mod文件")
            return False
        
        # 检查API配置
        api_url = self.config.get('api_url')
        api_key = self.config.get('api_key')
        model_id = self.config.get('model_id')
        wait_time = self.config.get('wait_time', 3)
        
        if not api_url or not api_key:
            print("错误: API配置不完整，请先完成配置")
            return False
        
        # 加载索引文件
        index_path = os.path.join(self.fanyi_dir, "index.json")
        if not os.path.exists(index_path):
            print("错误: 索引文件不存在，请先处理mod文件")
            return False
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except Exception as e:
            print(f"错误: 无法读取索引文件: {str(e)}")
            return False
        
        total_paths = len(index.get("paths", []))
        if total_paths == 0:
            print("错误: 没有找到需要翻译的路径")
            return False
        
        print(f"\n=== 开始AI翻译 ===")
        print(f"共有 {total_paths} 个翻译路径需要处理")
        
        # 统计
        stats = {
            "total_files": 0,
            "success_files": 0,
            "failed_files": 0,
            "total_keys": 0,
            "translated_keys": 0
        }
        
        # 遍历每个翻译路径
        for path_info in index.get("paths", []):
            rel_path = path_info.get("path")
            split_files = path_info.get("split_files", [])
            
            if not rel_path or not split_files:
                continue
            
            print(f"\n处理路径: {rel_path}")
            print(f"来自mod: {', '.join(path_info.get('mods', ['未知']))}")
            print(f"共有 {len(split_files)} 个翻译文件")
            
            # 创建对应的翻译结果目录
            target_dir = os.path.join(self.fanyi_ok_dir, rel_path)
            os.makedirs(target_dir, exist_ok=True)
            
            # 遍历每个分割文件
            for file_name in split_files:
                stats["total_files"] += 1
                source_file = os.path.join(self.fanyi_dir, rel_path, file_name)
                target_file = os.path.join(target_dir, file_name)
                
                if not os.path.exists(source_file):
                    print(f"警告: 文件不存在: {source_file}")
                    stats["failed_files"] += 1
                    continue
                
                # 如果目标文件已存在，跳过翻译
                if os.path.exists(target_file):
                    print(f"跳过已翻译文件: {file_name}")
                    # 统计已翻译的键数量
                    try:
                        with open(target_file, 'r', encoding='utf-8') as f:
                            translated_data = json.load(f)
                            stats["translated_keys"] += len(translated_data)
                    except:
                        pass
                    stats["success_files"] += 1
                    continue
                
                try:
                    # 读取待翻译文件
                    with open(source_file, 'r', encoding='utf-8') as f:
                        to_translate = json.load(f)
                    
                    if not to_translate:
                        print(f"警告: 文件为空: {file_name}")
                        stats["failed_files"] += 1
                        continue
                    
                    keys_count = len(to_translate)
                    stats["total_keys"] += keys_count
                    print(f"翻译文件: {file_name} (包含 {keys_count} 个条目)")
                    
                    # 构建提示词
                    prompt = self._build_translation_prompt(to_translate)
                    
                    # 调用AI API进行翻译
                    translated_json = self._call_ai_api(prompt, api_url, api_key, model_id)
                    
                    if translated_json:
                        # 保存翻译结果
                        with open(target_file, 'w', encoding='utf-8') as f:
                            json.dump(translated_json, f, ensure_ascii=False, indent=4)
                        
                        print(f"成功翻译文件: {file_name} (翻译 {len(translated_json)} 个条目)")
                        stats["success_files"] += 1
                        stats["translated_keys"] += len(translated_json)
                    else:
                        print(f"翻译失败: {file_name}")
                        stats["failed_files"] += 1
                    
                    # 等待一段时间，避免API请求过于频繁
                    time.sleep(wait_time)
                    
                except Exception as e:
                    print(f"处理文件 {file_name} 时出错: {str(e)}")
                    stats["failed_files"] += 1
        
        # 显示统计信息
        print("\n=== 翻译统计 ===")
        print(f"总文件数: {stats['total_files']}")
        print(f"成功翻译: {stats['success_files']} 个文件")
        print(f"翻译失败: {stats['failed_files']} 个文件")
        print(f"总条目数: {stats['total_keys']}")
        print(f"已翻译条目: {stats['translated_keys']}")
        
        if stats['success_files'] > 0:
            print(f"\n翻译结果已保存到 {self.fanyi_ok_dir}")
            return True
        else:
            print("\n没有成功翻译任何文件")
            return False
    
    def _build_translation_prompt(self, to_translate):
        """构建AI翻译的提示词"""
        prompt = """你是一个专业的Minecraft模组翻译专家，精通中英文翻译。请将以下Minecraft模组中的英文文本翻译成简体中文。

要求：
1. 保持专业游戏术语的准确性，使用Minecraft中文社区常用的翻译
2. 保留所有占位符（如%s, %d, %1$s等）和格式代码（如§a, §b等）
3. 保留原文中的标点符号风格
4. 直接输出JSON格式的翻译结果，不要有任何解释或额外文本
5. 保持键名不变，只翻译值
6. 不要翻译专有名词、命令和变量名
7. 对于不确定的专有名词，保留英文原文

以下是需要翻译的内容（JSON格式）：
"""
        
        # 添加待翻译的JSON
        prompt += json.dumps(to_translate, ensure_ascii=False, indent=2)
        
        # 添加输出格式要求
        prompt += """

请直接返回翻译后的JSON，格式如下：
{
  "key1": "中文翻译1",
  "key2": "中文翻译2",
  ...
}

不要输出任何其他内容，只输出翻译后的JSON。"""
        
        return prompt
    
    def _call_ai_api(self, prompt, api_url, api_key, model_id):
        """调用AI API进行翻译"""
        try:
            print(f"使用模型: {model_id}")
            print(f"API URL: {api_url}")
            
            # 创建OpenAI客户端
            client = OpenAI(
                api_key=api_key,
                base_url=api_url
            )
            
            # 构建系统提示和用户提示
            system_message = "你是一个专业的Minecraft模组翻译助手，只输出翻译后的JSON格式内容，不包含任何其他文字。"
            
            # 发送请求
            try:
                completion = client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,  # 低温度以保持一致性
                    response_format={"type": "json_object"}  # 强制输出JSON格式
                )
                
                # 提取响应内容
                content = completion.choices[0].message.content
                
                # 尝试解析JSON内容
                try:
                    # 如果内容被包裹在```json和```之间，提取JSON部分
                    json_match = re.search(r'```(?:json)?(.*?)```', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1).strip()
                    
                    # 解析JSON
                    translated_json = json.loads(content)
                    return translated_json
                except json.JSONDecodeError:
                    print("警告: 无法解析AI返回的JSON内容")
                    print(f"返回内容: {content[:200]}...")
                    return None
                
            except Exception as api_error:
                print(f"API调用错误: {str(api_error)}")
                return None
                
        except Exception as e:
            print(f"调用AI API时出错: {str(e)}")
            return None
    
    def merge_translations(self):
        """合并翻译结果，生成最终的zh_cn.json文件"""
        if not os.path.exists(self.fanyi_ok_dir):
            print("错误: 翻译结果文件夹不存在，请先完成翻译")
            return False
        
        # 加载索引文件
        index_path = os.path.join(self.fanyi_dir, "index.json")
        if not os.path.exists(index_path):
            print("错误: 索引文件不存在")
            return False
        
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except Exception as e:
            print(f"错误: 无法读取索引文件: {str(e)}")
            return False
        
        print("\n=== 开始合并翻译结果 ===")
        
        # 统计
        stats = {
            "total_paths": 0,
            "merged_paths": 0,
            "total_keys": 0,
            "merged_keys": 0
        }
        
        # 清空并创建输出目录
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 遍历每个翻译路径
        for path_info in index.get("paths", []):
            rel_path = path_info.get("path")
            split_files = path_info.get("split_files", [])
            
            if not rel_path or not split_files:
                continue
            
            stats["total_paths"] += 1
            
            # 源文件夹和目标文件夹
            source_dir = os.path.join(self.fanyi_ok_dir, rel_path)
            if not os.path.exists(source_dir):
                print(f"警告: 翻译结果文件夹不存在: {rel_path}")
                continue
            
            # 创建输出目录
            output_path = os.path.join(self.output_dir, rel_path)
            os.makedirs(output_path, exist_ok=True)
            
            # 合并所有分割文件
            merged_data = {}
            missing_files = []
            
            for file_name in split_files:
                file_path = os.path.join(source_dir, file_name)
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            merged_data.update(data)
                            stats["total_keys"] += len(data)
                    except Exception as e:
                        print(f"警告: 无法读取文件 {file_path}: {str(e)}")
                else:
                    missing_files.append(file_name)
            
            if missing_files:
                print(f"警告: 路径 {rel_path} 中有 {len(missing_files)} 个文件未找到翻译结果")
                for file in missing_files[:5]:  # 只显示前5个
                    print(f"  - {file}")
                if len(missing_files) > 5:
                    print(f"  - ... 等 {len(missing_files) - 5} 个文件")
            
            if merged_data:
                # 写入合并后的zh_cn.json
                output_file = os.path.join(output_path, "zh_cn.json")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(merged_data, f, ensure_ascii=False, indent=4)
                
                stats["merged_paths"] += 1
                stats["merged_keys"] += len(merged_data)
                print(f"成功合并路径 {rel_path} 的翻译结果，共 {len(merged_data)} 个条目")
        
        # 复制根目录下的app文件夹内容到输出目录
        self._copy_app_content_to_output()
        
        # 显示统计信息
        print("\n=== 合并统计 ===")
        print(f"总路径数: {stats['total_paths']}")
        print(f"成功合并: {stats['merged_paths']} 个路径")
        print(f"总条目数: {stats['total_keys']}")
        print(f"合并条目: {stats['merged_keys']} 个")
        
        if stats['merged_paths'] > 0:
            print(f"\n合并结果已保存到 {self.output_dir}")
            
            # 打包输出目录为ZIP文件
            zip_result = self._create_output_zip()
            if zip_result:
                print(f"已将输出内容打包为: {zip_result}")
            
            print("你可以将翻译资源包加到游戏中，或者复制到mod的assets目录中")
            return True
        else:
            print("\n没有成功合并任何翻译结果")
            return False
    
    def _copy_app_content_to_output(self):
        """复制根目录下的app文件夹内容到输出目录"""
        app_dir = os.path.join(os.getcwd(), "app")
        if not os.path.exists(app_dir):
            print("注意: 根目录下没有找到app文件夹，跳过复制")
            return
        
        print("\n=== 复制app文件夹内容 ===")
        
        try:
            # 遍历app目录下的所有文件和文件夹
            for item in os.listdir(app_dir):
                source_path = os.path.join(app_dir, item)
                target_path = os.path.join(self.output_dir, item)
                
                # 如果是目录，递归复制整个目录
                if os.path.isdir(source_path):
                    if os.path.exists(target_path):
                        shutil.rmtree(target_path)
                    shutil.copytree(source_path, target_path)
                    print(f"已复制目录: {item}/")
                # 如果是文件，直接复制
                else:
                    shutil.copy2(source_path, target_path)
                    print(f"已复制文件: {item}")
            
            print(f"成功将app文件夹内容复制到输出目录")
        except Exception as e:
            print(f"复制app文件夹内容时出错: {str(e)}")
    
    def _create_output_zip(self):
        """将输出目录打包为ZIP文件"""
        try:
            # 生成带时间戳的文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"翻译资源包_{timestamp}.zip"
            zip_path = os.path.join(os.getcwd(), zip_filename)
            
            print(f"\n=== 创建资源包ZIP ===")
            print(f"打包目录: {self.output_dir}")
            print(f"输出文件: {zip_filename}")
            
            # 创建ZIP文件
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 获取输出目录的绝对路径
                abs_output_dir = os.path.abspath(self.output_dir)
                
                # 记录添加的文件数量
                file_count = 0
                
                # 遍历输出目录中的所有文件和子目录
                for root, dirs, files in os.walk(self.output_dir):
                    # 计算相对路径
                    rel_root = os.path.relpath(root, self.output_dir)
                    
                    # 添加文件到ZIP
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算在ZIP中的路径（相对于输出目录）
                        if rel_root == ".":
                            zip_path = file
                        else:
                            zip_path = os.path.join(rel_root, file)
                        
                        # 添加到ZIP
                        zipf.write(file_path, zip_path)
                        file_count += 1
            
            print(f"打包完成，共添加 {file_count} 个文件")
            return zip_filename
            
        except Exception as e:
            print(f"创建ZIP文件时出错: {str(e)}")
            return None

def main_menu():
    """显示主菜单并处理用户选择"""
    translator = ModTranslator()
    
    while True:
        try:
            print("\n=== Minecraft Mod 汉化工具 ===")
            print(f"版本: {VERSION_INFO['version']} ({VERSION_INFO['release_date']})")
            print("1. 选择mod文件")
            print("2. 选择已有翻译资源包（可选）")
            print("3. 处理已选择的mod文件")
            print("4. 使用AI翻译")
            print("5. 合并翻译结果")
            print("6. 清理临时文件夹")
            print("7. 修改配置")
            print("8. 检查更新")
            print("0. 退出程序")
            
            choice = input("\n请选择操作 [0-8]: ").strip()
            
            if choice == '0':
                print("正在退出程序...")
                break
            elif choice == '1':
                translator.select_mods_interactively()
            elif choice == '2':
                translator.select_resource_packs_interactively()
            elif choice == '3':
                if not translator.selected_mods:
                    print("请先选择mod文件")
                    continue
                translator.process_mods()
            elif choice == '4':
                translator.translate_with_ai()
            elif choice == '5':
                translator.merge_translations()
            elif choice == '6':
                translator.clean_temp_folder()
                print("已清理临时文件夹")
            elif choice == '7':
                # 重新创建配置
                translator.config.create_new_config()
            elif choice == '8':
                # 检查更新
                print("\n=== 检查更新 ===")
                auto_update = translator.config.get('auto_update', False)
                check_for_updates(auto_update=auto_update)
            else:
                print("无效的选择，请重试")
        except KeyboardInterrupt:
            print("\n\n程序被中断，正在退出...")
            break
        except Exception as e:
            print(f"\n发生错误: {str(e)}")
            print("请重试或退出程序")

if __name__ == "__main__":
    print("欢迎使用 Minecraft Mod 汉化工具")
    print(f"版本: {VERSION_INFO['version']} ({VERSION_INFO['release_date']})")
    
    # 如果配置允许，在启动时检查更新
    if REQUESTS_AVAILABLE:
        # 尝试加载配置以获取auto_update设置
        try:
            config = Config()
            auto_update = config.get('auto_update', False)
            print("正在检查更新...")
            check_for_updates(auto_update=auto_update)
        except Exception as e:
            print(f"检查更新时出错: {str(e)}")
            # 如果配置加载失败，仍然检查更新但不自动更新
            print("正在检查更新...")
            check_for_updates()
    
    try:
        main_menu()
    except Exception as e:
        print(f"\n程序遇到错误: {str(e)}")
    finally:
        print("\n程序已退出") 