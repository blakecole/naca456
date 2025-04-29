# ********************************************************** #
#    NAME: Blake Cole                                        #
#    ORGN: (self)                                            #
#    FILE: main.py                                           #
#    DATE: 30 APR 2025                                       #
# ********************************************************** #

from naca456 import NACA456

"""
INPUT PARAMETERS:
a           Extent of constant loading, as fraction of chord.
            (only applies to 6-digit camber lines)
        
camber		Name of the camber line, enclosed in quotes.
            (acceptable values are '0', '2', '3', '3R', '6' and '6M')
            
cl		    Design lift coefficient of the camber line.
            (only applies to 3-digit, 3-digit-reflex, 6-series and 
            series camber lines)
            
chord		Model chord used for listing ordinates in dimensional units.

cmax		Maximum camber, as a fraction of chord.

dencode 	Spacing of the x-array where the points are computed.
			=0 if specified by user
			=1 for coarse output
			=2 for fine output
			=3 for very fine output
            
leindex		Leading edge radius parameter.
			(only applies to 4-digit-modified profiles)
            
name		Title desired on output. It must be enclosed in quotes.

ntable		Size of xtable (only if dencode==0).

profile		Thickness family name, enclosed in quotes.
            (acceptable values are '4', '4M', '63', '64', '65', '66', '67',
            '63A', '64A', '65A')
            
toc		    Thickness-chord ratio.

xmaxc		Chordwise position of maximum camber, as fraction of chord.
            (only used for 2-digit camber lines).
            
xmaxt		Chordwise location of maximum thickness, as fraction of chord.
            (only used for 4-digit modified airfoils)
            
xorigin		X-coordinate of the leading edge of the airfoil.

yorigin		Y-coordinate of the leading edge of the airfoil.      
  
xtable		Table of points (ntable values) at which the airfoil ordinates
			will be computed.

TECHNICAL PAPER:
Carmichael, Ralph L. "Algorithm for Calculating Coordinates of Cambered
NACA Airfoils At Specified Chord Locations".  AIAA Paper 2001-5235, Nov 2001.
https://www.pdas.com/refs/aiaa5235.pdf
"""

naca = NACA456()
parameters = {
    'profile': '63',
    'camber' : '6M',
    'toc'    : 0.15,
    'cl'     : 0.6,
    'dencode': 3
}

result = naca.generate(parameters, preview=True)
if len(result)==3:
    print(" Built cambered profile with ", len(result[0]), " points.")
else:
    print(" Built symmmetric profile with ", len(result[0]), " points.")