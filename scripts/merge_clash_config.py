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

def merge_all_proxies(subscription_files):
    """从所有订阅文件中提取并合并代理节点"""
    all_proxies = []
    seen_servers = set()

    for sub_file in subscription_files:
        print(f"\n读取订阅文件: {sub_file.name}")
        sub_data = load_yaml(sub_file)

        if not sub_data or 'proxies' not in sub_data:
            print(f"  ⚠️  文件中没有代理节点")
            continue

        proxies = sub_data['proxies']
        print(f"  找到 {len(proxies)} 个代理节点")

        # 去重：基于服务器地址和端口
        for proxy in proxies:
            server = proxy.get('server', '')
            port = proxy.get('port', 0)
            server_key = f"{server}:{port}"

            if server and server_key not in seen_servers:
                all_proxies.append(proxy)
                seen_servers.add(server_key)

    print(f"\n✓ 总共收集到 {len(all_proxies)} 个唯一代理节点")
    return all_proxies

def merge_with_template(template_data, all_proxies):
    """将所有代理节点合并到模板中"""
    if not template_data:
        return None

    # 复制模板
    merged = template_data.copy()

    # 替换代理节点
    merged['proxies'] = all_proxies

    print(f"✓ 已将 {len(all_proxies)} 个代理节点合并到模板")

    return merged

def main():
    """主函数"""
    print("=" * 60)
    print("Clash 配置合并工具")
    print("=" * 60)

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n✓ 输出目录已创建: {OUTPUT_DIR}")

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

    # 从所有订阅文件中提取并合并代理节点
    all_proxies = merge_all_proxies(subscription_files)

    if not all_proxies:
        print("\n❌ 没有找到任何代理节点")
        return 1

    # 与模板合并
    print("\n正在与 ACL4SSR 模板合并...")
    merged_config = merge_with_template(template_data, all_proxies)

    if not merged_config:
        print("❌ 合并失败")
        return 1

    # 保存最终配置
    output_file = OUTPUT_DIR / "clash.yaml"
    print(f"\n保存最终配置到: {output_file}")

    if not save_yaml(merged_config, output_file):
        return 1

    # 输出结果
    print("\n" + "=" * 60)
    print(f"✓ 配置生成成功！")
    print(f"  输出文件: {output_file}")
    print(f"  代理节点: {len(all_proxies)} 个")
    print(f"  策略组: {len(merged_config.get('proxy-groups', []))} 个")
    print(f"  规则数: {len(merged_config.get('rules', []))} 条")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    exit(main())
