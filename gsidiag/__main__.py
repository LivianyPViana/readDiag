#!/usr/bin/env python3
#-----------------------------------------------------------------------------#
#           Group on Data Assimilation Development - GDAD/CPTEC/INPE          #
#-----------------------------------------------------------------------------#
#BOP
#
# !SCRIPT: gsiDiag.py
#
# !DESCRIPTION: Class to read and plot GSI diagnostics files.
#
# !CALLING SEQUENCE:
#
# !REVISION HISTORY: 
# 09 out 2017 - J. G. de Mattos - Initial Version
#
# !REMARKS:
#   Work only with conventional diganostics files
#
#EOP
#-----------------------------------------------------------------------------#
#BOC

"""
This module defines the majority of gsidiag functions, including all plot types
"""
from diag2python import diag2python as d2p
from .datasources import getVarInfo
import pandas as pd
import geopandas as gpd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.axes_grid1 import make_axes_locatable
from cartopy import crs as ccrs
import gc
from textwrap import wrap
import matplotlib as mpl
import matplotlib.ticker as mticker
from matplotlib.offsetbox import AnchoredOffsetbox, TextArea, HPacker, VPacker

def help():
    print('Esta é uma ajudada')


def getColor(minVal, maxVal, value, hex=False, cmapName=None):

    try:
       import matplotlib.cm as cm
       from matplotlib.colors import Normalize
       from matplotlib.colors import rgb2hex
    except ImportError:
       pass # module doesn't exist, deal with it.

    if cmapName is None:
        cmapName='Paired'

    # Get a color map
    cmap = cm.get_cmap(cmapName)

    # Get normalize function (takes data in range [vmin, vmax] -> [0, 1])
    norm = Normalize(vmin=minVal, vmax=maxVal)
    
    if hasattr(value,'__iter__'):

       color = []
       for i in range(len(value)):
          if hex is True:
              color.append(rgb2hex(cmap(norm(value[i]))))
          else:
              color.append(cmap(norm(value[i]),bytes=True))

    else:

        if hex is True:
            color = rgb2hex(cmap(norm(value)))
        else:
            color = cmap(norm(value),bytes=True)

    return color

def geoMap(**kwargs):
    
    if 'ax' not in kwargs:
        fig  = plt.figure(figsize=(12, 6))
        ax   = fig.add_subplot(1, 1, 1)#, projection=ccrs.PlateCarree())
    else:
        ax = kwargs['ax']
        del kwargs['ax']

    
    path=gpd.datasets.get_path('naturalearth_lowres')
    
    world = gpd.read_file(path)
    gdp_max = world['gdp_md_est'].max()
    gdp_min = world['gdp_md_est'].min()
    
    ax = world.plot(ax=ax, facecolor='lightgrey', edgecolor='k')#,**kwargs)
    
    # set axis range
    ax.set_xlim([-180,180])
    ax.set_xlabel('Longitude')
    ax.set_ylim([ -90, 90])
    ax.set_ylabel('Latitude')

    return ax
    
class setcolor:
    HEADER    = '\033[95m'
    OKBLUE    = '\033[94m'
    OKGREEN   = '\033[92m'
    WARNING   = '\033[93m'
    FAIL      = '\033[91m'
    ENDC      = '\033[0m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'

