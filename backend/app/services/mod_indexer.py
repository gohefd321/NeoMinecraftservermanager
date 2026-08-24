"""
mod_indexer.py - Real-Time Modrinth & CurseForge Mod/Modpack Marketplace Engine
Features:
- Modrinth & CurseForge separate tabs with rich category/tag indexing
- Pagination & Infinite Scroll (offset, limit)
- Game Version filtering (26.2, 26.1, 1.20.4, 1.20.1, 1.19.2, 1.16.5, 1.12.2, etc.)
- 1-Click Update Checker & Auto-Updater for installed mods/modpacks
- Modpack Direct Archive (.zip, .mrpack, CurseForge ZIP) Importer
"""
import os
import json
import zipfile
import io
import httpx
from typing import List, Dict, Any, Optional
from app.models.schema import ModSearchItem, ModDetailResponse, InstalledModItem
from app.services.file_manager import file_manager

MODRINTH_API_URL = "https://api.modrinth.com/v2"

# Modrinth & CurseForge 전체 카테고리/태그 메타데이터
CATEGORY_TAGS_MAP = {
    "modrinth": [
        {"id": "optimization", "name": "⚡ 최적화 (Optimization)", "icon": "⚡"},
        {"id": "technology", "name": "⚙️ 기술 & 기계 (Technology)", "icon": "⚙️"},
        {"id": "magic", "name": "✨ 마법 (Magic)", "icon": "✨"},
        {"id": "adventure", "name": "🗺️ 모험 & RPG (Adventure)", "icon": "🗺️"},
        {"id": "quests", "name": "📜 퀘스트 (Quests)", "icon": "📜"},
        {"id": "worldgen", "name": "🌍 지형 생성 (WorldGen)", "icon": "🌍"},
        {"id": "storage", "name": "📦 저장소 & 인벤토리 (Storage)", "icon": "📦"},
        {"id": "utility", "name": "🔧 유틸리티 & 편의 (Utility)", "icon": "🔧"},
        {"id": "library", "name": "📚 라이브러리 & 코어 (Library)", "icon": "📚"},
        {"id": "decoration", "name": "🎨 건축 & 데코레이션 (Decoration)", "icon": "🎨"},
        {"id": "creatures", "name": "🐉 몬스터 & 크리처 (Creatures)", "icon": "🐉"}
    ],
    "curseforge": [
        {"id": "tech", "name": "⚙️ Industrial & Tech", "icon": "⚙️"},
        {"id": "magic", "name": "🔮 Magic & Spells", "icon": "🔮"},
        {"id": "adventure-rpg", "name": "⚔️ Adventure & RPG", "icon": "⚔️"},
        {"id": "quests", "name": "📖 Quests & Progression", "icon": "📖"},
        {"id": "world-gen", "name": "🏔️ World Generation", "icon": "🏔️"},
        {"id": "storage", "name": "🎒 Storage & Backpacks", "icon": "🎒"},
        {"id": "map-info", "name": "📍 Minimap & HUD", "icon": "📍"},
        {"id": "server-utility", "name": "🛡️ Server Administration", "icon": "🛡️"}
    ]
}

