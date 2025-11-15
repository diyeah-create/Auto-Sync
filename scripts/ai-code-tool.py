#!/usr/bin/env python3
"""同步指定仓库的最新发布资产（仅元数据模式）。"""
from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
TARGET_ROOT = Path("Ai-Code-Tool")
REPOSITORIES: List[Tuple[str, str]] = [
    ("zhaochengcube", "augment-token-mng"),
    ("zhaochengcube", "augment-code-auto"),
    ("Zheng-up", "augment-code-z"),
    ("Zheng-up", "zAugment"),
    ("wuqi-y", "auto-cursor-releases"),
    ("crispvibe", "Windsurf-Tool"),
]

# 文件大小限制（字节），默认 10MB
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", 10 * 1024 * 1024))
# 是否仅保存元数据
METADATA_ONLY = os.environ.get("METADATA_ONLY", "false").lower() == "true"


def fetch_json(url: str, token: str) -> Dict[str, object]:
    """调用 GitHub API 并返回 JSON 数据。"""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "release-sync-bot",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:  # type: ignore[arg-type]
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        print(f"HTTP 错误 {e.code}: {e.reason}")
        if e.code == 404:
            print(f"URL 不存在: {url}")
        elif e.code == 403:
            print("API 速率限制或权限不足")
        raise
    except URLError as e:
        print(f"网络错误: {e.reason}")
        raise


def download_asset(asset: Dict[str, object], token: str, destination: Path) -> bool:
    """下载发布资产到指定路径。返回是否成功。"""
    asset_url = str(asset.get("url"))
    if not asset_url:
        print("  错误: 发布资产缺少下载地址")
        return False
    
    # 检查文件大小
    asset_size = int(asset.get("size", 0))
    if asset_size > MAX_FILE_SIZE:
        print(f"  跳过 {destination.name} (大小: {asset_size / 1024 / 1024:.2f} MB，超过限制)")
        return False
    
    headers = {
        "Accept": "application/octet-stream",
        "Authorization": f"token {token}",
        "User-Agent": "release-sync-bot",
    }
    request = Request(asset_url, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:  # type: ignore[arg-type]
            with destination.open("wb") as file_handle:
                shutil.copyfileobj(response, file_handle)
        print(f"  ✓ 下载成功: {destination.name}")
        return True
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        return False


def sync_repository(owner: str, name: str, token: str) -> bool:
    """同步单个仓库的最新发布，返回是否产生变更。"""
    print(f"\n处理仓库: {owner}/{name}")
    metadata_url = f"{API_ROOT}/repos/{owner}/{name}/releases/latest"
    
    try:
        release = fetch_json(metadata_url, token)
    except HTTPError as error:
        if error.code == 404:
            print(f"  ⚠ 仓库 {owner}/{name} 没有发布版本")
            return False
        print(f"  ✗ 请求失败，状态码: {error.code}")
        return False
    except URLError as error:
        print(f"  ✗ 网络错误: {error.reason}")
        return False
    except Exception as error:
        print(f"  ✗ 未知错误: {error}")
        traceback.print_exc()
        return False

    tag_name = str(release.get("tag_name") or "").strip()
    assets = release.get("assets")

    if not tag_name:
        print(f"  ✗ 最新发布缺少 tag_name 字段")
        return False
    
    if not isinstance(assets, list):
        assets = []

    project_dir = TARGET_ROOT / name
    version_file = project_dir / "version.txt"

    current_version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else ""
    if current_version == tag_name:
        print(f"  ✓ 已是最新版本 {tag_name}")
        return False

    print(f"  发现新版本: {current_version or '(无)'} -> {tag_name}")

    # 清理旧版本
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 保存资产信息到 metadata.json
    assets_info = []
    downloaded_count = 0
    
    if assets:
        print(f"  处理 {len(assets)} 个资产:")
        for asset in assets:
            asset_name = str(asset.get("name") or "").strip()
            if not asset_name:
                continue
            
            asset_info = {
                "name": asset_name,
                "size": asset.get("size"),
                "download_url": asset.get("browser_download_url"),
                "content_type": asset.get("content_type"),
            }
            assets_info.append(asset_info)
            
            # 如果不是仅元数据模式，且文件小于限制，则下载
            if not METADATA_ONLY:
                destination = project_dir / asset_name
                if download_asset(asset, token, destination):
                    downloaded_count += 1
            else:
                print(f"  • {asset_name} ({asset.get('size', 0) / 1024 / 1024:.2f} MB)")
        
        if not METADATA_ONLY:
            print(f"  下载完成: {downloaded_count}/{len(assets)}")
    else:
        print(f"  ⚠ 没有资产文件")

    # 保存版本信息
    version_file.write_text(tag_name, encoding="utf-8")
    
    # 保存元数据
    metadata_file = project_dir / "metadata.json"
    metadata_content = {
        "repository": f"{owner}/{name}",
        "tag": tag_name,
        "release_id": release.get("id"),
        "html_url": release.get("html_url"),
        "published_at": release.get("published_at"),
        "fetched_at": os.environ.get("GITHUB_RUN_DATETIME"),
        "assets": assets_info,
    }
    metadata_file.write_text(
        json.dumps(metadata_content, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"  ✓ 更新完成")
    return True


def main() -> None:
    """主函数。"""
    print("=" * 70)
    print("GitHub Release 同步工具")
    print("=" * 70)
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("✗ 错误: 缺少 GITHUB_TOKEN 环境变量")
        sys.exit(1)

    mode = "仅元数据" if METADATA_ONLY else f"下载文件（限制 {MAX_FILE_SIZE / 1024 / 1024:.0f} MB）"
    print(f"同步模式: {mode}")
    print(f"目标目录: {TARGET_ROOT.absolute()}")
    print(f"仓库数量: {len(REPOSITORIES)}")

    # 确保目标目录存在
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    
    changed: List[str] = []
    failed: List[str] = []

    for owner, name in REPOSITORIES:
        try:
            changed_flag = sync_repository(owner, name, token)
            if changed_flag:
                changed.append(f"{owner}/{name}")
        except Exception as error:
            print(f"✗ 处理 {owner}/{name} 时发生错误: {error}")
            traceback.print_exc()
            failed.append(f"{owner}/{name}")

    print("\n" + "=" * 70)
    print("同步结果:")
    print("=" * 70)
    
    if changed:
        print(f"✓ 已更新 ({len(changed)}):")
        for repo in changed:
            print(f"  • {repo}")
    else:
        print("• 所有仓库均为最新版本")
    
    if failed:
        print(f"\n✗ 失败 ({len(failed)}):")
        for repo in failed:
            print(f"  • {repo}")
        sys.exit(1)
    
    print("\n✓ 同步完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ 用户中断")
        sys.exit(130)
    except Exception as error:
        print(f"\n✗ 致命错误: {error}")
        traceback.print_exc()
        sys.exit(1)