class read_diag(object):

    """
    read a diagnostic file from gsi. Return an array with
    some information.
    """
    #@profile(precision=8)

    def __init__(self, diagFile, diagFileAnl=None, isisList=None, zlevs=None):

        self._diagFile     = diagFile
        self._diagFileAnl  = diagFileAnl

        if diagFileAnl == None:
            extraInfo = False
        else:
            extraInfo = True

        convIndex =['lat','lon', 'elev', 'prs', 'hgt', 'press', 'time', 'idqc', 'iuse', 'iusev', 
                   'wpbqc', 'inp_err', 'adj_err', 'inverr', 'oer', 'obs', 'omf', 'oma', 'imp', 'dfs']

        radIndex  = ['lat','lon','elev','nchan','time','iuse','idqc','inverr','oer','obs',
                     'omf','omf_nobc','emiss','oma','oma_nobc','imp','dfs']
                     
        if isisList is None:
            isis = np.array(['None'],dtype='c').T
        else:
            # put all string with same length
            s=len(max(isisList,key=len))
            l=[]
            for i in isisList:
                l.append(i.ljust(s,' '))
            isis = np.array(l,dtype='c').T
            
        self._FNumber    = d2p.open(self._diagFile, self._diagFileAnl, isis)
        if (self._FNumber <= -1):
            self._FNumber = None
            print('Some was was wrong during reading files ...')
            return

        self._FileType   = d2p.getFileType(self._FNumber)
        if (self._FileType == -1):
            print('Some wrong was happening!')
            return
        
        self._undef = d2p.getUndef(self._FNumber)
        
        # set default levels to obtain data information
        if zlevs is None:
           self.zlevs = [1000.0,900.0,800.0,700.0,600.0,500.0,400.0,300.0,250.0,200.0,150.0,100.0,50.0,0.0]
        else:
           self.zlevs = zlevs

        #
        # Get extra informations
        #

        self._nVars     = d2p.getnvars(self._FNumber)
        vnames,nTypes   = d2p.getObsVarInfo(self._FNumber,self._nVars);
        self.varNames   = []
        self.obsInfo    = {}
        for i, name in enumerate(vnames):
            obsName = name.tostring().decode('UTF-8').strip()
            self.varNames.append(obsName)
            vTypes, svTypes = d2p.getVarTypes(self._FNumber,obsName, nTypes[i])
            sTypes = svTypes.tostring().decode('UTF-8').strip().split()
            df = {}
            if self._FileType == 1:
            # for convetional data
               for i, vType in enumerate(vTypes):
                   nObs = d2p.getobs(self._FNumber, obsName, vType, 'None', self.zlevs, len(self.zlevs))
                   if extraInfo is True:
                       d = pd.DataFrame(d2p.array2d.copy().T,index=convIndex).T
                       d2p.array2d = None
                   else:
                       d = pd.DataFrame(d2p.array2d.copy().T,index=convIndex[:17]).T
                       d2p.array2d = None

                   # convert all undef to NaN
                   d.replace(to_replace = self._undef,
                             value      = np.nan,
                             inplace    = True)

                   lon = (d.lon + 180) % 360 - 180
                   lat = d.lat
                   df[vType] = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(lon,lat))
                
            elif self._FileType == 2:
            # for satellite data
               for i, sType in enumerate(sTypes):
                   nObs = d2p.getobs(self._FNumber, obsName, 0, sType, self.zlevs, len(self.zlevs))
                   if extraInfo is True:
                       d   = pd.DataFrame(d2p.array2d.copy().T,index=radIndex).T
                       d2p.array2d = None
                   else:
                       d = pd.DataFrame(d2p.array2d.copy().T,index=radIndex[:13]).T
                       d2p.array2d = None

                   # convert all undef to NaN
                   d.replace(to_replace = self._undef,
                             value      = np.nan,
                             inplace    = True)

                   lon = (d.lon + 180) % 360 - 180
                   lat = d.lat
                   df[sType] = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(lon,lat))


            if self._FileType == 1:
                self.obsInfo[obsName] = pd.concat(df.values(),keys=df.keys(), names=['kx','points'])
            elif self._FileType == 2:
                self.obsInfo[obsName] = pd.concat(df.values(),keys=df.keys(), names=['SatId','points'])
            
        self.obs  = pd.concat(self.obsInfo, sort=False).reset_index(level=2, drop=True)

    def overview(self):

        """
        Creates a dictionary of the existing variables and types. Returns a Python dictionary.

        Usage: overview()
        """

        variablesList = {}
        for var in self.varNames:
            variablesTypes = []
            for kx in self.obsInfo[var].index.levels[0]:
                variablesTypes.append(kx)
            variablesList.update({var:variablesTypes})
        return variablesList

    def pfileinfo(self):

        """
        Prints a fancy list of the existing variables and types.

        Usage: pfileinfo()
        """

        for name in self.varNames:
            print('Variable Name :',name)
            print('              └── kx => ', end='', flush=True)
            for kx in self.obsInfo[name].index.levels[0]:
               print(kx,' ', end='', flush=True)
            print()

            print()
       
    def close(self):

        """
        Closes a previous openned file. Returns an integer status value.

        Usage: close()
        """

        iret = d2p.close(self._FNumber)
        self._FileName = None # File name
        self._FNumber  = None # File unit number to be closed
        self._nVars    = None # Total of variables
        self.varNames  = None # Name of variables
        self.obsInfo   = None 
        self.nObs      = None # Number of observations for vName
        del self
        gc.collect()
        
        return iret

    def tocsv(self, varName=None, varType=None, dateIni=None, dateFin=None, nHour="06", Level=None, Lay = None, SingleL=None):
        
        '''
        A função tocsv gera um arquivo CSV com o resultado do processamento dos dados provenientes do ReadDiag.
        Dentre as informações contidas no arquivo CSV estão:

            Data, media, desvio padrão, total de dados

        Estas informações são apresentadas para cada nível ou para um nível em particular. A seguir se encontra um exemplo de 
        como usar a função tocsv.

        Exemplo:

        dini     = 2017010100 # Data inicial
        dfin     = 2017010106 # Data final
        varName  = "ps"
        varType  = 180
        Level    = None
        path     = '/stornext/online6/das/Avalia/SMR/EXP02/gsi/dataout/'

        gsiTools = gs.gsiFunctions()
        gsiTools.tocsv(varName=varName, varType=varType, dateIni=dini, dateFin=dfin, path=path, Level=None)

        '''

        delta = nHour
        omflag = "OmF"
        omflaga = "OmA"

        Laydef = 50

        separator = " ====================================================================================================="

        print()
        print(separator)
        #print(" Reading dataset in " + data_path)
        print(" Analyzing data of variable: " + varName + "  ||  type: " + str(varType) + "  ||  " + getVarInfo(varType, varName, 'instrument') + "  ||  check: " + omflag)
        print(separator)
        print()

        zlevs_def = list(map(int,self[0].zlevs))

        datei = datetime.strptime(str(dateIni), "%Y%m%d%H")
        datef = datetime.strptime(str(dateFin), "%Y%m%d%H")
        date  = datei

        levs_tmp, DayHour_tmp = [], []
        info_check = {}
        f = 0
        while (date <= datef):
            
            datefmt = date.strftime("%Y%m%d%H")
            DayHour_tmp.append(date.strftime("%d%H"))
            
            dataDict = self[f].obsInfo[varName].loc[varType]
            info_check.update({date.strftime("%d%H"):True})

            if 'prs' in dataDict and (Level == None or Level == "Zlevs"):
                if(Level == None):
                    levs_tmp.extend(list(set(map(int,dataDict['prs']))))
                else:
                    levs_tmp = zlevs_def[::-1]
                info_check.update({date.strftime("%d%H"):True})
                print(date.strftime(' Preparing data for: ' + "%Y-%m-%d:%H"))
                print(' Levels: ', sorted(levs_tmp), end='\n')
                print("")
                f = f + 1
            else:
                if (Level != None and Level != "Zlevs") and info_check[date.strftime("%d%H")] == True:
                    levs_tmp.extend([Level])
                    print(date.strftime(' Preparing data for: ' + "%Y-%m-%d:%H"), ' - Level: ', Level , end='\n')
                    f = f + 1
                else:
                    info_check.update({date.strftime("%d%H"):False})
                    print(date.strftime(setcolor.WARNING + ' Preparing data for: ' + "%Y-%m-%d:%H"), ' - No information on this date ' + setcolor.ENDC, end='\n')

            del(dataDict)
            
            date = date + timedelta(hours=int(delta))
            
        if(len(DayHour_tmp) > 4):
            DayHour = [hr if (ix % int(len(DayHour_tmp) / 4)) == 0 else '' for ix, hr in enumerate(DayHour_tmp)]
        else:
            DayHour = DayHour_tmp

        zlevs = [z if z in zlevs_def else "" for z in sorted(set(levs_tmp+zlevs_def))]

        print()
        print(separator)
        print()

        list_meanByLevs, list_stdByLevs, list_countByLevs = [], [], []
        list_meanByLevsa, list_stdByLevsa, list_countByLevsa = [], [], []
        date = datei
        levs = sorted(list(set(levs_tmp)))
        levs_tmp.clear()
        del(levs_tmp[:])

        head_levs = ['datetime']
        for lev in levs:
            head_levs.append('mean'+str(lev))
            head_levs.append('std'+str(lev))
            head_levs.append('count'+str(lev))

        dset = []
        dseta = []
        f = 0
        while (date <= datef):

            print(date.strftime(' Calculating for ' + "%Y-%m-%d:%H"))
            datefmt = date.strftime("%Y%m%d%H")

            try: 
                if info_check[date.strftime("%d%H")] == True:
                    dataDict = self[f].obsInfo[varName].loc[varType]
                    dataByLevs, mean_dataByLevs, std_dataByLevs, count_dataByLevs = {}, {}, {}, {}
                    dataByLevsa, mean_dataByLevsa, std_dataByLevsa, count_dataByLevsa = {}, {}, {}, {}
                    [dataByLevs.update({int(lvl): []}) for lvl in levs]
                    [dataByLevsa.update({int(lvl): []}) for lvl in levs]
                    if Level != None and Level != "Zlevs":
                        if SingleL == None:
                            [ dataByLevs[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) == Level ]
                            [ dataByLevsa[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) == Level ]
                            forplot = ' Level='+str(Level) +'hPa'
                            forplotname = 'level_'+str(Level) +'hPa'
                        else:
                            if SingleL == "All":
                                [ dataByLevs[Level].append(v) for v in self[f].obsInfo[varName].loc[varType].omf ]
                                [ dataByLevsa[Level].append(v) for v in self[f].obsInfo[varName].loc[varType].oma ]
                                forplot = ' Layer=Entire Atmosphere'
                                forplotname = 'layer_allAtm'
                            else:
                                if SingleL == "OneL":
                                    if Lay == None:
                                        print("")
                                        print(" Variable Lay is None, resetting it to its default value: "+str(Laydef)+" hPa.")
                                        print("")
                                        Lay = Laydef
                                    [ dataByLevs[int(Level)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) >=Level-Lay and int(p) <Level+Lay ]
                                    [ dataByLevsa[int(Level)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) >=Level-Lay and int(p) <Level+Lay ]
                                    forplot = ' Layer='+str(Level+Lay)+'-'+str(Level-Lay)+'hPa'
                                    forplotname = 'layer_'+str(Level+Lay)+'-'+str(Level-Lay)+'hPa'
                                else:
                                    print(" Wrong value for variable SingleL. Please, check it and rerun the script.")    
                    else:
                        if Level == None:
                            [ dataByLevs[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) ]
                            [ dataByLevsa[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) ]
                            forplotname = 'all_levels_byLevels'
                        else:
                            for ll in range(len(levs)):
                                if Lay == None:
                                    lv = levs[ll]
                                    if ll == 0:
                                        Llayi = 0
                                    else:
                                        Llayi = (levs[ll] - levs[ll-1]) / 2.0
                                    if ll == len(levs)-1:
                                        Llayf = Llayi
                                    else:
                                        Llayf = (levs[ll+1] - levs[ll]) / 2.0
                                    cutlevs = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) >=lv-Llayi and int(p) <lv+Llayf ]
                                    cutlevsa = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) >=lv-Llayi and int(p) <lv+Llayf ]
                                    forplotname = 'all_levels_filledLayers'
                                else:
                                    cutlevs = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) >=lv-Lay and int(p) <lv+Lay ]
                                    cutlevsa = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) >=lv-Lay and int(p) <lv+Lay ]
                                    forplotname = 'all_levels_bylayers'
                                [ dataByLevs[lv].append(il) for il in cutlevs ]
                                [ dataByLevsa[lv].append(il) for il in cutlevsa ]
                    f = f + 1
                for lv in levs:
                    if len(dataByLevs[lv]) != 0 and info_check[date.strftime("%d%H")] == True:
                        mean_dataByLevs.update({int(lv): np.mean(np.array(dataByLevs[lv]))})
                        std_dataByLevs.update({int(lv): np.std(np.array(dataByLevs[lv]))})
                        count_dataByLevs.update({int(lv): len(np.array(dataByLevs[lv]))})
                        mean_dataByLevsa.update({int(lv): np.mean(np.array(dataByLevsa[lv]))})
                        std_dataByLevsa.update({int(lv): np.std(np.array(dataByLevsa[lv]))})
                        count_dataByLevsa.update({int(lv): len(np.array(dataByLevsa[lv]))})
                    else:
                        mean_dataByLevs.update({int(lv): -99})
                        std_dataByLevs.update({int(lv): -99})
                        count_dataByLevs.update({int(lv): -99})
                        mean_dataByLevsa.update({int(lv): -99})
                        std_dataByLevsa.update({int(lv): -99})
                        count_dataByLevsa.update({int(lv): -99})
            
            except:
                if info_check[date.strftime("%d%H")] == True:
                    print("ERROR in time_series function.")
                else:
                    print(setcolor.WARNING + "    >>> No information on this date (" + str(date.strftime("%Y-%m-%d:%H")) +") <<< " + setcolor.ENDC)

                for lv in levs:
                    mean_dataByLevs.update({int(lv): -99})
                    std_dataByLevs.update({int(lv): -99})
                    count_dataByLevs.update({int(lv): -99})
                    mean_dataByLevsa.update({int(lv): -99})
                    std_dataByLevsa.update({int(lv): -99})
                    count_dataByLevsa.update({int(lv): -99})

            if Level == None or Level == "Zlevs":
                list_meanByLevs.append(list(mean_dataByLevs.values()))
                list_stdByLevs.append(list(std_dataByLevs.values()))
                list_countByLevs.append(list(count_dataByLevs.values()))
                list_meanByLevsa.append(list(mean_dataByLevsa.values()))
                list_stdByLevsa.append(list(std_dataByLevsa.values()))
                list_countByLevsa.append(list(count_dataByLevsa.values()))
            else:
                list_meanByLevs.append(mean_dataByLevs[int(Level)])
                list_stdByLevs.append(std_dataByLevs[int(Level)])
                list_countByLevs.append(count_dataByLevs[int(Level)])
                list_meanByLevsa.append(mean_dataByLevsa[int(Level)])
                list_stdByLevsa.append(std_dataByLevsa[int(Level)])
                list_countByLevsa.append(count_dataByLevsa[int(Level)])
                
            dataByLevs.clear()
            mean_dataByLevs.clear()
            std_dataByLevs.clear()
            count_dataByLevs.clear()
            dataByLevsa.clear()
            mean_dataByLevsa.clear()
            std_dataByLevsa.clear()
            count_dataByLevsa.clear()

            date_finale = date
            date = date + timedelta(hours=int(delta))

            values_levs = [datefmt]
            values_levsa = [datefmt]
            for me,sd,nd in zip(list_meanByLevs[-1][:],list_stdByLevs[-1][:],list_countByLevs[-1][:]):
                values_levs.append(me)
                values_levs.append(sd)
                values_levs.append(nd)
            for me,sd,nd in zip(list_meanByLevsa[-1][:],list_stdByLevsa[-1][:],list_countByLevsa[-1][:]):
                values_levsa.append(me)
                values_levsa.append(sd)
                values_levsa.append(nd)
            dset.append(values_levs)
            dseta.append(values_levsa)

        print()
        print(separator)
        print()


        # ==============================================================================================================
        # Save dataset into CSV File ===================================================================================

        print("\n Saving Dataset in CSV File...  ")

        dataout_file  = 'dataout_' + str(varName) + '_' + str(varType) + '_' + omflag  + '.csv'
        dataout_filea = 'dataout_' + str(varName) + '_' + str(varType) + '_' + omflaga + '.csv'
        df = pd.DataFrame.from_records(dset, columns=head_levs)
        df.to_csv(dataout_file, index=False)
        del(df)
        df = pd.DataFrame.from_records(dseta, columns=head_levs)
        df.to_csv(dataout_filea, index=False)
        del(df)
        print(" Done \n")

        return