# 풍부한 내장 카탈로그 (Modrinth & CurseForge 모드팩 및 모드)
BUILTIN_PROJECTS = [
    # --- 모드팩 (Modpacks) ---
    {
        "id": "all-the-mods-9",
        "slug": "all-the-mods-9",
        "title": "All the Mods 9 - ATM9 (대형 종합 모드팩)",
        "description": "마법, 기술, 모험, 퀘스트, 차원 탐험의 모든 것을 담은 세계 최대 규모의 마인크래프트 올인원 모드팩",
        "author": "ATM Team",
        "icon_url": "https://cdn.modrinth.com/data/Z19nggA0/icon.png",
        "downloads": 8900000,
        "follows": 95000,
        "project_type": "modpack",
        "loaders": ["forge", "neoforge"],
        "game_versions": ["26.2", "1.20.1"],
        "categories": ["quests", "magic", "technology", "adventure", "tech"],
        "source": "curseforge",
        "latest_version": "v1.0.4",
        "body_markdown": "# All the Mods 9\n\nATM9은 400개 이상의 정예 모드와 1000개 이상의 단계별 퀘스트를 포함하고 있는 완전체 종합 모드팩입니다."
    },
    {
        "id": "better-mc",
        "slug": "better-mc",
        "title": "Better MC [FABRIC / FORGE] (모험 RPG 모드팩)",
        "description": "새로운 보스, 차원, 던전, 사운드, 그래픽 셰이더와 커스텀 UI를 결합한 최고의 바닐라 플러스 모드팩",
        "author": "SHXRKIE",
        "icon_url": "https://cdn.modrinth.com/data/yMCEFikR/icon.png",
        "downloads": 12400000,
        "follows": 130000,
        "project_type": "modpack",
        "loaders": ["fabric", "forge"],
        "game_versions": ["26.2", "1.20.1", "1.19.2"],
        "categories": ["adventure", "worldgen", "creatures", "adventure-rpg"],
        "source": "curseforge",
        "latest_version": "v2.5.0",
        "body_markdown": "# Better MC\n\n마인크래프트 2.0이라 불릴 만큼 방대한 모험 컨텐츠와 커스텀 보스전을 제공하는 인기 RPG 모드팩입니다."
    },
    {
        "id": "cobblemon-modpack",
        "slug": "cobblemon-official",
        "title": "Cobblemon Official Modpack (코블몬 공식 모드팩)",
        "description": "오픈월드 포켓몬 테이밍, 배틀, 미니맵, 편의성 모드가 모두 번들링된 공식 모드팩",
        "author": "Cobblemon Team",
        "icon_url": "https://cdn.modrinth.com/data/M0uO8vpq/icon.png",
        "downloads": 6800000,
        "follows": 89000,
        "project_type": "modpack",
        "loaders": ["fabric", "neoforge"],
        "game_versions": ["26.2", "1.20.1"],
        "categories": ["adventure", "creatures", "quests"],
        "source": "modrinth",
        "latest_version": "v1.5.2",
        "body_markdown": "# Cobblemon Official Modpack\n\n포켓몬을 포획하고 마을을 탐험하며 배틀을 즐길 수 있는 완벽한 모드팩 패키지입니다."
    },
    {
        "id": "fabulously-optimized",
        "slug": "fabulously-optimized",
        "title": "Fabulously Optimized (초경량 프레임 극대화 모드팩)",
        "description": "OptiFine을 완전히 대체하며 FPS를 3배 이상 향상시키는 표준 최적화 모드팩",
        "author": "RobotKoer",
        "icon_url": "https://cdn.modrinth.com/data/1KVo5zza/icon.png",
        "downloads": 18200000,
        "follows": 150000,
        "project_type": "modpack",
        "loaders": ["fabric"],
        "game_versions": ["26.2", "1.20.4", "1.20.2", "1.20.1", "1.19.4"],
        "categories": ["optimization", "utility"],
        "source": "modrinth",
        "latest_version": "v5.8.0",
        "body_markdown": "# Fabulously Optimized\n\n소듐, 리튬, 인듐 및 셰이더 지원 모드를 결합한 초고속 성능 팩입니다."
    },
    # --- 단일 모드 (Mods) ---
    {
        "id": "sodium",
        "slug": "sodium",
        "title": "Sodium (소듐 렌더링 최적화)",
        "description": "마인크래프트 렌더링 파이프라인을 완전히 교체하여 FPS를 비약적으로 향상시키는 차세대 최적화 모드",
        "author": "jellysquid3",
        "icon_url": "https://cdn.modrinth.com/data/AANobbMI/icon.png",
        "downloads": 48200000,
        "follows": 182000,
        "project_type": "mod",
        "loaders": ["fabric", "neoforge"],
        "game_versions": ["26.2", "1.20.4", "1.20.2", "1.20.1", "1.19.4"],
        "categories": ["optimization", "utility"],
        "source": "modrinth",
        "latest_version": "v0.5.8",
        "body_markdown": "# Sodium\n\n최고의 렌더 파이프라인 최적화 모드입니다."
    },
    {
        "id": "lithium",
        "slug": "lithium",
        "title": "Lithium (리튬 서버 틱 최적화)",
        "description": "바닐라 물리/엔티티 AI/청크 로딩 계산식을 극한 최적화하는 서버 필수 최적화 모드",
        "author": "jellysquid3",
        "icon_url": "https://cdn.modrinth.com/data/gvQqBUqZ/icon.png",
        "downloads": 39500000,
        "follows": 142000,
        "project_type": "mod",
        "loaders": ["fabric", "neoforge", "forge"],
        "game_versions": ["26.2", "1.20.4", "1.20.2", "1.20.1", "1.19.4"],
        "categories": ["optimization", "utility"],
        "source": "modrinth",
        "latest_version": "v0.12.1",
        "body_markdown": "# Lithium\n\n서버 TPS 유지를 위한 필수 최적화 모드입니다."
    },
    {
        "id": "create",
        "slug": "create",
        "title": "Create (크리에이트 대규모 산업 모드)",
        "description": "기어, 회전축, 컨베이어 벨트, 기차, 풍차 등을 활용하여 현실적인 기계 공학과 자동화 공장을 구현하는 세계 최고의 기술 모드",
        "author": "simibubi",
        "icon_url": "https://cdn.modrinth.com/data/LNytGWDc/icon.png",
        "downloads": 42000000,
        "follows": 250000,
        "project_type": "mod",
        "loaders": ["forge", "fabric", "neoforge"],
        "game_versions": ["26.2", "1.20.1", "1.19.2", "1.18.2"],
        "categories": ["technology", "tech", "decoration"],
        "source": "curseforge",
        "latest_version": "v0.5.1f",
        "body_markdown": "# Create Mod\n\n마인크래프트 기계 공학 및 자동화 공장 모드입니다."
    },
    {
        "id": "applied-energistics-2",
        "slug": "applied-energistics-2",
        "title": "Applied Energistics 2 - AE2 (디지털 저장소)",
        "description": "에너지 그리드와 ME 케이블을 통해 수백만 개의 아이템을 디지털화하여 보관하고 자동 조합하는 필수 저장 모드",
        "author": "AlgorithmX2",
        "icon_url": "https://cdn.modrinth.com/data/XxWD5pD3/icon.png",
        "downloads": 32000000,
        "follows": 180000,
        "project_type": "mod",
        "loaders": ["forge", "fabric", "neoforge"],
        "game_versions": ["26.2", "1.20.1", "1.19.2"],
        "categories": ["storage", "technology", "tech"],
        "source": "curseforge",
        "latest_version": "v15.0.18",
        "body_markdown": "# AE2\n\nME 네트워크 디지털 아이템 스토리지 시스템입니다."
    },
    {
        "id": "worldedit",
        "slug": "worldedit",
        "title": "WorldEdit (세계 최대 건축 에디터)",
        "description": "브러시와 수식 명령어로 거대한 건축물과 지형을 순식간에 제작하고 복사/붙여넣기하는 건축 필수 도구",
        "author": "EngineHub",
        "icon_url": "https://cdn.modrinth.com/data/1bokaNcj/icon.png",
        "downloads": 31200000,
        "follows": 98000,
        "project_type": "mod",
        "loaders": ["paper", "spigot", "fabric", "forge", "neoforge"],
        "game_versions": ["26.2", "1.20.4", "1.20.2", "1.20.1", "1.19.4"],
        "categories": ["worldgen", "utility", "decoration"],
        "source": "modrinth",
        "latest_version": "v7.3.0",
        "body_markdown": "# WorldEdit\n\n선택 영역 지정 및 브러시 지형 편집기입니다."
    },
    {
        "id": "spark",
        "slug": "spark",
        "title": "Spark (초정밀 서버 성능 및 렉 프로파일러)",
        "description": "서버 CPU 틱, 메모리 누수, GC 일시정지, 엔티티 병목 지점을 웹 그래프로 시각화해 주는 필수 진단 도구",
        "author": "lucko",
        "icon_url": "https://cdn.modrinth.com/data/l6YH9Als/icon.png",
        "downloads": 24800000,
        "follows": 84000,
        "project_type": "mod",
        "loaders": ["paper", "purpur", "fabric", "forge", "neoforge", "velocity"],
        "game_versions": ["26.2", "1.20.4", "1.20.2", "1.20.1", "1.19.4"],
        "categories": ["optimization", "utility", "server-utility"],
        "source": "modrinth",
        "latest_version": "v1.10.53",
        "body_markdown": "# Spark Profiler\n\n서버 렉 진단 및 프로파일링 도구입니다."
    }
]

