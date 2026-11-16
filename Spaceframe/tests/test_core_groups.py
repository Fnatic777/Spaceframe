"""Core: technologies by All, race, family and ship (Ships.py)."""
import sys
import types
import builtins
sys.path.insert(0, "/mnt/user-data/outputs/Spaceframe/tests")
import mock_app

builtins.reload = lambda m: m


def plugin(sName, sRace, sSubMenu, **techs):
	m = types.ModuleType("Custom.Bedrock.Ships." + sName)
	m.Race = sRace
	m.SubMenu = sSubMenu
	for k in techs.keys():
		setattr(m, k, techs[k])
	sys.modules["Custom.Bedrock.Ships." + sName] = m
	sys.modules["Custom.Bedrock.Ships"].__dict__[sName] = m


def load(All=None, Races=None, Families=None, Ships=None):
	App = mock_app.make_app()
	mock_app.install(App)
	for n in ("Custom", "Custom.Bedrock", "Custom.Bedrock.Ships", "Custom.Spaceframe"):
		sys.modules[n] = types.ModuleType(n)
	ships = types.ModuleType("Custom.Spaceframe.Ships")
	ships.Def = -1
	ships.Ships = Ships or {}
	if All != None:
		ships.All = All
	if Races != None:
		ships.Races = Races
	if Families != None:
		ships.Families = Families
	sys.modules["Custom.Spaceframe.Ships"] = ships
	sys.modules["Custom.Spaceframe"].Ships = ships
	sys.modules["Custom"].Spaceframe = sys.modules["Custom.Spaceframe"]
	sys.modules["Custom"].Bedrock = sys.modules["Custom.Bedrock"]
	sys.modules["Custom.Bedrock"].Ships = sys.modules["Custom.Bedrock.Ships"]
	plugin("Galaxy", "Federation", "Galaxy")
	plugin("GalaxyCVB", "Federation", "Galaxy")
	plugin("Defiant", "Federation", "N/A")
	plugin("Warbird", "Romulan", "N/A", MVShields=60)
	C = mock_app.load_module("Spaceframe.py", "Custom.Spaceframe.Spaceframe")
	C.g_lModules = [("MVShields", None), ("AblativeArmor", None), ("AutoFire", None)]
	return C


def test_old_format_unchanged():
	C = load(Ships={"Galaxy": {"MVShields": -1}})
	assert C.GetShipTechs("Galaxy") == {"MVShields": -1}
	assert C.GetShipTechs("Defiant") == {}


def test_all():
	C = load(All={"AutoFire": -1})
	assert C.GetShipTechs("Warbird")["AutoFire"] == -1
	assert C.GetShipTechs("SomeStockShip") == {"AutoFire": -1}


def test_race():
	C = load(Races={"Federation": {"MVShields": -1}})
	assert C.GetShipTechs("Defiant") == {"MVShields": -1}
	assert C.GetShipTechs("GalaxyCVB") == {"MVShields": -1}
	assert C.GetShipTechs("Warbird") == {"MVShields": 60}	# its own plugin


def test_family():
	C = load(Families={"Galaxy": {"AblativeArmor": 80}})
	assert C.GetShipTechs("Galaxy") == {"AblativeArmor": 80}
	assert C.GetShipTechs("GalaxyCVB") == {"AblativeArmor": 80}
	assert C.GetShipTechs("Defiant") == {}	# SubMenu "N/A": no family


def test_most_specific_wins():
	C = load(All={"MVShields": 30}, Races={"Federation": {"MVShields": 50}},
		Families={"Galaxy": {"MVShields": 70}}, Ships={"GalaxyCVB": {"MVShields": 90}})
	assert C.GetShipTechs("Defiant")["MVShields"] == 50
	assert C.GetShipTechs("Galaxy")["MVShields"] == 70
	assert C.GetShipTechs("GalaxyCVB")["MVShields"] == 90
	assert C.GetShipTechs("Warbird")["MVShields"] == 60


def test_zero_turns_off():
	C = load(Races={"Federation": {"MVShields": -1}}, Ships={"Defiant": {"MVShields": 0}})
	assert C.GetShipTechs("Defiant")["MVShields"] == 0


def test_groups():
	C = load()
	assert C.GetShipGroups("GalaxyCVB") == ("Federation", "Galaxy")
	assert C.GetShipGroups("Defiant") == ("Federation", None)
	assert C.GetShipGroups("SomeStockShip") == (None, None)


def run():
	failed = 0
	names = [n for n in sorted(globals()) if n.startswith("test_")]
	for n in names:
		try:
			globals()[n]()
			print("PASS " + n)
		except Exception as e:
			failed = failed + 1
			print("FAIL " + n + ": " + type(e).__name__ + " " + str(e)[:120])
	print(str(len(names) - failed) + "/" + str(len(names)) + " passed")
	return failed


if __name__ == "__main__":
	sys.exit(run())
