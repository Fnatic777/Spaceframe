###############################################################################
#	Spaceframe - ship list
#
#	Which ships use which technology: for every ship (All), by race
#	(Races), by family (Families) and ship by ship (Ships). Each level
#	overrides the one before it, so a race can get a technology and one of
#	its ships something else, or 0 to switch it off:
#	    All  <  Races  <  Families  <  the ship's Bedrock plugin  <  Ships
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
#
#	Ship name = the ship's FILE NAME, without extension, exactly as written
#	(upper/lower case matters): the same name as the plugin in
#	scripts\Custom\Bedrock\Ships\ and the file in scripts\ships\.
#	E.g. "AkiraCVS" (file AkiraCVS.py), NOT "Akira CVS" (name shown in the
#	game) nor "Akira" (hardpoint name). The "Peregrine FT" in the menu is
#	the file Fighter.py.
#
#	Each technology takes Def (the default value set in that module's
#	Config.py) or a number chosen for that ship:
#	  "MVShields": Def or 1 to 100  - multivectral shields, efficiency
#	                                  (default: DefaultEfficiency, 100)
#	  "AblativeArmor": Def or %     - ablative armor, capacity as a
#	                                  percentage of the hull
#	                                  (default: DefaultArmor, 50)
#	  "AutoFire": Def               - automatic fire for the player's ship
#	                                  (switched on with L or the menu)
#	  "SecondaryTarget": Def or 1-7 - weapons that cannot reach the main
#	                                  target shoot other enemies; the number
#	                                  adds 1 phasers, 2 torpedoes, 4 pulse
#	                                  (default: Weapons, 7; 0 = off)
#	A ship without a technology simply does not list it.
#
#	Races and families come from each ship's Orion Delta plugin
#	(scripts\Custom\Bedrock\Ships\<Ship>.py): Race = "Federation",
#	"Romulan", "Klingon"...; family = its SubMenu, the sub-menu the variants
#	share in the ship menus, e.g. "Galaxy" for Galaxy, GalaxyCVB, GalaxyX...
#	Write them exactly as in the plugin. Ships without a plugin (stock ships)
#	or with SubMenu = "N/A" have no race or family: only All and Ships apply.
#	The diagnostics command (see the README) shows each ship's race and
#	family.
#
#	On Orion Delta a ship can also get a technology from its own Bedrock
#	plugin: add e.g. "MVShields = 80" above "###Do Not Change Below###"
#	(use -1 there for the default value). Ships (below) wins over it.
###############################################################################

# Use the module's default value.
Def = -1
Default = Def		# older name, still accepted

# Every ship.
All = {
	"AutoFire": Def,	# only ever acts on the ship the player controls
	"SecondaryTarget": Def,	# only ever acts on the ship the player controls
}

# By race.
Races = {
	"Federation":			{"MVShields": Def},
	"TMP Federation":		{"MVShields": Def},
	"ENT Starfleet":		{"MVShields": Def},
}

# By family (all the variants of a class).
Families = {
	"Prometheus":		{"AblativeArmor": Def},
	"Sovereign":		{"AblativeArmor": Def},
}

# Ship by ship.
Ships = {
	"DefiantNX":		{"AblativeArmor": 25},
	"Defiant":			{"AblativeArmor": Def},
	"Steamrunner":		{"AblativeArmor": Def},
	"SovereignR":		{"AblativeArmor": 75},
	"Inquiry":			{"AblativeArmor": Def},
	"ExcelsiorII":		{"AblativeArmor": 25},
	"NeoConstitutionR":	{"AblativeArmor": 25},
	"Odyssey":			{"AblativeArmor": 100},
	"Peregrine":		{"AblativeArmor": Def},	# Peregrine FT launched by carriers
	"Fighter":			{"AblativeArmor": Def},	# Peregrine FT from the menu
}