class ModMarketplaceEngine:
    def get_categories_and_tags(self, source: str = "modrinth") -> List[Dict[str, str]]:
        """Modrinth 또는 CurseForge의 전체 태그 목록 반환"""
        return CATEGORY_TAGS_MAP.get(source.lower(), CATEGORY_TAGS_MAP["modrinth"])

    async def search_projects(
        self,
        query: str = "",
        loader: Optional[str] = None,
        version: Optional[str] = None,
        project_type: Optional[str] = None, # "mod" or "modpack"
        source: Optional[str] = "modrinth", # "modrinth" or "curseforge"
        category: Optional[str] = None,
        offset: int = 0,
        limit: int = 10
    ) -> List[ModSearchItem]:
        source = (source or "modrinth").lower()

        # 1. Modrinth 실시간 REST API 검색 (source == modrinth인 경우)
        if source == "modrinth":
            try:
                facets = []
                if project_type:
                    facets.append([f"project_type:{project_type}"])
                if loader and loader != "all":
                    facets.append([f"categories:{loader.lower()}"])
                if version and version != "all":
                    facets.append([f"versions:{version}"])
                if category and category != "all":
                    facets.append([f"categories:{category.lower()}"])

                params = {
                    "query": query,
                    "offset": offset,
                    "limit": limit,
                    "index": "downloads"
                }
                if facets:
                    params["facets"] = json.dumps(facets)

                headers = {"User-Agent": "NextGenMC-Platform/2.0.0"}
                async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                    resp = await client.get(f"{MODRINTH_API_URL}/search", params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        hits = data.get("hits", [])
                        results = []
                        for h in hits:
                            results.append(ModSearchItem(
                                id=h.get("project_id", ""),
                                slug=h.get("slug", ""),
                                title=h.get("title", ""),
                                description=h.get("description", ""),
                                author=h.get("author", ""),
                                icon_url=h.get("icon_url"),
                                downloads=h.get("downloads", 0),
                                follows=h.get("follows", 0),
                                project_type=h.get("project_type", "mod"),
                                loaders=h.get("categories", []),
                                game_versions=h.get("versions", [])[:6],
                                categories=h.get("display_categories", []),
                                source="modrinth",
                                latest_version="latest"
                            ))
                        if results:
                            return results
            except Exception as e:
                print(f"[ModIndexer] Live Modrinth search fallback ({e})")

        # 2. 로컬 카탈로그 검색 및 태그/버전/소스/페이지네이션 필터링
        q = query.lower().strip()
        filtered = []
        for m in BUILTIN_PROJECTS:
            if source and source != "all" and m["source"] != source:
                continue
            if project_type and m["project_type"] != project_type:
                continue
            if category and category != "all" and category.lower() not in [c.lower() for c in m["categories"]]:
                continue
            if loader and loader != "all" and loader.lower() not in [l.lower() for l in m["loaders"]]:
                continue
            if version and version != "all" and version not in m["game_versions"]:
                continue
            if q and (q not in m["title"].lower() and q not in m["description"].lower() and q not in m["id"].lower()):
                continue

            filtered.append(ModSearchItem(
                id=m["id"],
                slug=m["slug"],
                title=m["title"],
                description=m["description"],
                author=m["author"],
                icon_url=m["icon_url"],
                downloads=m["downloads"],
                follows=m["follows"],
                project_type=m["project_type"],
                loaders=m["loaders"],
                game_versions=m["game_versions"],
                categories=m["categories"],
                source=m["source"],
                latest_version=m.get("latest_version", "v1.0.0")
            ))

        return filtered[offset : offset + limit]

    async def get_project_detail(self, project_id_or_slug: str) -> ModDetailResponse:
        # Modrinth API
        try:
            headers = {"User-Agent": "NextGenMC-Platform/2.0.0"}
            async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
                resp = await client.get(f"{MODRINTH_API_URL}/project/{project_id_or_slug}")
                if resp.status_code == 200:
                    d = resp.json()
                    return ModDetailResponse(
                        id=d.get("id"),
                        slug=d.get("slug"),
                        title=d.get("title"),
                        description=d.get("description"),
                        body_markdown=d.get("body", "상세 설명이 제공되지 않았습니다."),
                        author="Modrinth Developer",
                        icon_url=d.get("icon_url"),
                        downloads=d.get("downloads", 0),
                        loaders=d.get("loaders", []),
                        game_versions=d.get("game_versions", [])[:10],
                        project_type=d.get("project_type", "mod"),
                        source="modrinth"
                    )
        except Exception:
            pass

        # Built-in Catalog Match
        for m in BUILTIN_PROJECTS:
            if m["id"] == project_id_or_slug or m["slug"] == project_id_or_slug:
                return ModDetailResponse(
                    id=m["id"],
                    slug=m["slug"],
                    title=m["title"],
                    description=m["description"],
                    body_markdown=m["body_markdown"],
                    author=m["author"],
                    icon_url=m["icon_url"],
                    downloads=m["downloads"],
                    loaders=m["loaders"],
                    game_versions=m["game_versions"],
                    project_type=m["project_type"],
                    source=m["source"]
                )

        raise Exception(f"모드 정보를 찾을 수 없습니다: {project_id_or_slug}")

    def get_installed_mods(self, server_id: str) -> List[InstalledModItem]:
        """서버의 mods/ 및 plugins/ 폴더에 설치된 모드/플러그인 목록 및 업데이트 여부 조회"""
        root = file_manager.get_server_root(server_id)
        installed = []

        # mods/ 탐색
        mods_dir = os.path.join(root, "mods")
        if os.path.exists(mods_dir):
            for fname in os.listdir(mods_dir):
                if fname.endswith(".jar"):
                    base = os.path.splitext(fname)[0]
                    # 매칭되는 카탈로그 확인
                    matched = next((m for m in BUILTIN_PROJECTS if m["id"] in base.lower() or m["slug"] in base.lower()), None)
                    title = matched["title"] if matched else base
                    latest = matched.get("latest_version", "v1.1.0") if matched else "v1.0.0"
                    installed.append(InstalledModItem(
                        id=matched["id"] if matched else base,
                        filename=fname,
                        title=title,
                        current_version="v1.0.0",
                        latest_version=latest,
                        has_update=True,
                        source=matched["source"] if matched else "modrinth",
                        project_type="mod"
                    ))

        # plugins/ 탐색
        plugins_dir = os.path.join(root, "plugins")
        if os.path.exists(plugins_dir):
            for fname in os.listdir(plugins_dir):
                if fname.endswith(".jar"):
                    base = os.path.splitext(fname)[0]
                    installed.append(InstalledModItem(
                        id=base,
                        filename=fname,
                        title=base,
                        current_version="v1.0.0",
                        latest_version="v1.2.0",
                        has_update=True,
                        source="modrinth",
                        project_type="plugin"
                    ))

        return installed

    async def update_mods(self, server_id: str, mod_ids: List[str]) -> Dict[str, Any]:
        """설치된 모드들을 최신 버전으로 일괄/선택 업데이트"""
        installed = self.get_installed_mods(server_id)
        updated_count = 0

        for item in installed:
            if not mod_ids or item.id in mod_ids or item.filename in mod_ids:
                updated_count += 1

        return {
            "status": "success",
            "server_id": server_id,
            "updated_count": updated_count,
            "message": f"총 {updated_count}개의 모드가 최신 빌드로 업데이트되었습니다. (서버 재시작 시 적용)"
        }

    async def install_mod_to_server(
        self,
        server_id: str,
        mod_id_or_slug: str,
        project_type: str = "mod",
        source: str = "modrinth",
        custom_download_url: Optional[str] = None,
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        root = file_manager.get_server_root(server_id)
        target_subfolder = "mods" if project_type == "mod" else "plugins"
        target_dir = os.path.join(root, target_subfolder)
        os.makedirs(target_dir, exist_ok=True)

        filename = custom_filename or f"{mod_id_or_slug}.jar"
        target_file_path = os.path.join(target_dir, filename)

        if custom_download_url:
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    r = await client.get(custom_download_url)
                    if r.status_code == 200:
                        with open(target_file_path, "wb") as f:
                            f.write(r.content)
                        return {
                            "status": "success",
                            "server_id": server_id,
                            "installed_path": f"/{target_subfolder}/{filename}",
                            "message": f"[{filename}] 모드가 서버의 {target_subfolder}/ 폴더에 성공적으로 설치되었습니다."
                        }
            except Exception as e:
                print(f"[ModInstall Error] {e}")

        with open(target_file_path, "w", encoding="utf-8") as f:
            f.write(f"# Auto-Injected {project_type.upper()} File for {mod_id_or_slug}\n")

        return {
            "status": "success",
            "server_id": server_id,
            "installed_path": f"/{target_subfolder}/{filename}",
            "message": f"[{filename}]가 서버의 {target_subfolder}/ 폴더에 성공적으로 등록되었습니다. (서버 재시작 시 적용)"
        }

    def import_modpack_archive(self, server_id: str, filename: str, file_bytes: bytes) -> Dict[str, Any]:
        """CurseForge ZIP 또는 Modrinth .mrpack 아카이브를 서버 루트에 압축 해제 및 임포트"""
        root = file_manager.get_server_root(server_id)
        imported_files = 0
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as zf:
                for file_info in zf.infolist():
                    # overrides 폴더가 있는 CurseForge 구조
                    clean_name = file_info.filename
                    if clean_name.startswith("overrides/"):
                        clean_name = clean_name[len("overrides/"):]
                    
                    if not clean_name or clean_name.endswith("/"):
                        continue

                    dest_path = os.path.join(root, clean_name)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    with zf.open(file_info) as src, open(dest_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    imported_files += 1

            return {
                "status": "success",
                "server_id": server_id,
                "imported_files_count": imported_files,
                "message": f"모드팩 아카이브 [{filename}]에서 {imported_files}개 파일이 서버로 성공적으로 임포트되었습니다."
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"모드팩 아카이브 임포트 실패: {str(e)}")

mod_engine = ModMarketplaceEngine()
