"""Runs vuckfield_ue.build_level end to end against a fake `unreal` module.

This proves the importer's own control flow, report writing and verification wiring. It does NOT
prove the Unreal API calls are right - only running in the editor does that.
"""
import importlib
import json
import sys
import types
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
UE_PY = ROOT / "unreal" / "Content" / "Python"
MANIFEST = json.loads((ROOT / "build" / "regions" / "nursery-lane" / "manifest.json").read_text())


class Vec:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


class FakeActor:
    def __init__(self, label_src):
        self.src = label_src
        self.folder = ""

    def set_actor_label(self, label):
        self.label = label

    def set_folder_path(self, path):
        self.folder = path

    def get_folder_path(self):
        return self.folder

    def get_actor_bounds(self, only_colliding):
        # Faithful import: east -> +X, north -> -Y, metres -> cm.
        b = MANIFEST["files"].get(getattr(self.src, "key", ""), MANIFEST["files"]["terrain"])["bounds_local_m"]
        e, n, z = b["x_east"], b["y_north"], b["z"]
        c = Vec((e[0] + e[1]) * 50, -(n[0] + n[1]) * 50, (z[0] + z[1]) * 50)
        x = Vec((e[1] - e[0]) * 50, (n[1] - n[0]) * 50, (z[1] - z[0]) * 50)
        return c, x


def fake_unreal(saved_dir, fail_import=None):
    u = types.ModuleType("unreal")
    u.Vector, u.Rotator = Vec, lambda *a, **kw: (a, kw)
    u.StaticMesh = type("StaticMesh", (), {})
    for cls in ("DirectionalLight", "SkyAtmosphere", "SkyLight", "ExponentialHeightFog", "PlayerStart"):
        setattr(u, cls, type(cls, (), {}))
    u.ComponentMobility = types.SimpleNamespace(MOVABLE="movable")
    u.Paths = types.SimpleNamespace(project_dir=lambda: str(ROOT / "unreal") + "/",
                                    project_saved_dir=lambda: str(saved_dir),
                                    convert_relative_path_to_full=lambda p: p)
    u.CollisionTraceFlag = types.SimpleNamespace(CTF_USE_COMPLEX_AS_SIMPLE="complex_as_simple")
    u.SystemLibrary = types.SimpleNamespace(get_engine_version=lambda: "5.x-fake")
    u.logs = []
    u.log = lambda m: u.logs.append(("info", m))
    u.log_error = lambda m: u.logs.append(("error", m))
    u.log_warning = lambda m: u.logs.append(("warning", m))

    imported = {}

    class Task:
        objects = ()

        def set_editor_property(self, k, v):
            setattr(self, k, v)

        def get_objects(self):
            return list(self.objects)

    def import_asset_tasks(tasks):
        for t in tasks:
            key = t.destination_path.rsplit("/", 1)[-1]
            if fail_import and fail_import in t.filename:
                raise RuntimeError("Interchange exploded")
            mesh = u.StaticMesh()
            mesh.key = key
            mesh.get_path_name = lambda key=key: f"/Game/fake/{key}"
            mesh.body_setup = mock.MagicMock()
            mesh.get_editor_property = lambda name, mesh=mesh: getattr(mesh, name)
            imported[t.destination_path] = mesh
            t.objects = (mesh, object())  # plus a non-mesh (material) the importer must ignore

    u.AssetImportTask = Task
    u.AssetToolsHelpers = types.SimpleNamespace(
        get_asset_tools=lambda: types.SimpleNamespace(import_asset_tasks=import_asset_tasks))
    u.EditorAssetLibrary = types.SimpleNamespace(
        does_asset_exist=lambda p: False,
        list_assets=lambda d, recursive=True, include_folder=False: [d] if d in imported else [],
        load_asset=lambda p: imported[p],
        save_loaded_asset=lambda a: True,
    )

    def spawn_obj(obj, loc, rot):
        return FakeActor(obj)

    def spawn_cls(cls, loc, rot):
        a = FakeActor(None)
        a.light_component = mock.MagicMock()
        return a

    actors = types.SimpleNamespace(spawn_actor_from_object=spawn_obj, spawn_actor_from_class=spawn_cls,
                                   get_all_level_actors=lambda: [], destroy_actor=lambda a: None)
    les = types.SimpleNamespace(new_level=lambda p: True, load_level=lambda p: True,
                                save_current_level=lambda: True)
    subsystems = {"LevelEditorSubsystem": les, "EditorActorSubsystem": actors,
                  "UnrealEditorSubsystem": mock.MagicMock()}
    for n in subsystems:
        setattr(u, n, n)
    u.get_editor_subsystem = lambda n: subsystems[n]

    class SlowTask:
        def __init__(self, *a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def make_dialog(self, *a):
            pass

        def enter_progress_frame(self, *a):
            pass

    u.ScopedSlowTask = SlowTask
    return u


def run(tmp_path, unreal_module=None, **kw):
    u = unreal_module or fake_unreal(tmp_path, **kw)
    with mock.patch.dict(sys.modules, {"unreal": u}):
        sys.path.insert(0, str(UE_PY))
        try:
            for m in [m for m in sys.modules if m.startswith("vuckfield_ue")]:
                del sys.modules[m]
            ue = importlib.import_module("vuckfield_ue")
            verdict = ue.build_level("nursery-lane")
        finally:
            sys.path.remove(str(UE_PY))
    report = json.loads((tmp_path / "Vuckfield" / "report_nursery-lane.json").read_text())
    return verdict, report, u.logs


def test_successful_build_passes_and_writes_report(tmp_path):
    verdict, report, logs = run(tmp_path)
    assert verdict == "PASS", report
    assert all(s["ok"] for s in report["steps"])
    assert report["fit"]["east_is"] == "+X" and report["fit"]["north_is"] == "-Y"
    assert any("VUCKFIELD BUILD nursery-lane: PASS" in m for _, m in logs)
    assert any(s["step"] == "terrain collision" for s in report["steps"])


def test_save_failure_is_reported(tmp_path):
    u = fake_unreal(tmp_path)
    u.get_editor_subsystem("LevelEditorSubsystem").save_current_level = lambda: False
    verdict, report, _ = run(tmp_path, unreal_module=u)
    assert verdict == "FAIL"
    assert any(s["step"] == "save level" and not s["ok"] for s in report["steps"])


def test_failed_import_still_writes_report_with_error(tmp_path):
    verdict, report, logs = run(tmp_path, fail_import="roads.glb")
    assert verdict == "FAIL"
    failed = [s for s in report["steps"] if not s["ok"]]
    assert failed and "Interchange exploded" in failed[0]["error"]
    assert any(level == "error" and "FAIL" in m for level, m in logs)
