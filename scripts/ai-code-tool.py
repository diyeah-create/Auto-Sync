#!/usr/bin/env python3
"""同步指定仓库的最新发布资产（仅元数据模式）。"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
TARGET_ROOT = Path("artifacts")
REPOSITORIES: List[Tuple[str, str]] = [
    ("zhaochengcube", "augment-token-mng"),
    ("zhaochengcube", "augment-code-auto"),
    ("Zheng-up", "augment-code-z"),
    ("Zheng-up", "zAugment"),
    ("wuqi-y", "auto-cursor-releases"),
    ("crispvibe", "Windsurf-Tool"),
    ("yuzeguitarist", "Windsurf-Reset"),
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
    with urlopen(request) as response:  # type: ignore[arg-type]
        return json.loads(response.read().decode("utf-8"))


def download_asset(asset: Dict[str, object], token: str, destination: Path) -> None:
    """下载发布资产到指定路径。"""
    asset_url = str(asset.get("url"))
    if not asset_url:
        raise RuntimeError("发布资产缺少下载地址")
    
    # 检查文件大小
    asset_size = int(asset.get("size", 0))
    if asset_size > MAX_FILE_SIZE:
        print(f"  跳过 {destination.name} (大小: {asset_size / 1024 / 1024:.2f} MB，超过限制)")
        return
    
    headers = {
        "Accept": "application/octet-stream",
        "Authorization": f"token {token}",
        "User-Agent": "release-sync-bot",
    }
    request = Request(asset_url, headers=headers)
    with urlopen(request) as response:  # type: ignore[arg-type]
        with destination.open("wb") as file_handle:
            shutil.copyfileobj(response, file_handle)


def sync_repository(owner: str, name: str, token: str) -> bool:
    """同步单个仓库的最新发布，返回是否产生变更。"""
    metadata_url = f"{API_ROOT}/repos/{owner}/{name}/releases/latest"
    try:
        release = fetch_json(metadata_url, token)
    except HTTPError as error:
        raise RuntimeError(f"请求 {owner}/{name} 发布信息失败，状态码: {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"请求 {owner}/{name} 发布信息失败: {error.reason}") from error

    tag_name = str(release.get("tag_name") or "").strip()
    assets = release.get("assets")

    if not tag_name:
        raise RuntimeError(f"{owner}/{name} 的最新发布缺少 tag_name 字段")
    if not isinstance(assets, list):
        assets = []

    project_dir = TARGET_ROOT / name
    version_file = project_dir / "version.txt"

    current_version = version_file.read_text(encoding="utf-8").strip() if version_file.exists() else ""
    if current_version == tag_name:
        print(f"{owner}/{name} 已是最新版本 {tag_name}")
        return False

    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 保存资产信息到 metadata.json
    assets_info = []
    if assets:
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
                print(f"下载 {owner}/{name} 的资产 {asset_name}")
                try:
                    download_asset(asset, token, destination)
                except Exception as e:
                    print(f"  下载失败: {e}")
            else:
                print(f"记录 {owner}/{name} 的资产信息 {asset_name}")
    else:
        print(f"{owner}/{name} 的最新发布没有资产")

    version_file.write_text(tag_name, encoding="utf-8")
    metadata_file = project_dir / "metadata.json"
    metadata_file.write_text(
        json.dumps(
            {
                "repository": f"{owner}/{name}",
                "tag": tag_name,
                "release_id": release.get("id"),
                "html_url": release.get("html_url"),
                "published_at": release.get("published_at"),
                "fetched_at": os.environ.get("GITHUB_RUN_DATETIME"),
                "assets": assets_info,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return True


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("缺少 GITHUB_TOKEN 环境变量")

    mode = "仅元数据" if METADATA_ONLY else f"下载文件（限制 {MAX_FILE_SIZE / 1024 / 1024:.0f} MB）"
    print(f"同步模式: {mode}\n")

    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    changed: List[str] = []

    for owner, name in REPOSITORIES:
        try:
            changed_flag = sync_repository(owner, name, token)
            if changed_flag:
                changed.append(f"{owner}/{name}")
        except Exception as error:
            print(f"错误: {error}", file=sys.stderr)
            continue

    if changed:
        summary = "\n".join(changed)
        print(f"\n已更新的仓库:\n{summary}")
    else:
        print("\n所有仓库均为最新版本")


if __name__ == "__main__":
    main()