class plot_diag(object):
    """
    plot diagnostic file from gsi. 
    """

    def plot(self, varName, varType, param, mask=None, **kwargs):
        '''
        The plot function makes a plot for the selected observation by using information of the following columns available within the dataframe.
 
        Available columns to be used with the plot function:

        lat  : All latitudes from the selected kinds 
        lon  : All longitudes from the selected kinds
        prs  : Pressure level of the observation
        lev  : Pressure levels of the observation 
        time : Time of the observation (in minutes, relative to the analysis time)
        idqc : Quality control mark or event mark 
        iuse : Use flag (use = 1; monitoring = -1)
        iusev: Value of the flag used in the analysis
        obs  : Observation value

        Example:
        gd.plot('ps', 187, 'obs', mask='iuse == 1')
        
        In the above example, a plot will be made displaying by using the values of the used surface pressure observations of the kind 187 (ADPSFC).
 
        '''
        #
        # Parse options 
        #
        if 'style' in kwargs:
            plt.style.use(kwargs['style'])
            del kwargs['style']
        else:
            plt.style.use('seaborn')
        
        if 'ax' not in kwargs:
            fig = plt.figure(figsize=(12, 6))
            ax  = fig.add_subplot(1, 1, 1)
        else:
            ax = kwargs['ax']
            del kwargs['ax']

        if kwargs.get('legend') is True:
            divider = make_axes_locatable(ax)
            cax     = divider.append_axes("right", size="5%", pad=0.1)
            kwargs['cax'] = cax

        if 'title' in kwargs:
            ax.set_title(kwargs['title'])

        if 'cmap' not in kwargs:
            kwargs['cmap'] = 'jet'

        ax = geoMap(ax=ax)

        if mask is None:
            ax  = self.obsInfo[varName].loc[varType].plot(param, ax=ax, **kwargs, legend_kwds={'shrink': 0.5})
        else:
            df = self.obsInfo[varName].loc[varType]
            ax = df.query(mask).plot(param, ax=ax, **kwargs, legend_kwds={'shrink': 0.5})

        
        return ax

    def ptmap(self, varName, varType=None, mask=None, **kwargs):
        '''
        The ptmap function plots the selected observation for the selected kinds.

        Example:
        a.ptmap('uv', [290, 224, 223])
        
        In the above example, a plot for the wind (uv) for the kinds 290 (ASCATW), 224 (VADWND) and 223 (PROFLR) will be made.

        Note: If no kind is explicity informed, all kinds for that particular observation will be considered, which may clutter
        the plot.
        '''
        #
        # Parse options 
        #

        if 'style' in kwargs:
            plt.style.use(kwargs['style'])
            del kwargs['style']
        else:
            plt.style.use('seaborn')

        if 'ax' not in kwargs:
            fig  = plt.figure(figsize=(12, 6))
            ax   = fig.add_subplot(1, 1, 1)
        else:
            ax = kwargs['ax']
            del kwargs['ax']

        if varType is None:
            varType = self.obsInfo[varName].index.levels[0].tolist()

        if 'alpha' not in kwargs:
            kwargs['alpha'] = 0.5

        if 'marker' not in kwargs:
            kwargs['marker'] = '*'

        if 'markersize' not in kwargs:
            kwargs['markersize'] = 5

        if 'linewidth' not in kwargs:
            kwargs['linewidth'] = 1

        if 'legend' not in kwargs:
            kwargs['legend'] = False
            legend = True
        else:
            legend = kwargs['legend']
            kwargs['legend'] = False
                
        
        ax = geoMap(ax=ax)

        # color range
        if type(varType) is list:
            cmin = 0
            cmax = len(varType)-1
        else:
            varType = [varType]
            cmin = 0
            cmax = 1

        legend_labels = []
        for i, kx in enumerate(varType):
            df    = self.obsInfo[varName].loc[kx]

            color = getColor(minVal=cmin, maxVal=cmax,
                             value=i,hex=True,cmapName='Paired')
            instr = getVarInfo(kx,varName,'instrument')

            label = '\n'.join(wrap(varName + '-' + str(kx) + ' | ' + instr,30))
            legend_labels.append(mpatches.Patch(color=color, 
                                 label=label)
                                )

            if mask is None:
               ax = df.plot(ax=ax,c=color, **kwargs)
            else:
               ax = df.query(mask).plot(ax=ax,c=color, **kwargs)
        
        if legend is True:
            plt.subplots_adjust(bottom=0.30)
            plt.legend(handles=legend_labels, loc='upper center', bbox_to_anchor=(0.5, -0.08),
                       fancybox=False, shadow=False, frameon=False, numpoints=1, prop={"size": 9}, labelspacing=1.0, ncol=4)


        return ax

    def pvmap(self, varName=None, mask=None, **kwargs):
        '''
        The pvmap function plots the selected observations without specifying its kinds. It used the flag iuse instead. 

        Example:
        a.pvmap(['uv','ps','t','q'], mask='iuse==1')
        
        In the above example, a plot for the used (iuse=1) observations of wind (uv), surface pressure (ps), temperature (t) and moisture (q) will be made. 
        '''
        #
        # Parse options 
        #
        
        if 'style' in kwargs:
            plt.style.use(kwargs['style'])
            del kwargs['style']
        else:
            plt.style.use('seaborn')
        
        if 'ax' not in kwargs:
            fig = plt.figure(figsize=(12, 6))
            ax  = fig.add_subplot(1, 1, 1)
        else:
            ax = kwargs['ax']
            del kwargs['ax']

        if 'alpha' not in kwargs:
            kwargs['alpha'] = 0.5

        if 'marker' not in kwargs:
            kwargs['marker'] = '*'

        if 'markersize' not in kwargs:
            kwargs['markersize'] = 5

        if 'linewidth' not in kwargs:
            kwargs['linewidth'] = 1

        if 'legend' not in kwargs:
            kwargs['legend'] = False
            legend = True
        else:
            legend = kwargs['legend']
            kwargs['legend'] = False

        #
        # total by var
        #
        
        total = self.obs.groupby(level=0).size()

        #
        # parse options em kwargs

        if varName is None:
            varName = total.sort_values(ascending=False).keys()
        else:
            if type(varName) is list:
               varName = total[varName].sort_values(ascending=False).keys()
            else:
                varName = [varName]
        
        ax = geoMap(ax=ax)

        
        colors_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22']
        setColor = 0
        legend_labels = []
        for var in varName:
            df    = self.obsInfo[var]
            legend_labels.append(mpatches.Patch(color=colors_palette[setColor], label=var) )

            if mask is None:
               ax = df.plot(ax=ax,c=colors_palette[setColor], **kwargs)
            else:
               ax = df.query(mask).plot(ax=ax,c=colors_palette[setColor], **kwargs)
            setColor += 1

        if legend is True:
            plt.legend(handles=legend_labels, numpoints=1, loc='best', bbox_to_anchor=(1.1, 0.6), 
                       fancybox=False, shadow=False, frameon=False, ncol=1, prop={"size": 10})


        return ax

    def pcount(self,varName,**kwargs):

        """
        Plots a histogram of the desired variable and types.

        Usage: pcount(VarName)
        """

        try:
           import matplotlib.pyplot as plt
           import matplotlib.cm as cm
           from matplotlib.colors import Normalize

        except ImportError:
           pass # module doesn't exist, deal with it.
        #
        # Parse options 
        #

        if 'style' in kwargs:
            plt.style.use(kwargs['style'])
            del kwargs['style']
        else:
            plt.style.use('seaborn')

        if 'alpha' not in kwargs:
            kwargs['alpha'] = 0.5

        if 'rot' not in kwargs:
            kwargs['rot'] = 45

        if 'legend' not in kwargs:
            kwargs['legend'] = False


        df = self.obsInfo[varName].groupby(level=0).size()

        # Get a color map
        colors = getColor(minVal=df.min(),maxVal=df.max(),
                          value=df.values,hex=True,cmapName='Paired')

        df.plot.bar(color=colors,**kwargs)

        plt.ylabel('Number of Observations')
        plt.xlabel('KX')
        plt.title('Variable Name : '+varName)
 
    def vcount(self,**kwargs):

        """
        Plots a histogram of the total count of eath variable.

        Usage: pcount(**kwargs)
        """

        try:
           import matplotlib.pyplot as plt
           import matplotlib.cm as cm
           from matplotlib.colors import Normalize

        except ImportError:
           pass # module doesn't exist, deal with it.
        #
        # Parse options 
        #

        if 'style' in kwargs:
            plt.style.use(kwargs['style'])
            del kwargs['style']
        else:
            plt.style.use('seaborn')

        if 'alpha' not in kwargs:
            kwargs['alpha'] = 0.5

        if 'rot' not in kwargs:
            kwargs['rot'] = 0

        if 'legend' not in kwargs:
            kwargs['legend'] = False

        df = pd.DataFrame({key: len(value) for key, value in self.obsInfo.items()},index=['total']).T

        # Get a color map
        colors = getColor(minVal=df.min(),maxVal=df.max(),
                          value=df['total'].values,hex=True,cmapName='Paired')
         
        df.plot.bar(color=colors, **kwargs)

        plt.ylabel('Number of Observations')
        plt.xlabel('Variable Names')
        plt.title('Total Number of Observations')
 
    def kxcount(self,**kwargs):

        """
        Plots a histogram of the total count by KX.

        Usage: pcount(**kwargs)
        """

        try:
           import matplotlib.pyplot as plt
           from matplotlib.colors import Normalize

        except ImportError:
           pass # module doesn't exist, deal with it.
        #
        # Parse options 
        #

        if 'style' in kwargs:
            plt.style.use(kwargs['style'])
            del kwargs['style']
        else:
            plt.style.use('seaborn')

        if 'alpha' not in kwargs:
            kwargs['alpha'] = 0.5

        if 'rot' not in kwargs:
            kwargs['rot'] = 90

        if 'legend' not in kwargs:
            kwargs['legend'] = False

        d  = pd.concat(self.obsInfo, sort=False).reset_index(level=2, drop=True)
        df = d.groupby(['kx']).size()

        # Get a color map
        colors = getColor(minVal=df.min(),maxVal=df.max(),
                          value=df.values,hex=True,cmapName='Paired')
          
        plt.style.use('seaborn')
        df.plot.bar(color=colors, **kwargs)

        plt.ylabel('Number of Observations by KX')
        plt.xlabel('KX number')
        plt.title('Total Number of Observations')
 
    def time_series(self, varName=None, varType=None, dateIni=None, dateFin=None, nHour="06", vminOMA=None, vmaxOMA=None, vminSTD=0.0, vmaxSTD=14.0, Level=None, Lay = None, SingleL=None, Clean=None):
        
        '''
        A função time_series realiza a plotagem da série temporal de diferentes variáveis, considerando diferentes intervalos de tempo. É possivel escolher entre fazer a série
        para um único nível ou para diversos níveis.

        Exemplo:

        dini = 2013010100 # Data inicial
        dfin = 2013010900 # Data final
        nHour = "06"      # Intervalo de tempo
        vName = 'uv'      # Variável
        vType = 224       # Fonte da variável
        vminOMA = -4.0    # Valor mínimo da escala Y para OmF ou OmA
        vmaxOMA = 4.0     # Valor máximo da escala Y para OmF ou OmA
        vminSTD = 0.0     # Valor mínimo da escala Y para o desvio-padrão
        vmaxSTD = 14.0    # Valor máximo da escala Y para o desvio-padrão
        Level = 1000      # Valor do nível a ser feita a série temporal, se não informar, será¡ feita para todos os níveis padrões
        Lay = 15          # Metade do tamanho da camada em hPa se ptar por amostragem em camadas.
        SingleL = "OneL"  # Quando Level tiver um valor fixo, ex: 1000 hPa, o plot pode ser exatamente nesse nível (SingleL = None),
                          # em todos os níveis como uma única camada (SingleL = "All") ou em uma camada definida em torno do Level
                          # variando entre Level-Lay e Level+Lay (SingleL="OneL"). Se Lay não for informado, será usado um valor padrão de 50 hPa. 


        gsiTools = gs.gsiFunctions()
        gsiTools.time_series(varName=vName, varType=vType, dateIni=dini, dateFin=dfin, vminOMA=None, vmaxOMA=None, vminSTD=None, vmaxSTD=None, Level=None)

        '''
        if Clean == None:
            Clean = True

        delta = nHour
        omflag = "OmF"
        omflaga = "OmA"

        Laydef = 50

        separator = " ====================================================================================================="

        print()
        print(separator)
        #print(" Reading dataset in " + data_path)
        print(" Analyzing data of variable: " + varName + "  ||  type: " + str(varType) + "  ||  " + getVarInfo(varType, varName, 'instrument') + "  ||  check: " + omflag)
        print(separator)
        print()

        zlevs_def = list(map(int,self[0].zlevs))

        datei = datetime.strptime(str(dateIni), "%Y%m%d%H")
        datef = datetime.strptime(str(dateFin), "%Y%m%d%H")
        date  = datei

        levs_tmp, DayHour_tmp = [], []
        info_check = {}
        f = 0
        while (date <= datef):
            
            datefmt = date.strftime("%Y%m%d%H")
            DayHour_tmp.append(date.strftime("%d%H"))
            
            dataDict = self[f].obsInfo[varName].loc[varType]
            info_check.update({date.strftime("%d%H"):True})

            if 'prs' in dataDict and (Level == None or Level == "Zlevs"):
                if(Level == None):
                    levs_tmp.extend(list(set(map(int,dataDict['prs']))))
                else:
                    levs_tmp = zlevs_def[::-1]
                info_check.update({date.strftime("%d%H"):True})
                print(date.strftime(' Preparing data for: ' + "%Y-%m-%d:%H"))
                print(' Levels: ', sorted(levs_tmp), end='\n')
                print("")
                f = f + 1
            else:
                if (Level != None and Level != "Zlevs") and info_check[date.strftime("%d%H")] == True:
                    levs_tmp.extend([Level])
                    print(date.strftime(' Preparing data for: ' + "%Y-%m-%d:%H"), ' - Level: ', Level , end='\n')
                    f = f + 1
                else:
                    info_check.update({date.strftime("%d%H"):False})
                    print(date.strftime(setcolor.WARNING + ' Preparing data for: ' + "%Y-%m-%d:%H"), ' - No information on this date ' + setcolor.ENDC, end='\n')

            del(dataDict)
            
            date = date + timedelta(hours=int(delta))
            
        if(len(DayHour_tmp) > 4):
            DayHour = [hr if (ix % int(len(DayHour_tmp) / 4)) == 0 else '' for ix, hr in enumerate(DayHour_tmp)]
        else:
            DayHour = DayHour_tmp

        zlevs = [z if z in zlevs_def else "" for z in sorted(set(levs_tmp+zlevs_def))]

        print()
        print(separator)
        print()

        list_meanByLevs, list_stdByLevs, list_countByLevs = [], [], []
        list_meanByLevsa, list_stdByLevsa, list_countByLevsa = [], [], []
        date = datei
        levs = sorted(list(set(levs_tmp)))
        levs_tmp.clear()
        del(levs_tmp[:])

        f = 0
        while (date <= datef):

            print(date.strftime(' Calculating for ' + "%Y-%m-%d:%H"))
            datefmt = date.strftime("%Y%m%d%H")

            try: 
                if info_check[date.strftime("%d%H")] == True:
                    dataDict = self[f].obsInfo[varName].loc[varType]
                    dataByLevs, mean_dataByLevs, std_dataByLevs, count_dataByLevs = {}, {}, {}, {}
                    dataByLevsa, mean_dataByLevsa, std_dataByLevsa, count_dataByLevsa = {}, {}, {}, {}
                    [dataByLevs.update({int(lvl): []}) for lvl in levs]
                    [dataByLevsa.update({int(lvl): []}) for lvl in levs]
                    if Level != None and Level != "Zlevs":
                        if SingleL == None:
                            [ dataByLevs[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) == Level ]
                            [ dataByLevsa[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) == Level ]
                            forplot = ' Level='+str(Level) +'hPa'
                            forplotname = 'level_'+str(Level) +'hPa'
                        else:
                            if SingleL == "All":
                                [ dataByLevs[Level].append(v) for v in self[f].obsInfo[varName].loc[varType].omf ]
                                [ dataByLevsa[Level].append(v) for v in self[f].obsInfo[varName].loc[varType].oma ]
                                forplot = ' Layer=Entire Atmosphere'
                                forplotname = 'layer_allAtm'
                            else:
                                if SingleL == "OneL":
                                    if Lay == None:
                                        print("")
                                        print(" Variable Lay is None, resetting it to its default value: "+str(Laydef)+" hPa.")
                                        print("")
                                        Lay = Laydef
                                    [ dataByLevs[int(Level)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) >=Level-Lay and int(p) <Level+Lay ]
                                    [ dataByLevsa[int(Level)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) >=Level-Lay and int(p) <Level+Lay ]
                                    forplot = ' Layer='+str(Level+Lay)+'-'+str(Level-Lay)+'hPa'
                                    forplotname = 'layer_'+str(Level+Lay)+'-'+str(Level-Lay)+'hPa'
                                else:
                                    print(" Wrong value for variable SingleL. Please, check it and rerun the script.")    
                    else:
                        if Level == None:
                            [ dataByLevs[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) ]
                            [ dataByLevsa[int(p)].append(v) for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) ]
                            forplotname = 'all_levels_byLevels'
                        else:
                            for ll in range(len(levs)):
                                lv = levs[ll]
                                if Lay == None:
                                    if ll == 0:
                                        Llayi = 0
                                    else:
                                        Llayi = (levs[ll] - levs[ll-1]) / 2.0
                                    if ll == len(levs)-1:
                                        Llayf = Llayi
                                    else:
                                        Llayf = (levs[ll+1] - levs[ll]) / 2.0
                                    cutlevs = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) >=lv-Llayi and int(p) <lv+Llayf ]
                                    cutlevsa = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) >=lv-Llayi and int(p) <lv+Llayf ]
                                    forplotname = 'all_levels_filledLayers'
                                else:
                                    cutlevs = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].omf) if int(p) >=lv-Lay and int(p) <lv+Lay ]
                                    cutlevsa = [ v for p,v in zip(self[f].obsInfo[varName].loc[varType].prs,self[f].obsInfo[varName].loc[varType].oma) if int(p) >=lv-Lay and int(p) <lv+Lay ]
                                    forplotname = 'all_levels_bylayers_'+str(Lay)+"hPa"
                                [ dataByLevs[lv].append(il) for il in cutlevs ]
                                [ dataByLevsa[lv].append(il) for il in cutlevsa ]
                    f = f + 1
                for lv in levs:
                    if len(dataByLevs[lv]) != 0 and info_check[date.strftime("%d%H")] == True:
                        mean_dataByLevs.update({int(lv): np.mean(np.array(dataByLevs[lv]))})
                        std_dataByLevs.update({int(lv): np.std(np.array(dataByLevs[lv]))})
                        count_dataByLevs.update({int(lv): len(np.array(dataByLevs[lv]))})
                        mean_dataByLevsa.update({int(lv): np.mean(np.array(dataByLevsa[lv]))})
                        std_dataByLevsa.update({int(lv): np.std(np.array(dataByLevsa[lv]))})
                        count_dataByLevsa.update({int(lv): len(np.array(dataByLevsa[lv]))})
                    else:
                        mean_dataByLevs.update({int(lv): -99})
                        std_dataByLevs.update({int(lv): -99})
                        count_dataByLevs.update({int(lv): -99})
                        mean_dataByLevsa.update({int(lv): -99})
                        std_dataByLevsa.update({int(lv): -99})
                        count_dataByLevsa.update({int(lv): -99})
            
            except:
                if info_check[date.strftime("%d%H")] == True:
                    print("ERROR in time_series function.")
                else:
                    print(setcolor.WARNING + "    >>> No information on this date (" + str(date.strftime("%Y-%m-%d:%H")) +") <<< " + setcolor.ENDC)

                for lv in levs:
                    mean_dataByLevs.update({int(lv): -99})
                    std_dataByLevs.update({int(lv): -99})
                    count_dataByLevs.update({int(lv): -99})
                    mean_dataByLevsa.update({int(lv): -99})
                    std_dataByLevsa.update({int(lv): -99})
                    count_dataByLevsa.update({int(lv): -99})

            if Level == None or Level == "Zlevs":
                list_meanByLevs.append(list(mean_dataByLevs.values()))
                list_stdByLevs.append(list(std_dataByLevs.values()))
                list_countByLevs.append(list(count_dataByLevs.values()))
                list_meanByLevsa.append(list(mean_dataByLevsa.values()))
                list_stdByLevsa.append(list(std_dataByLevsa.values()))
                list_countByLevsa.append(list(count_dataByLevsa.values()))
            else:
                list_meanByLevs.append(mean_dataByLevs[int(Level)])
                list_stdByLevs.append(std_dataByLevs[int(Level)])
                list_countByLevs.append(count_dataByLevs[int(Level)])
                list_meanByLevsa.append(mean_dataByLevsa[int(Level)])
                list_stdByLevsa.append(std_dataByLevsa[int(Level)])
                list_countByLevsa.append(count_dataByLevsa[int(Level)])

            dataByLevs.clear()
            mean_dataByLevs.clear()
            std_dataByLevs.clear()
            count_dataByLevs.clear()
            dataByLevsa.clear()
            mean_dataByLevsa.clear()
            std_dataByLevsa.clear()
            count_dataByLevsa.clear()

            date_finale = date
            date = date + timedelta(hours=int(delta))

        print()
        print(separator)
        print()

        print(' Making Graphics...')

        y_axis      = np.arange(0, len(zlevs), 1)
        x_axis      = np.arange(0, len(DayHour), 1)

        mean_final  = np.ma.masked_array(np.array(list_meanByLevs), np.array(list_meanByLevs) == -99)
        std_final   = np.ma.masked_array(np.array(list_stdByLevs), np.array(list_stdByLevs) == -99)
        count_final = np.ma.masked_array(np.array(list_countByLevs), np.array(list_countByLevs) == -99)
        mean_finala  = np.ma.masked_array(np.array(list_meanByLevsa), np.array(list_meanByLevsa) == -99)
        std_finala   = np.ma.masked_array(np.array(list_stdByLevsa), np.array(list_stdByLevsa) == -99)
        count_finala = np.ma.masked_array(np.array(list_countByLevsa), np.array(list_countByLevsa) == -99)

        mean_limit = np.max(np.array([np.abs(np.min(mean_final)), np.abs(np.min(mean_final))]))

        OMF_inf = np.array(list_meanByLevs)-np.array(list_stdByLevs)
        OMF_sup = np.array(list_meanByLevs)+np.array(list_stdByLevs)
        OMA_inf = np.array(list_meanByLevsa)-np.array(list_stdByLevsa)
        OMA_sup = np.array(list_meanByLevsa)+np.array(list_stdByLevsa)

        if (vminOMA == None) and (vmaxOMA == None): vminOMA, vmaxOMA = -1*mean_limit, mean_limit

        date_title = str(datei.strftime("%d%b")) + '-' + str(date_finale.strftime("%d%b")) + ' ' + str(date_finale.strftime("%Y"))
        instrument_title = str(varName) + '-' + str(varType) + '  |  ' + getVarInfo(varType, varName, 'instrument')

        # Figure with more than one level - default levels: [600, 700, 800, 900, 1000]
        if Level == None or Level == "Zlevs":
            fig = plt.figure(figsize=(6, 9))
            plt.rcParams['axes.facecolor'] = 'None'
            plt.rcParams['hatch.linewidth'] = 0.3

            ##### OMF

            plt.subplot(3, 1, 1)
            ax = plt.gca()
            ax.add_patch(mpl.patches.Rectangle((-1,-1),(len(DayHour)+1),(len(levs)+3), hatch='xxxxx', color='black', fill=False, snap=False, zorder=0))
            plt.imshow(np.flipud(mean_final.T), origin='lower', vmin=vminOMA, vmax=vmaxOMA, cmap='seismic', aspect='auto', zorder=1,interpolation='none')
            plt.colorbar(orientation='horizontal', pad=0.18, shrink=1.0)
            plt.tight_layout()
            plt.title(instrument_title, loc='left', fontsize=10)
            plt.title(date_title, loc='right', fontsize=10)
            plt.ylabel('Vertical Levels (hPa)')
            plt.xlabel('Mean ('+omflag+')')
            plt.yticks(y_axis, zlevs[::-1])
            plt.xticks(x_axis, DayHour)

            plt.subplot(3, 1, 2)
            ax = plt.gca()
            ax.add_patch(mpl.patches.Rectangle((-1,-1),(len(DayHour)+1),(len(levs)+3), hatch='xxxxx', color='black', fill=False, snap=False, zorder=0))
            plt.imshow(np.flipud(std_final.T), origin='lower', vmin=vminSTD, vmax=vmaxSTD, cmap='Blues', aspect='auto', zorder=1,interpolation='none')
            plt.colorbar(orientation='horizontal', pad=0.18, shrink=1.0)
            plt.tight_layout()
            plt.title(instrument_title, loc='left', fontsize=10)
            plt.title(date_title, loc='right', fontsize=10)
            plt.ylabel('Vertical Levels (hPa)')
            plt.xlabel('Standard Deviation ('+omflag+')')
            plt.yticks(y_axis, zlevs[::-1])
            plt.xticks(x_axis, DayHour)

            plt.subplot(3, 1, 3)
            ax = plt.gca()
            ax.add_patch(mpl.patches.Rectangle((-1,-1),(len(DayHour)+1),(len(levs)+3), hatch='xxxxx', color='black', fill=False, snap=False, zorder=0))
            plt.imshow(np.flipud(count_final.T), origin='lower', vmin=0.0, vmax=np.max(count_final), cmap='gist_heat_r', aspect='auto', zorder=1,interpolation='none')
            plt.colorbar(orientation='horizontal', pad=0.18, shrink=1.0)
            plt.title(instrument_title, loc='left', fontsize=10)
            plt.title(date_title, loc='right', fontsize=10)
            plt.ylabel('Vertical Levels (hPa)')
            plt.xlabel('Total Observations')
            plt.yticks(y_axis, zlevs[::-1])
            plt.xticks(x_axis, DayHour)
            plt.tight_layout()
            plt.savefig('time_series_'+str(varName) + '-' + str(varType)+'_'+omflag+'_'+forplotname+'.png', bbox_inches='tight', dpi=100)
            if Clean:
                plt.clf()

            ##### OMA

            fig = plt.figure(figsize=(6, 9))
            plt.rcParams['axes.facecolor'] = 'None'
            plt.rcParams['hatch.linewidth'] = 0.3

            plt.subplot(3, 1, 1)
            ax = plt.gca()
            ax.add_patch(mpl.patches.Rectangle((-1,-1),(len(DayHour)+1),(len(levs)+3), hatch='xxxxx', color='black', fill=False, snap=False, zorder=0))
            plt.imshow(np.flipud(mean_finala.T), origin='lower', vmin=vminOMA, vmax=vmaxOMA, cmap='seismic', aspect='auto', zorder=1,interpolation='none')
            plt.colorbar(orientation='horizontal', pad=0.18, shrink=1.0)
            plt.tight_layout()
            plt.title(instrument_title, loc='left', fontsize=10)
            plt.title(date_title, loc='right', fontsize=10)
            plt.ylabel('Vertical Levels (hPa)')
            plt.xlabel('Mean ('+omflaga+')')
            plt.yticks(y_axis, zlevs[::-1])
            plt.xticks(x_axis, DayHour)

            plt.subplot(3, 1, 2)
            ax = plt.gca()
            ax.add_patch(mpl.patches.Rectangle((-1,-1),(len(DayHour)+1),(len(levs)+3), hatch='xxxxx', color='black', fill=False, snap=False, zorder=0))
            plt.imshow(np.flipud(std_finala.T), origin='lower', vmin=vminSTD, vmax=vmaxSTD, cmap='Blues', aspect='auto', zorder=1,interpolation='none')
            plt.colorbar(orientation='horizontal', pad=0.18, shrink=1.0)
            plt.tight_layout()
            plt.title(instrument_title, loc='left', fontsize=10)
            plt.title(date_title, loc='right', fontsize=10)
            plt.ylabel('Vertical Levels (hPa)')
            plt.xlabel('Standard Deviation ('+omflaga+')')
            plt.yticks(y_axis, zlevs[::-1])
            plt.xticks(x_axis, DayHour)

            plt.subplot(3, 1, 3)
            ax = plt.gca()
            ax.add_patch(mpl.patches.Rectangle((-1,-1),(len(DayHour)+1),(len(levs)+3), hatch='xxxxx', color='black', fill=False, snap=False, zorder=0))
            plt.imshow(np.flipud(count_finala.T), origin='lower', vmin=0.0, vmax=np.max(count_finala), cmap='gist_heat_r', aspect='auto', zorder=1,interpolation='none')
            plt.colorbar(orientation='horizontal', pad=0.18, shrink=1.0)
            plt.title(instrument_title, loc='left', fontsize=10)
            plt.title(date_title, loc='right', fontsize=10)
            plt.ylabel('Vertical Levels (hPa)')
            plt.xlabel('Total Observations')
            plt.yticks(y_axis, zlevs[::-1])
            plt.xticks(x_axis, DayHour)
            plt.tight_layout()
            plt.savefig('time_series_'+str(varName) + '-' + str(varType)+'_'+omflaga+'_'+forplotname+'.png', bbox_inches='tight', dpi=100)
            if Clean:
                plt.clf()

        # Figure with only one level
        else:
        
            ##### OMF

            fig = plt.figure(figsize=(6, 4))
            fig, ax1 = plt.subplots(1, 1)
            plt.style.use('seaborn-ticks')

            plt.axhline(y=0.0,ls='solid',c='#d3d3d3')
            plt.annotate(forplot, xy=(0.0, 0.965), xytext=(0,0), xycoords='axes fraction', textcoords='offset points', color='lightgray', fontweight='bold', fontsize='12',
            horizontalalignment='left', verticalalignment='center')

            ax1.plot(x_axis, list_meanByLevs, "b-", label="Mean ("+omflag+")")
            ax1.plot(x_axis, list_meanByLevs, "bo", label="Mean ("+omflag+")")
            ax1.set_xlabel('Date (DayHour)', fontsize=10)
            # Make the y-axis label, ticks and tick labels match the line color.
            ax1.set_ylim(vminOMA, vmaxOMA)
            ax1.set_ylabel('Mean ('+omflag+')', color='b', fontsize=10)
            ax1.tick_params('y', colors='b')
            plt.xticks(x_axis, DayHour)
            plt.axhline(y=np.mean(list_meanByLevs),ls='dotted',c='blue')
            
            ax2 = ax1.twinx()
            ax2.plot(x_axis, std_final, "r-", label="Std. Deviation ("+omflag+")")
            ax2.plot(x_axis, std_final, "rs", label="Std. Deviation ("+omflag+")")
            ax2.set_ylim(vminSTD, vmaxSTD)
            ax2.set_ylabel('Std. Deviation ('+omflag+')', color='r', fontsize=10)
            ax2.tick_params('y', colors='r')
            plt.axhline(y=np.mean(std_final),ls='dotted',c='red')

            ax3 = ax1.twinx()
            ax3.plot(x_axis, count_final, "g-", label="Total Observations")
            ax3.plot(x_axis, count_final, "g^", label="Total Observations")
            ax3.set_ylim(0, np.max(count_final) + (np.max(count_final)/8))
            ax3.set_ylabel('Total Observations', color='g', fontsize=10)
            ax3.tick_params('y', colors='g')
            ax3.spines["right"].set_position(("axes", 1.15))
            plt.yticks(rotation=90)
            plt.axhline(y=np.mean(count_final),ls='dotted',c='green')

            ax3.set_title(instrument_title, loc='left', fontsize=10)
            ax3.set_title(date_title, loc='right', fontsize=10)

            plt.xticks(x_axis, DayHour)
            plt.title(instrument_title, loc='left', fontsize=9)
            plt.title(date_title, loc='right', fontsize=9)
            plt.subplots_adjust(left=None, bottom=None, right=0.80, top=None)
            plt.tight_layout()
            plt.savefig('time_series_'+str(varName) + '-' + str(varType)+'_'+omflag+'_'+forplotname+'.png', bbox_inches='tight', dpi=100)
            if Clean:
                plt.clf()

            ##### OMA

            fig = plt.figure(figsize=(6, 4))
            fig, ax1 = plt.subplots(1, 1)
            plt.style.use('seaborn-ticks')

            plt.axhline(y=0.0,ls='solid',c='#d3d3d3')
            plt.annotate(forplot, xy=(0.0, 0.965), xytext=(0, 0), xycoords='axes fraction', textcoords='offset points', color='lightgray', fontweight='bold', fontsize='12',
            horizontalalignment='left', verticalalignment='center')

            ax1.plot(x_axis, list_meanByLevsa, "b-", label="Mean ("+omflaga+")")
            ax1.plot(x_axis, list_meanByLevsa, "bo", label="Mean ("+omflaga+")")
            ax1.set_xlabel('Date (DayHour)', fontsize=10)
            # Make the y-axis label, ticks and tick labels match the line color.
            ax1.set_ylim(vminOMA, vmaxOMA)
            ax1.set_ylabel('Mean ('+omflaga+')', color='b', fontsize=10)
            ax1.tick_params('y', colors='b')
            plt.xticks(x_axis, DayHour)
            plt.axhline(y=np.mean(list_meanByLevsa),ls='dotted',c='blue')
            
            ax2 = ax1.twinx()
            ax2.plot(x_axis, std_finala, "r-", label="Std. Deviation ("+omflaga+")")
            ax2.plot(x_axis, std_finala, "rs", label="Std. Deviation ("+omflaga+")")
            ax2.set_ylim(vminSTD, vmaxSTD)
            ax2.set_ylabel('Std. Deviation ('+omflaga+')', color='r', fontsize=10)
            ax2.tick_params('y', colors='r')
            plt.axhline(y=np.mean(std_finala),ls='dotted',c='red')

            ax3 = ax1.twinx()
            ax3.plot(x_axis, count_finala, "g-", label="Total Observations")
            ax3.plot(x_axis, count_finala, "g^", label="Total Observations")
            ax3.set_ylim(0, np.max(count_finala) + (np.max(count_finala)/8))
            ax3.set_ylabel('Total Observations', color='g', fontsize=10)
            ax3.tick_params('y', colors='g')
            ax3.spines["right"].set_position(("axes", 1.15))
            plt.yticks(rotation=90)
            plt.axhline(y=np.mean(count_finala),ls='dotted',c='green')

            ax3.set_title(instrument_title, loc='left', fontsize=10)
            ax3.set_title(date_title, loc='right', fontsize=10)

            plt.xticks(x_axis, DayHour)
            plt.title(instrument_title, loc='left', fontsize=9)
            plt.title(date_title, loc='right', fontsize=9)
            plt.subplots_adjust(left=None, bottom=None, right=0.80, top=None)
            plt.tight_layout()
            plt.savefig('time_series_'+str(varName) + '-' + str(varType)+'_'+omflaga+'_'+forplotname+'.png', bbox_inches='tight', dpi=100)
            if Clean:
                plt.clf()

            ##### OMF and OMA

            fig = plt.figure(figsize=(6, 4))
            fig, ax1 = plt.subplots(1, 1)
            plt.style.use('seaborn-ticks')

            plt.annotate(forplot, xy=(0.0, 0.965), xytext=(0, 0), xycoords='axes fraction', textcoords='offset points', color='lightgray', fontweight='bold', fontsize='12',
            horizontalalignment='left', verticalalignment='center')

            plt.axhline(y=0.0,ls='solid',c='#d3d3d3')
            ax1.plot(x_axis, list_meanByLevs, "b-", label="Mean ("+omflag+")")
            ax1.plot(x_axis, list_meanByLevs, "bo", label="")
            ax1.set_xlabel('Date (DayHour)', fontsize=10)
            # Make the y-axis label, ticks and tick labels match the line color.
            ax1.set_ylim(vminOMA, vmaxOMA)
            ax1.tick_params('y', colors='b')
            plt.xticks(x_axis, DayHour)
            plt.axhline(y=np.mean(list_meanByLevs),ls='dotted',c='blue')
            
            ax1.plot(x_axis, list_meanByLevsa, "r-", label="Mean ("+omflaga+")")
            ax1.plot(x_axis, list_meanByLevsa, "rs", label="")
            ax1.set_ylim(vminOMA, vmaxOMA)
            ax1.tick_params('y', colors='black')
            plt.axhline(y=np.mean(list_meanByLevsa),ls='dotted',c='red')

            plt.xticks(x_axis, DayHour)
            plt.title(instrument_title, loc='left', fontsize=9)
            plt.title(date_title, loc='right', fontsize=9)
            plt.subplots_adjust(left=None, bottom=None, right=0.80, top=None)

            ybox1 = TextArea('Mean ('+omflag+')' , textprops=dict(color="b", size=12,rotation=90,ha='left',va='bottom'))
            ybox2 = TextArea(' and '             , textprops=dict(color="k", size=12,rotation=90,ha='left',va='bottom'))
            ybox3 = TextArea('Mean ('+omflaga+')', textprops=dict(color="r", size=12,rotation=90,ha='left',va='bottom'))

            ybox = VPacker(children=[ybox3, ybox2, ybox1],align="bottom", pad=0, sep=5)

            anchored_ybox = AnchoredOffsetbox(loc=3, child=ybox, pad=0., frameon=False, bbox_to_anchor=(-0.12, 0.16), 
                                                bbox_transform=ax1.transAxes, borderpad=0.)

            ax1.add_artist(anchored_ybox)
            plt.legend()

            plt.tight_layout()
            plt.savefig('time_series_'+str(varName) + '-' + str(varType)+'_OmFOmA_'+ forplotname +'.png', bbox_inches='tight', dpi=100)

            # OMF and OMA and StdDev

            fig = plt.figure(figsize=(6, 4))
            fig, ax1 = plt.subplots(1, 1)
            plt.style.use('seaborn-ticks')
            
            ax1.plot(x_axis, list_meanByLevs, lw=2, label='OmF Mean', color='blue', zorder=2)
            ax1.fill_between(x_axis, OMF_inf, OMF_sup, label='OmF Std Dev',  facecolor='blue', alpha=0.3, zorder=2)
            ax1.plot(x_axis, list_meanByLevsa, lw=2, label='OmA Mean', color='red', zorder=1)
            ax1.fill_between(x_axis, OMA_inf, OMA_sup, label='OmA Std Dev',  facecolor='red', alpha=0.3, zorder=1)
            ybox1 = TextArea(' OmF ' , textprops=dict(color="b", size=12,rotation=90,ha='left',va='bottom'))
            ybox2 = TextArea(' | '             , textprops=dict(color="k", size=12,rotation=90,ha='left',va='bottom'))
            ybox3 = TextArea(' OmA ', textprops=dict(color="r", size=12,rotation=90,ha='left',va='bottom'))

            ybox = VPacker(children=[ybox3, ybox2, ybox1],align="bottom", pad=0, sep=5)

            anchored_ybox = AnchoredOffsetbox(loc=3, child=ybox, pad=0., frameon=False, bbox_to_anchor=(-0.125, 0.42), 
                                                bbox_transform=ax1.transAxes, borderpad=0.)

            ax1.add_artist(anchored_ybox)
            ax1.set_xlabel('Date (DayHour)', fontsize=12)
            ax1.set_ylim(-20,20)
            ax1.legend(bbox_to_anchor=(-0.11, -0.25),ncol=4,loc='lower left', fancybox=True, shadow=False, frameon=True, framealpha=1.0, fontsize='11', facecolor='white', edgecolor='lightgray')
            plt.grid(axis='y', color='lightgray', linestyle='-.', linewidth=0.5, zorder=0)

            ax2 = ax1.twinx()
            ax2.plot(x_axis, list_countByLevsa, lw=2, label='OmA', linestyle='--', color='darkgray', zorder=3)
            ax2.plot(x_axis, list_countByLevs, lw=2, label='OmF', linestyle=':', color='lightgray', zorder=3)
            ax2.set_ylabel('Total Observations (OmF | OmA)', fontsize=12)
            ax2.set_ylim(0, (np.max(list_countByLevsa) + np.max(list_countByLevsa)/5))
            ax2.legend(loc='upper left', ncol=2, fancybox=True, shadow=False, frameon=True, framealpha=1.0, fontsize='11', facecolor='white', edgecolor='lightgray')
            
            plt.xticks(x_axis, DayHour)
            plt.title(instrument_title, loc='left', fontsize=12)
            plt.title(date_title, loc='right', fontsize=12)
        
            t = plt.annotate(forplot, xy=(0.78, 0.995), xytext=(-9, -9), xycoords='axes fraction', textcoords='offset points', color='darkgray', fontweight='bold', fontsize='10',
                                horizontalalignment='center', verticalalignment='center')
            t.set_bbox(dict(facecolor='whitesmoke', alpha=1.0, edgecolor='whitesmoke', boxstyle="square,pad=0.3"))

            plt.tight_layout()
            plt.savefig('time_series_'+str(varName) + '-' + str(varType)+'_OmFOmA_StdDev_'+ forplotname +'.png', bbox_inches='tight', dpi=100)

        # Cleaning up
        if Clean:
            plt.close('all')

        print(' Done!')
        print()
        
               

        return

    
#EOC
#-----------------------------------------------------------------------------#

