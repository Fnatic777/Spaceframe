###############################################################################
#	MV Shields - Spaceframe module configuration
#
#	Edit with a text editor (Notepad++ recommended). Close the file in the
#	editor when you are done, so an old copy is not saved over it later.
#	Timer interval, multiplayer and debug settings are in the core
#	configuration: scripts\Custom\Spaceframe\Config.py
###############################################################################

# Which ships have multivectral shields is set in the Spaceframe ship list:
#     scripts\Custom\Spaceframe\Ships.py    (e.g. "Galaxy": {"MVShields": Def})
# An old "Ships = {...}" list here is still accepted.

# Default efficiency, from 1 to 100, used for ships set to Def in Ships.py.
# It is the share of the difference between the facings corrected each time
# the shields are redistributed:
#   100 = fully equalized at once; 50 = half of the difference each time;
#   lower values = the hit facing stays weak for longer.
# A ship can use its own value instead, e.g. "Excelsior": {"MVShields": 40}.
DefaultEfficiency = 100

# When the shields are redistributed:
#   0 = off (MV Shields does nothing)
#   1 = on hit only   - immediately when a weapon hits the ship
#   2 = cycle only    - on every cycle of the Spaceframe timer
#   3 = both          - on hit and on every cycle (recommended)
# The cycle also covers what is not a weapon hit: shield recharge, Orion's
# Shield Transfer and Power Macros, collisions.
Mode = 3
