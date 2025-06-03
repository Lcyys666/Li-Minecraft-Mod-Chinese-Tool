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
try:
    from openai import OpenAI
except ImportError:
    print("警告: OpenAI库未安装，请运行 'pip install openai' 安装")

class Config:
    """配置管理类"""
    def __init__(self):
        self.config_file = "config.json"
        self.default_config = {
            "api_url": "",
            "api_key": "",
            "model_id": "",
            "wait_time": 3,
            "batch_size": 40  # 每个翻译文件的最大条目数
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
        self.mod_json_path = os.path.join(self.mod_dir, "mod.json")
        self.selected_mods = []
        
        # 创建隐藏的tkinter根窗口，用于文件选择对话框
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏窗口
        
        # 确保翻译结果目录存在
        os.makedirs(self.fanyi_ok_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
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
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.mod_dir, exist_ok=True)
        os.makedirs(self.fanyi_dir, exist_ok=True)
        os.makedirs(self.fanyi_ok_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
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
    
    def process_mods(self):
        """处理所有选定的mod文件"""
        if not self.selected_mods:
            print("错误: 没有选择mod文件")
            return False
        
        # 清理并创建TEMP文件夹
        self.clean_temp_folder()
        
        mod_info = []
        stats = {
            "processed": 0,         # 成功处理的mod数量
            "no_lang_files": 0,     # 没有语言文件的mod数量
            "no_en_us": 0,          # 没有英文语言文件的mod数量
            "complete_zh_cn": 0,    # 已有完整中文翻译的mod数量
            "partial_zh_cn": 0,     # 有不完整中文翻译的mod数量
            "no_zh_cn": 0           # 完全没有中文翻译的mod数量
        }
        
        print(f"\n开始处理 {len(self.selected_mods)} 个mod文件...")
        
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
            self._organize_translation_files(mod_info)
            
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
            print(f"整理后的翻译文件已保存到 {self.fanyi_dir}")
            return True
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
        
        # 遍历所有mod
        for mod in mod_info:
            mod_name = mod["name"]
            
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
                            
                            # 如果这个键在中文文件中不存在，或者是空字符串，将其添加到待翻译列表
                            if key not in zh_data or not zh_data[key]:
                                merged_translations[rel_path]["to_translate"][key] = value
                        
                        # 合并中文内容
                        for key, value in zh_data.items():
                            if value:  # 只合并非空的翻译
                                merged_translations[rel_path]["zh_cn"][key] = value
                    
                    except Exception as e:
                        print(f"警告: 处理文件 {en_path} 时出错: {str(e)}")
        
        # 创建索引文件
        index = {
            "total_paths": len(merged_translations),
            "paths": []
        }
        
        # 将合并后的翻译内容写入文件，保持原始路径结构
        for rel_path, data in merged_translations.items():
            # 确保rel_path是正确的格式(assets/xxx/lang)
            if not rel_path.startswith('assets/'):
                print(f"警告: 忽略非标准路径 {rel_path}")
                continue
                
            # 创建目标文件夹
            target_dir = os.path.join(self.fanyi_dir, rel_path)
            os.makedirs(target_dir, exist_ok=True)
            
            # 写入待翻译文件，如果内容较多则分割成多个文件
            split_files = []
            if data["to_translate"]:
                # 计算待翻译内容的数量
                to_translate_count = len(data["to_translate"])
                
                if to_translate_count > 40:
                    # 如果待翻译内容超过40项，分割成多个文件
                    print(f"路径 {rel_path} 的待翻译内容较多 ({to_translate_count} 项)，分割成多个文件")
                    split_files = split_json_file(
                        data["to_translate"], 
                        target_dir, 
                        "fanyi", 
                        items_per_file=40
                    )
                    # 记录分割文件的相对路径
                    split_files = [os.path.basename(f) for f in split_files]
                else:
                    # 如果待翻译内容不多，只创建一个文件
                    fanyi_path = os.path.join(target_dir, "fanyi.json")
                    with open(fanyi_path, 'w', encoding='utf-8') as f:
                        json.dump(data["to_translate"], f, ensure_ascii=False, indent=4)
                    split_files = ["fanyi.json"]
            
            # 记录路径信息
            path_info = {
                "path": rel_path,
                "mods": data["mods"],
                "total_keys": len(data["en_us"]),
                "translated_keys": len(data["zh_cn"]),
                "to_translate_keys": len(data["to_translate"]),
                "split_files": split_files
            }
            index["paths"].append(path_info)
        
        # 写入索引文件
        with open(os.path.join(self.fanyi_dir, "index.json"), 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=4)
        
        print(f"整理完成，共处理 {len(merged_translations)} 个翻译路径")
    
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
            print("1. 选择mod文件")
            print("2. 处理已选择的mod文件")
            print("3. 使用AI翻译")
            print("4. 合并翻译结果")
            print("5. 清理临时文件夹")
            print("6. 修改配置")
            print("0. 退出程序")
            
            choice = input("\n请选择操作 [0-6]: ").strip()
            
            if choice == '0':
                print("正在退出程序...")
                break
            elif choice == '1':
                translator.select_mods_interactively()
            elif choice == '2':
                if not translator.selected_mods:
                    print("请先选择mod文件")
                    continue
                translator.process_mods()
            elif choice == '3':
                translator.translate_with_ai()
            elif choice == '4':
                translator.merge_translations()
            elif choice == '5':
                translator.clean_temp_folder()
                print("已清理临时文件夹")
            elif choice == '6':
                # 重新创建配置
                translator.config.create_new_config()
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
    try:
        main_menu()
    except Exception as e:
        print(f"\n程序遇到错误: {str(e)}")
    finally:
        print("\n程序已退出") 