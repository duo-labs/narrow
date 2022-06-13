import cfg
import patch_extractor
import pathlib

def test_single_file():
    graph = cfg.ControlFlowGraph()
    graph.construct_from_file("tests/projects/single_file/main.py", False)

    assert graph.function_exists("foo")
    assert graph.function_exists("bar")
    assert not graph.function_exists("does_not_exist")


def test_extraction():
    extractor = patch_extractor.PatchExtractor()

    targets = extractor.find_targets_in_string("""
    diff --git a/archinstall/lib/user_interaction/disk_conf.py b/archinstall/lib/user_interaction/disk_conf.py
index 41657e1b4..371d052f5 100644
--- a/archinstall/lib/user_interaction/disk_conf.py
+++ b/archinstall/lib/user_interaction/disk_conf.py
@@ -7,7 +7,6 @@
 from ..exceptions import DiskError
 from ..menu import Menu
 from ..menu.menu import MenuSelectionType
-from ..output import log

 if TYPE_CHECKING:
 	_: Any
@@ -60,7 +59,7 @@ def select_disk_layout(preset: Optional[Dict[str, Any]], block_devices: list, ad
 				return select_individual_blockdevice_usage(block_devices)


-def select_disk(dict_o_disks: Dict[str, BlockDevice]) -> BlockDevice:
+def select_disk(dict_o_disks: Dict[str, BlockDevice]) -> Optional[BlockDevice]:
 	\"""
 	Asks the user to select a harddrive from the `dict_o_disks` selection.
 	Usually this is combined with :ref:`archinstall.list_drives`.
@@ -73,19 +72,15 @@ def select_disk(dict_o_disks: Dict[str, BlockDevice]) -> BlockDevice:
 	\"""
 	drives = sorted(list(dict_o_disks.keys()))
 	if len(drives) >= 1:
-		for index, drive in enumerate(drives):
-			print(
-				f"{index}: {drive} ({dict_o_disks[drive]['size'], dict_o_disks[drive].device, dict_o_disks[drive]['label']})"
-			)
+		title = str(_('You can skip selecting a drive and partitioning and use whatever drive-setup is mounted at /mnt (experimental)')) + '\n'
+		title += str(_('Select one of the disks or skip and use /mnt as default'))

-		log("You can skip selecting a drive and partitioning and use whatever drive-setup is mounted at /mnt (experimental)",
-			fg="yellow")
+		choice = Menu(title, drives).run()

-		drive = Menu('Select one of the disks or skip and use "/mnt" as default"', drives).run()
-		if not drive:
-			return drive
+		if choice.type_ == MenuSelectionType.Esc:
+			return None

-		drive = dict_o_disks[drive]
+		drive = dict_o_disks[choice.value]
 		return drive

 	raise DiskError('select_disk() requires a non-empty dictionary of disks to select from.')
    """, patch_extractor.LanguageName.PYTHON)

    assert('select_disk' in targets)


def test_file_extraction():
    extractor = patch_extractor.PatchExtractor()

    targets = extractor.find_targets_in_file((pathlib.Path(__file__).parent / 'example.diff').resolve().as_posix(), patch_extractor.LanguageName.PYTHON)

    assert('select_disk' in targets)


def test_github_pr_extraction():
    extractor = patch_extractor.PatchExtractor()

    targets = extractor.find_targets_in_github_pull_request(
        'https://github.com/archlinux/archinstall/pull/1194')

    assert('select_disk' in targets)


def test_nvd_extraction():
    extractor = patch_extractor.PatchExtractor()

    targets = extractor.find_targets_in_ndv_entry('CVE-2018-18074')

    assert('test_auth_is_stripped_on_redirect_off_host' in targets)
    assert('rebuild_auth' in targets)

def test_ghsa_extraction():
    extractor = patch_extractor.PatchExtractor()

    targets = extractor.find_targets_in_osv_entry('GHSA-g3rq-g295-4j3m')
    assert('urlize' in targets)

