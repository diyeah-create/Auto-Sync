#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clash 配置合并脚本
从 clash 目录读取订阅配置，与 ACL4SSR 模板合并，生成最终配置
"""

import os
import yaml
import requests
from pathlib import Path

# 配置路径
CLASH_DIR = Path("clash")
TEMPLATE_FILE = Path("templates/ACL4SSR_Online_Full.yaml")
OUTPUT_DIR = CLASH_DIR / "GG"

def load_yaml(file_path):
    """加载 YAML 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 加载文件失败 {file_path}: {e}")
        return None

def save_yaml(data, file_path):
    """保存 YAML 文件"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        print(f"✓ 保存配置: {file_path}")
        return True
    except Exception as e:
        print(f"❌ 保存文件失败 {file_path}: {e}")
        return False

def merge_configs(template_data, subscription_data):
    """合并模板和订阅配置"""
    if not template_data or not subscription_data:
        return None

    # 复制模板
    merged = template_data.copy()

    # 合并代理节点
    if 'proxies' in subscription_data:
        merged['proxies'] = subscription_data['proxies']
        print(f"  ✓ 合并了 {len(subscription_data['proxies'])} 个代理节点")

    # 如果订阅中有 proxy-groups，也可以选择性合并
    if 'proxy-groups' in subscription_data:
        # 这里可以根据需要决定是使用模板的策略组还是订阅的策略组
        # 默认使用模板的策略组，但可以添加订阅中的节点到策略组
        pass

    return merged

def process_subscription_file(sub_file, template_data):
    """处理单个订阅文件"""
    print(f"\n处理订阅文件: {sub_file.name}")

    # 加载订阅配置
    sub_data = load_yaml(sub_file)
    if not sub_data:
        return False

    # 合并配置
    merged_data = merge_configs(template_data, sub_data)
    if not merged_data:
        print(f"  ❌ 合并配置失败")
        return False

    # 生成输出文件名
    output_file = OUTPUT_DIR / sub_file.name

    # 保存合并后的配置
    return save_yaml(merged_data, output_file)

def main():
    """主函数"""
    print("=" * 60)
    print("Clash 配置合并工具")
    print("=" * 60)

    # 检查模板文件
    if not TEMPLATE_FILE.exists():
        print(f"❌ 模板文件不存在: {TEMPLATE_FILE}")
        print("请先运行 'Sync ACL4SSR template' 步骤")
        return 1

    print(f"\n✓ 加载模板: {TEMPLATE_FILE}")
    template_data = load_yaml(TEMPLATE_FILE)
    if not template_data:
        return 1

    # 查找所有订阅配置文件
    subscription_files = []
    if CLASH_DIR.exists():
        # 查找 clash 目录下的 yaml/yml 文件，但排除 GG 子目录
        for pattern in ['*.yaml', '*.yml']:
            for file in CLASH_DIR.glob(pattern):
                if file.is_file() and 'GG' not in file.parts:
                    subscription_files.append(file)

    if not subscription_files:
        print(f"\n⚠️  在 {CLASH_DIR} 目录下未找到订阅配置文件")
        print("请先运行 'Sync Clash repository' 工作流")
        return 0

    print(f"\n找到 {len(subscription_files)} 个订阅配置文件")

    # 处理每个订阅文件
    success_count = 0
    for sub_file in subscription_files:
        if process_subscription_file(sub_file, template_data):
            success_count += 1

    # 输出结果
    print("\n" + "=" * 60)
    print(f"处理完成: {success_count}/{len(subscription_files)} 个文件成功")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    return 0 if success_count > 0 else 1

if __name__ == "__main__":
    exit(main())
    # 参考: https://github.com/unicode-org/cldr
