#!/usr/bin/env python3
"""
使用 subconverter 处理 Clash 订阅源并生成配置文件
"""
import os
import yaml
import requests
from typing import Dict, List, Any
from urllib.parse import quote


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


def convert_with_subconverter(sources: List[str], subconverter_url: str, config: str = 'ACL4SSR_Online_Full') -> Dict[str, Any]:
    """使用 subconverter 转换订阅"""
    # 合并多个订阅源
    urls = '|'.join(sources)
    
    # 构建参数（不编码，直接传递给 subconverter）
    config_url = f'https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/config/{config}.ini'
    
    # 使用 params 但设置 safe 参数避免过度编码
    from urllib.parse import urlencode
    params = {
        'target': 'clash',
        'url': urls,
        'config': config_url,
        'emoji': 'true',
        'list': 'false',
        'udp': 'true',
        'tfo': 'true',
        'scv': 'true',
        'fdn': 'true',
        'sort': 'false'
    }
    
    # 手动构建查询字符串，保留特殊字符
    query_string = urlencode(params, safe=':/')
    full_url = f"{subconverter_url}/sub?{query_string}"
    
    print(f"正在调用 subconverter: {subconverter_url}")
    print(f"配置规则: {config}")
    
    try:
        response = requests.get(full_url, timeout=60)
        response.raise_for_status()
        
        # 解析返回的 YAML（处理 !<str> 等自定义标签）
        # 添加自定义构造器处理 !<str> 标签
        def str_constructor(loader, node):
            return loader.construct_scalar(node)
        
        yaml.add_constructor('!<str>', str_constructor, Loader=yaml.FullLoader)
        config_data = yaml.load(response.text, Loader=yaml.FullLoader)
        
        if not config_data:
            print("错误: subconverter 返回空配置")
            return {}
        
        proxy_count = len(config_data.get('proxies', []))
        group_count = len(config_data.get('proxy-groups', []))
        rule_count = len(config_data.get('rules', []))
        
        print(f"✓ 转换成功")
        print(f"  节点数量: {proxy_count}")
        print(f"  代理组数量: {group_count}")
        print(f"  规则数量: {rule_count}")
        
        return config_data
        
    except Exception as e:
        print(f"✗ subconverter 转换失败: {e}")
        return {}


def main():
    """主函数"""
    # 订阅源列表
    sources = [
        'https://raw.githubusercontent.com/go4sharing/sub/main/worker.yaml',
        'https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml'
    ]
    
    # subconverter 服务地址（优先使用环境变量，默认使用公共 API）
    subconverter_url = os.getenv('SUBCONVERTER_URL', 'https://sub.bestool.cc')
    
    print("=" * 60)
    print("Clash 配置转换工具 (subconverter + ACL4SSR)")
    print("=" * 60)
    print()
    
    print(f"订阅源数量: {len(sources)}")
    for i, url in enumerate(sources, 1):
        print(f"  {i}. {url}")
    print()
    
    # 使用 subconverter 转换
    print("正在使用 subconverter 处理订阅...")
    config_data = convert_with_subconverter(sources, subconverter_url)
    
    if not config_data:
        print("\n错误: 配置转换失败")
        return
    
    # 保存到文件
    output_dir = 'clash/GG'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'clash_1.yaml')
    
    print(f"\n正在保存配置到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    print("\n" + "=" * 60)
    print("✓ 配置生成完成!")
    print("=" * 60)
    print(f"\n配置文件: {output_file}")
    print(f"节点数量: {len(config_data.get('proxies', []))}")


if __name__ == '__main__':
    main()
