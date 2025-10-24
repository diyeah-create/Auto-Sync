#!/usr/bin/env python3
"""
合并多个 Clash 订阅源并生成符合 OpenClash 标准的配置文件（ACL4SSR 规则）
使用本地同步的 ACL4SSR 模板，动态插入合并后的节点
"""
import os
import yaml
import requests
from typing import Dict, List, Any


def load_yaml_from_url(url: str) -> Dict[str, Any]:
    """从 URL 加载 YAML 配置"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return yaml.safe_load(response.text) or {}
    except Exception as e:
        print(f"加载 {url} 失败: {e}")
        return {}


def load_yaml_from_file(file_path: str) -> Dict[str, Any]:
    """从本地文件加载 YAML 配置"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"加载本地文件 {file_path} 失败: {e}")
        return {}


def clean_proxy_name(proxy: Dict[str, Any], index: int) -> str:
    """清理并规范化节点名称"""
    import re
    
    # 提取基本信息
    server = proxy.get('server', 'unknown')
    port = proxy.get('port', 0)
    proxy_type = proxy.get('type', 'unknown').upper()
    
    # 尝试从原名称中提取地区信息
    original_name = proxy.get('name', '')
    
    # 地区映射
    region_map = {
        '🇭🇰': 'HK', '香港': 'HK', 'HK': 'HK', 'Hong Kong': 'HK',
        '🇨🇳': 'TW', '台湾': 'TW', 'TW': 'TW', 'Taiwan': 'TW',
        '🇸🇬': 'SG', '新加坡': 'SG', 'SG': 'SG', 'Singapore': 'SG',
        '🇯🇵': 'JP', '日本': 'JP', 'JP': 'JP', 'Japan': 'JP',
        '🇺🇸': 'US', '美国': 'US', 'US': 'US', 'United States': 'US',
        '🇰🇷': 'KR', '韩国': 'KR', 'KR': 'KR', 'Korea': 'KR',
    }
    
    # 尝试识别地区
    region = 'XX'
    for key, value in region_map.items():
        if key in original_name:
            region = value
            break
    
    # 如果没有识别到地区，尝试从服务器地址推断
    if region == 'XX':
        if any(x in server.lower() for x in ['hk', 'hong']):
            region = 'HK'
        elif any(x in server.lower() for x in ['tw', 'taiwan']):
            region = 'TW'
        elif any(x in server.lower() for x in ['sg', 'singapore']):
            region = 'SG'
        elif any(x in server.lower() for x in ['jp', 'japan', 'tokyo']):
            region = 'JP'
        elif any(x in server.lower() for x in ['us', 'america']):
            region = 'US'
        elif any(x in server.lower() for x in ['kr', 'korea']):
            region = 'KR'
    
    # 简化服务器地址（只保留域名或IP的前几位）
    if '.' in server:
        parts = server.split('.')
        if len(parts) >= 2:
            server_short = f"{parts[0][:8]}...{parts[-1]}"
        else:
            server_short = server[:15]
    else:
        server_short = server[:15]
    
    # 生成规范化名称
    clean_name = f"[{region}] {proxy_type} {server_short}:{port}"
    
    return clean_name


def merge_proxies(configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并多个配置中的代理节点并清理名称"""
    all_proxies = []
    seen_servers = set()
    
    proxy_index = 1
    for config in configs:
        proxies = config.get('proxies', [])
        for proxy in proxies:
            server = proxy.get('server', '')
            port = proxy.get('port', 0)
            server_key = f"{server}:{port}"
            
            # 去重：基于服务器地址和端口
            if server and server_key not in seen_servers:
                # 清理节点名称
                proxy['name'] = clean_proxy_name(proxy, proxy_index)
                all_proxies.append(proxy)
                seen_servers.add(server_key)
                proxy_index += 1
    
    return all_proxies


def create_openclash_config(proxies: List[Dict[str, Any]], template_path: str) -> Dict[str, Any]:
    """生成符合 OpenClash 标准的完整配置（基于本地 ACL4SSR 模板）"""
    
    # 加载本地 ACL4SSR 模板
    print(f"正在加载本地 ACL4SSR 模板: {template_path}")
    template = load_yaml_from_file(template_path)
    
    if not template:
        print("错误: 无法加载 ACL4SSR 模板")
        return {}
    
    print("ACL4SSR 模板加载成功")
    
    # 插入合并后的节点
    template['proxies'] = proxies
    
    # 添加基础配置（如果模板中没有）
    if 'port' not in template:
        template['port'] = 7890
    if 'socks-port' not in template:
        template['socks-port'] = 7891
    if 'allow-lan' not in template:
        template['allow-lan'] = True
    if 'mode' not in template:
        template['mode'] = 'Rule'
    if 'log-level' not in template:
        template['log-level'] = 'info'
    if 'external-controller' not in template:
        template['external-controller'] = '0.0.0.0:9090'
    
    # 添加 DNS 配置（如果模板中没有）
    if 'dns' not in template:
        template['dns'] = {
            'enable': True,
            'listen': '0.0.0.0:53',
            'enhanced-mode': 'fake-ip',
            'nameserver': [
                '223.5.5.5',
                '119.29.29.29'
            ],
            'fallback': [
                'https://1.1.1.1/dns-query',
                'https://dns.google/dns-query'
            ]
        }
    
    print(f"配置生成完成，包含 {len(proxies)} 个节点")
    print(f"代理组数量: {len(template.get('proxy-groups', []))}")
    print(f"规则提供者数量: {len(template.get('rule-providers', {}))}")
    print(f"规则数量: {len(template.get('rules', []))}")
    
    return template


def main():
    """主函数"""
    # 订阅源列表
    sources = [
        'https://raw.githubusercontent.com/go4sharing/sub/main/worker.yaml',
        'https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml'
    ]
    
    # ACL4SSR 模板路径
    template_path = 'templates/ACL4SSR_Online_Full.yaml'
    
    print("=" * 60)
    print("Clash 配置合并工具 (ACL4SSR 规则)")
    print("=" * 60)
    print()
    
    # 检查模板文件是否存在
    if not os.path.exists(template_path):
        print(f"错误: ACL4SSR 模板文件不存在: {template_path}")
        print("请先运行工作流同步模板文件")
        return
    
    print("开始拉取订阅源...")
    configs = []
    for url in sources:
        print(f"正在拉取: {url}")
        config = load_yaml_from_url(url)
        if config:
            proxy_count = len(config.get('proxies', []))
            print(f"  ✓ 成功，获取 {proxy_count} 个节点")
            configs.append(config)
        else:
            print(f"  ✗ 失败")
    
    if not configs:
        print("\n错误: 没有成功加载任何配置")
        return
    
    print(f"\n成功加载 {len(configs)} 个配置源")
    
    # 合并代理节点
    print("\n正在合并代理节点...")
    merged_proxies = merge_proxies(configs)
    print(f"合并后共 {len(merged_proxies)} 个节点（已去重）")
    
    # 生成 OpenClash 配置
    print("\n正在生成 OpenClash 配置...")
    openclash_config = create_openclash_config(merged_proxies, template_path)
    
    if not openclash_config:
        print("\n错误: 配置生成失败")
        return
    
    # 保存到文件
    output_dir = 'clash/GG'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'clash_1.yaml')
    
    print(f"\n正在保存配置到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(openclash_config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    print("\n" + "=" * 60)
    print("✓ 配置生成完成!")
    print("=" * 60)
    print(f"\n配置文件: {output_file}")
    print(f"节点数量: {len(merged_proxies)}")


if __name__ == '__main__':
    main()
