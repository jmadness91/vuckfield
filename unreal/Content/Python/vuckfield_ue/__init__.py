"""Editor-side import: build/regions/<id> -> /Game/Vuckfield level.

Run from the Vuckfield menu, or in the Output Log (Python):
    import vuckfield_ue; vuckfield_ue.build_level("nursery-lane")

Idempotent: re-running replaces the region's assets and actors.
"""
import json
import math
import os

import unreal

MANIFEST_VERSION = 1
CONTENT_ROOT = "/Game/Vuckfield"
ACTOR_FOLDER = "Vuckfield"
CAMERA_HEIGHT_CM = 2500.0  # start 25 m above Nursery Lane


def _repo_root():
    return os.path.abspath(os.path.join(unreal.Paths.project_dir(), os.pardir))


def _regions_build_dir():
    return os.path.join(_repo_root(), "build", "regions")


def available_regions():
    d = _regions_build_dir()
    if not os.path.isdir(d):
        return []
    return sorted(r for r in os.listdir(d) if os.path.isfile(os.path.join(d, r, "manifest.json")))


def _asset_name(region_id):
    return region_id.replace("-", "_")


def _load_manifest(region_id):
    path = os.path.join(_regions_build_dir(), region_id, "manifest.json")
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise RuntimeError(f"{path}: manifest_version {manifest.get('manifest_version')} != {MANIFEST_VERSION}; "
                           "update vuckfield_ue or rebuild the region")
    return manifest


def _import_glb(path, dest):
    if unreal.EditorAssetLibrary.does_directory_exist(dest):
        unreal.EditorAssetLibrary.delete_directory(dest)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", dest)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    meshes = []
    for p in unreal.EditorAssetLibrary.list_assets(dest, recursive=True, include_folder=False):
        asset = unreal.EditorAssetLibrary.load_asset(p)
        if isinstance(asset, unreal.StaticMesh):
            meshes.append(asset)
    if not meshes:
        raise RuntimeError(f"importing {path} produced no static meshes (check the Output Log)")
    return meshes


def _open_or_create_level(level_path):
    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if unreal.EditorAssetLibrary.does_asset_exist(level_path):
        les.load_level(level_path)
        for a in actors.get_all_level_actors():
            if str(a.get_folder_path()).startswith(ACTOR_FOLDER):
                actors.destroy_actor(a)
    elif not les.new_level(level_path):
        raise RuntimeError(f"could not create level {level_path}")
    return les, actors


def _spawn(actors, cls_or_mesh, label, folder, location=None, rotation=None):
    location = location or unreal.Vector(0, 0, 0)
    rotation = rotation or unreal.Rotator(0, 0, 0)
    if isinstance(cls_or_mesh, unreal.StaticMesh):
        a = actors.spawn_actor_from_object(cls_or_mesh, location, rotation)
    else:
        a = actors.spawn_actor_from_class(cls_or_mesh, location, rotation)
    a.set_actor_label(label)
    a.set_folder_path(f"{ACTOR_FOLDER}/{folder}")
    return a


def _spawn_environment(actors):
    sun = _spawn(actors, unreal.DirectionalLight, "Sun", "Environment",
                 rotation=unreal.Rotator(roll=0, pitch=-35, yaw=-140))
    sun.light_component.set_editor_property("atmosphere_sun_light", True)
    sun.light_component.set_editor_property("intensity", 10.0)
    _spawn(actors, unreal.SkyAtmosphere, "SkyAtmosphere", "Environment")
    sky = _spawn(actors, unreal.SkyLight, "SkyLight", "Environment")
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    _spawn(actors, unreal.ExponentialHeightFog, "HeightFog", "Environment")


def build_level(region_id):
    manifest = _load_manifest(region_id)
    src = os.path.join(_regions_build_dir(), region_id)
    name = _asset_name(region_id)
    content = f"{CONTENT_ROOT}/Regions/{name}"
    level_path = f"{CONTENT_ROOT}/Maps/L_{name}"

    with unreal.ScopedSlowTask(len(manifest["files"]) + 3, f"Building {manifest['name']}") as task:
        task.make_dialog(True)
        les, actors = _open_or_create_level(level_path)

        spawned = {}
        for key, info in manifest["files"].items():
            task.enter_progress_frame(1, f"Importing {info['file']}")
            meshes = _import_glb(os.path.join(src, info["file"]), f"{content}/{key}")
            folder = "Landmarks" if key.startswith("landmark_") else key.capitalize()
            spawned[key] = [_spawn(actors, m, f"{key}_{i}", folder) for i, m in enumerate(meshes)]

        task.enter_progress_frame(1, "Lighting")
        _spawn_environment(actors)

        task.enter_progress_frame(1, "Camera")
        _place_start(actors, spawned)

        task.enter_progress_frame(1, "Saving")
        les.save_current_level()
    unreal.log(f"Vuckfield: built {level_path} from {src}")
    return level_path


def _bounds_centre(actor_list):
    origin, _ = actor_list[0].get_actor_bounds(False)
    return origin


def _place_start(actors, spawned):
    """Start above Nursery Lane looking toward The Highlands, if both landmarks exist."""
    start_key, target_key = "landmark_nursery-lane", "landmark_the-highlands"
    if start_key in spawned:
        start = _bounds_centre(spawned[start_key])
    else:
        start = _bounds_centre(spawned["terrain"])
    start = unreal.Vector(start.x, start.y, start.z + CAMERA_HEIGHT_CM)
    yaw = 0.0
    pitch = -15.0
    if target_key in spawned:
        t = _bounds_centre(spawned[target_key])
        yaw = math.degrees(math.atan2(t.y - start.y, t.x - start.x))
    rot = unreal.Rotator(roll=0, pitch=pitch, yaw=yaw)
    _spawn(actors, unreal.PlayerStart, "PlayerStart", "Gameplay", location=start, rotation=rot)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(start, rot)
