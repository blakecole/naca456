# ********************************************************** #
#    NAME: Blake Cole                                        #
#    ORGN: (self)                                            #
#    FILE: run_naca456.py                                    #
#    DATE: 29 APR 2025                                       #
# ********************************************************** #
"""
A Python wrapper to run the PDAS naca456 executable.

Directory layout (absolute under project root):
    root = Path.home()/"GitHub"/"naca456"
      ├── naca456       (executable)
      ├── nml/          (input files)
      ├── out/          (.out files)
      ├── gnu/          (.gnu files)
      ├── dbg/          (.dbg files)
      └── out/xfoil/    (.dat files for XFOIL)

Features:
  • Accept any /NACA/ namelist key → writes verbatim, with Fortran quoting
  • Write to nml/<stem>.nml, run once (interactive), move outputs to out/, gnu/, dbg/
  • Optional return_xy + preview plotting using namelist['name'] as title
  • Parses both symmetric and cambered output
  • Export a labeled .dat file for XFOIL in out/xfoil via _export_for_xfoil()
  • Timeout and error handling
"""

import re
import subprocess, shutil
from pathlib import Path
from typing import Any, Dict, Tuple, Optional, Union

import numpy as np
import matplotlib.pyplot as plt


class NACA456:
    """
    A Python wrapper for PDAS naca456:
      - writes namelist (.nml)
      - runs naca456 interactively
      - moves .out, .gnu, .dbg
      - parses symmetric and cambered coords
      - exports .dat for XFOIL
    """
    def __init__(self,
                 root: Union[Path, str] = Path.home()/"GitHub"/"naca456",
                 exe: str = "naca456"):
        self.root = Path(root).expanduser().resolve()
        self.exe = self.root / exe
        if not self.exe.exists():
            raise FileNotFoundError(f"naca456 not found at {self.exe}")
        
        # ensure directories exist
        for sub in ("nml","out","gnu","dbg","out/xfoil"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)


    def _format_val(self, v: Any) -> str:
        if isinstance(v, bool):
            return ".TRUE." if v else ".FALSE."
        if isinstance(v, str):
            return v if v.startswith(("'", '"')) else f"'{v}'"
        return str(v)
    
    
    def _make_naca_name(self, nml: Dict[str, Any]) -> str:
        """
        Generate the canonical NACA name from namelist dict.
        Supports 4-digit, 5-digit, 6/7/8-series, 16-series.
        """
        prof = str(nml.get('profile','')).upper()
        cl   = float(nml.get('cl', 0.0))
        t    = float(nml.get('toc', 0.0))
        td = int(round(t * 100))

        if prof == '4':
            m = int(round(float(nml.get('cmax', 0.0)) * 100))
            p = int(round(float(nml.get('xmaxc', 0.0)) * 10))
            return f"NACA {m}{p}{td:02d}"
        if prof == '5':
            X = int(round((cl * 10) / 1.5))
            YZ = int(round(float(nml.get('xmaxc', 0.0)) * 20))
            return f"NACA {X}{YZ:02d}{td:02d}"
        if prof.startswith(('6','7','8')):
            cl_dig = int(round(cl * 10))
            return f"NACA {prof}{cl_dig}{td:02d}"
        if prof == '16':
            X = int(round(cl * 10))
            return f"NACA 16-{X}{td:02d}"

        raise ValueError(f"Unsupported profile family: {prof}")
    
    
    def _export_for_xfoil(self,
                          x: np.ndarray,
                          y_upper: np.ndarray,
                          y_lower: np.ndarray,
                          airfoil_name: str,
                          stem: str
                          ) -> Path:
        
        """
        Reorder arrays from TE→LE→TE, and export for XFOIL.
        """
        xs = np.concatenate([x[::-1], x[1:]])
        ys = np.concatenate([y_upper[::-1], y_lower[1:]])
        datp = self.root / 'out' / 'xfoil' / f"{stem}.dat"
        with datp.open('w') as f:
            f.write(f"{airfoil_name}\n")
            for xi, yi in zip(xs, ys): f.write(f"{xi:.6f}  {yi:.6f}\n")
        return datp


    def generate(self,
                 namelist: Dict[str, Any],
                 *,
                 preview: bool = False,
                 timeout: int = 20
                 ) -> Union[Tuple[np.ndarray,np.ndarray], Tuple[np.ndarray,np.ndarray,np.ndarray]]:
        """
        namelist: dict of NACA profile shape parameters
        preview: if True, plot profile
        timeout: seconds to wait for naca456

        Returns (x,y) for symmetric or (x, y_up, y_low) for cambered.
        """
        
        # 0) Get NACA profile name
        if namelist.get('name') is None:
            name = self._make_naca_name(namelist)
            namelist['name'] = name
        else:
            name = namelist['name']
            
        # create filename stem
        stem = name.lower()
        stem = re.sub(r'[^a-z0-9]', '', stem)
        print("\n " + name + " (" + stem + ")")
        
        
        # 1) Write .nml input file
        nml = self.root / "nml" / f"{stem}.nml"
        with nml.open('w') as f:
            f.write("&NACA\n")
            for k, v in namelist.items():
                f.write(f"  {k} = {self._format_val(v)},\n")
            f.write("/\n")
        
        # 2) Invoke naca456 interactively
        subprocess.run(
            [str(self.exe)],
            cwd=self.root,
            input=str(nml) + "\n",
            text=True,
            check=True,
            timeout=timeout
        )
        
        # 3) Move outputs
        for src, d in (('naca.out','out'),('naca.gnu','gnu'),('naca.dbg','dbg')):
            s = self.root/src
            if s.exists():
                shutil.move(s, self.root / d / f"{stem}.{src.split('.')[-1]}")
        
        # 4) Parse coords
        outp = self.root/'out'/f"{stem}.out"
        lines = outp.read_text().splitlines()
        
        # find interpolated vs symmetric
        interp_i = next((i for i,L in enumerate(lines)
                         if 'INTERPOLATED COORDINATES' in L),None)
        x, yu, yl = [], [], []
        
        if interp_i is not None:
            # cambered
            is_cambered = True
            header_i = next(j for j in range(interp_i+1, len(lines))
                            if lines[j].strip().lower().startswith('x') and 'yupper' in lines[j].lower())
            for L in lines[header_i+1:]:
                if not L.strip() or L.strip().lower().startswith('end'):
                    break
                p=L.split()
                x.append(float(p[1].strip(" *")))
                yu.append(float(p[2].strip(" *")))
                yl.append(float(p[3].strip(" *")))
        else:
            # symmetric
            is_cambered = False
            header_i = next(i for i,L in enumerate(lines)
                            if L.lstrip().lower().startswith('x') and 'dy/dx' in L.lower())
            for L in lines[header_i+1:]:
                if not L.strip() or L.strip().lower().startswith('end'):
                    break
                p=L.split()
                x.append(float(p[1].strip(" *")))
                yu.append(float(p[2].strip(" *")))
            yl = [-v for v in yu]
        
        x = np.array(x)
        yu = np.array(yu)
        yl = np.array(yl)
        
        # 5) Preview plot
        if preview:
            plt.figure(figsize=(6,3))
            plt.plot(x, yu, '-c', linewidth=0.8, label='Upper')
            if is_cambered:
                plt.plot(x, yl, '-r', linewidth=0.8, label='Lower'), plt.legend()
            else:
                plt.plot(x, yl, '-c', linewidth=0.8, label='Lower')
            plt.axis('equal')
            plt.grid(alpha=0.4)
            plt.title(name)
            plt.xlabel('x/c')
            plt.ylabel('y/c')
            plt.show()
    
        # 6) Export for XFOIL
        self._export_for_xfoil(x, yu, yl, name, stem)
        
        # 7) Return
        return (x, yu, yl) if is_cambered else (x, yu)



# === Example Usage ================================================
if __name__ == "__main__":
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