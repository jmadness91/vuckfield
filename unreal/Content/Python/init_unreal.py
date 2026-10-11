"""Runs at editor startup: adds a Vuckfield menu with one entry per region."""
import unreal

import vuckfield_ue


def _register_menu():
    menus = unreal.ToolMenus.get()
    main = menus.find_menu("LevelEditor.MainMenu")
    if main is None:
        unreal.log_warning("Vuckfield: main menu not found; run "
                           "'import vuckfield_ue; vuckfield_ue.build_level(\"<region>\")' in the Python console")
        return
    sub = main.add_sub_menu("Vuckfield", "Vuckfield", "Vuckfield", "Vuckfield")
    for region_id in vuckfield_ue.available_regions():
        entry = unreal.ToolMenuEntry(name=f"Build_{region_id}", type=unreal.MultiBlockType.MENU_ENTRY)
        entry.set_label(f"Build level: {region_id}")
        entry.set_tool_tip(f"Import build/regions/{region_id} and (re)build its level")
        entry.set_string_command(
            unreal.ToolMenuStringCommandType.PYTHON, "",
            f"import vuckfield_ue; vuckfield_ue.build_level('{region_id}')")
        sub.add_menu_entry("Regions", entry)
    menus.refresh_all_widgets()


_register_menu()
