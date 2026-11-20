###############################################################################
#	Spaceframe - core configuration
#
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
#	Each module has its own Config.py in Modules\<Name>\.
###############################################################################

# Modules found in Modules\ are enabled automatically.
# Set a module to 0 here to disable it, e.g. "MVShields": 0
Modules = {
	"MVShields": 1,
	"AblativeArmor": 1,
	"StatusHUD": 1,
	"AutoFire": 1,
}

# Time between cycles of the shared timer, in game seconds.
# Lower = modules react faster.
Interval = 0.25

# 1 = also runs in multiplayer (may desync), 0 = offline only.
EnableInMultiplayer = 0

# 0 = off.
# 1 = write the modules' log to Spaceframe_debug.log in the game folder
#     (needs the optional 'fileio' patch of tools/exe_patch.py; without it one
#     banner says the log file is unavailable). The game's own console shows nothing.
# 2 = the log (as 1) and also short banners on screen (target plans, errors,
#     Secondary Target trace).
# Switching Auto Fire / Secondary Target on or off always shows a banner.
Debug = 0
