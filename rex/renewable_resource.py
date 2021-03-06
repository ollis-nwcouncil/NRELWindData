# -*- coding: utf-8 -*-
"""
Classes to handle renewable resource data
"""
import numpy as np
import pandas as pd
import warnings

from rex.resource import Resource, MultiFileResource
from rex.sam_resource import SAMResource
from rex.utilities.exceptions import (ResourceValueError, ExtrapolationWarning,
                                      ResourceWarning,
                                      MoninObukhovExtrapolationError)


class SolarResource(Resource):
    """
    Class to handle Solar Resource .h5 files

    See Also
    --------
    resource.Resource : Parent class
    """
    def _get_SAM_df(self, ds_name, site):
        """
        Get SAM wind resource DataFrame for given site

        Parameters
        ----------
        ds_name : str
            'Dataset' name == SAM
        site : int
            Site to extract SAM DataFrame for

        Returns
        -------
        res_df : pandas.DataFrame
            time-series DataFrame of resource variables needed to run SAM
        """
        if not self._unscale:
            raise ResourceValueError("SAM requires unscaled values")

        res_df = pd.DataFrame(index=self.time_index)
        res_df.index.name = 'time_index'
        res_df.name = "{}-{}".format(ds_name, site)
        for var in ['dni', 'dhi', 'wind_speed', 'air_temperature']:
            ds_slice = (slice(None), site)
            var_array = self._get_ds(var, ds_slice)
            res_df[var] = SAMResource.check_units(var, var_array, tech='pv')

        return res_df

    def _preload_SAM(self, sites, tech='pv', clearsky=False, means=False):
        """
        Pre-load project_points for SAM

        Parameters
        ----------
        sites : list
            List of sites to be provided to SAM
        tech : str, optional
            Technology to be run by SAM, by default 'pv'
        clearsky : bool
            Boolean flag to pull clearsky instead of real irradiance
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        SAM_res = SAMResource(sites, tech, self.time_index, means=means)
        sites = SAM_res.sites_slice
        SAM_res['meta'] = self['meta', sites]
        for var in SAM_res.var_list:
            ds = var
            if clearsky and var in ['dni', 'dhi']:
                ds = 'clearsky_{}'.format(var)

            SAM_res[var] = self[ds, :, sites]

        return SAM_res

    @classmethod
    def preload_SAM(cls, h5_file, sites, unscale=True, hsds=False,
                    str_decode=True, group=None, tech='pv', clearsky=False,
                    means=False):
        """
        Pre-load project_points for SAM

        Parameters
        ----------
        h5_file : str
            h5_file to extract resource from
        sites : list
            List of sites to be provided to SAM
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        hsds : bool
            Boolean flag to use h5pyd to handle .h5 'files' hosted on AWS
            behind HSDS
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        group : str
            Group within .h5 resource file to open
        tech : str, optional
            Technology to be run by SAM, by default 'pv'
        clearsky : bool
            Boolean flag to pull clearsky instead of real irradiance
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        kwargs = {"unscale": unscale, "hsds": hsds,
                  "str_decode": str_decode, "group": group}
        with cls(h5_file, **kwargs) as res:
            SAM_res = res._preload_SAM(sites, tech=tech, clearsky=clearsky,
                                       means=means)

        return SAM_res


class NSRDB(SolarResource):
    """
    Class to handle NSRDB .h5 files

    See Also
    --------
    resource.Resource : Parent class
    """
    ADD_ATTR = 'psm_add_offset'
    SCALE_ATTR = 'psm_scale_factor'
    UNIT_ATTR = 'psm_units'

    def _preload_SAM(self, sites, tech='pv', clearsky=False, downscale=None,
                     means=False):
        """
        Pre-load project_points for SAM

        Parameters
        ----------
        sites : list
            List of sites to be provided to SAM
        tech : str, optional
            Technology to be run by SAM, by default 'pv'
        clearsky : bool
            Boolean flag to pull clearsky instead of real irradiance
        downscale : NoneType | str
            Option for NSRDB resource downscaling to higher temporal
            resolution. Expects a string in the Pandas frequency format,
            e.g. '5min'.
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        SAM_res = SAMResource(sites, tech, self.time_index, means=means)
        sites = SAM_res.sites_slice
        SAM_res['meta'] = self['meta', sites]

        if clearsky:
            SAM_res.set_clearsky()

        if not downscale:
            for var in SAM_res.var_list:
                SAM_res[var] = self[var, :, sites]
        else:
            # contingent import to avoid dependencies
            from rex.utilities.downscale import downscale_nsrdb
            SAM_res = downscale_nsrdb(SAM_res, self, downscale,
                                      sam_vars=SAM_res.var_list)

        return SAM_res

    @classmethod
    def preload_SAM(cls, h5_file, sites, unscale=True, hsds=False,
                    str_decode=True, group=None, tech='pv', clearsky=False,
                    downscale=None, means=False):
        """
        Pre-load project_points for SAM

        Parameters
        ----------
        h5_file : str
            h5_file to extract resource from
        sites : list
            List of sites to be provided to SAM
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        hsds : bool
            Boolean flag to use h5pyd to handle .h5 'files' hosted on AWS
            behind HSDS
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        group : str
            Group within .h5 resource file to open
        tech : str, optional
            Technology to be run by SAM, by default 'pv'
        clearsky : bool
            Boolean flag to pull clearsky instead of real irradiance
        downscale : NoneType | str
            Option for NSRDB resource downscaling to higher temporal
            resolution. Expects a string in the Pandas frequency format,
            e.g. '5min'.
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        kwargs = {"unscale": unscale, "hsds": hsds,
                  "str_decode": str_decode, "group": group}
        with cls(h5_file, **kwargs) as res:
            SAM_res = res._preload_SAM(sites, tech=tech, clearsky=clearsky,
                                       downscale=downscale, means=means)

        return SAM_res


class WindResource(Resource):
    """
    Class to handle Wind Resource .h5 files

    See Also
    --------
    resource.Resource : Parent class

    Examples
    --------
    >>> file = '$TESTDATADIR/wtk/ri_100_wtk_2012.h5'
    >>> with WindResource(file) as res:
    >>>     print(res.datasets)
    ['meta', 'pressure_0m', 'pressure_100m', 'pressure_200m',
    'temperature_100m', 'temperature_80m', 'time_index', 'winddirection_100m',
    'winddirection_80m', 'windspeed_100m', 'windspeed_80m']

    WindResource can interpolate between available hub-heights (80 & 100)

    >>> with WindResource(file) as res:
    >>>     wspd_90m = res['windspeed_90m']
    >>>
    >>> wspd_90m
    [[ 6.865      6.77       6.565     ...  8.65       8.62       8.415    ]
     [ 7.56       7.245      7.685     ...  5.9649997  5.8        6.2      ]
     [ 9.775      9.21       9.225     ...  7.12       7.495      7.675    ]
      ...
     [ 8.38       8.440001   8.85      ... 11.934999  12.139999  12.4      ]
     [ 9.900001   9.895      9.93      ... 12.825     12.86      12.965    ]
     [ 9.895     10.01      10.305     ... 14.71      14.79      14.764999 ]]

    WindResource can also extrapolate beyond available hub-heights

    >>> with WindResource(file) as res:
    >>>     wspd_150m = res['windspeed_150m']
    >>>
    >>> wspd_150m
    ExtrapolationWarning: 150 is outside the height range (80, 100).
    Extrapolation to be used.
    [[ 7.336291   7.2570405  7.0532546 ...  9.736436   9.713792   9.487364 ]
     [ 8.038219   7.687255   8.208041  ...  6.6909685  6.362647   6.668326 ]
     [10.5515785  9.804363   9.770399  ...  8.026898   8.468434   8.67222  ]
     ...
     [ 9.079792   9.170363   9.634542  ... 13.472508  13.7102585 14.004617 ]
     [10.710078  10.710078  10.698757  ... 14.468795  14.514081  14.6386175]
     [10.698757  10.857258  11.174257  ... 16.585903  16.676476  16.653833 ]]
    """

    def __init__(self, h5_file, unscale=True, hsds=False, str_decode=True,
                 group=None):
        """
        Parameters
        ----------
        h5_file : str
            Path to .h5 resource file
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        hsds : bool
            Boolean flag to use h5pyd to handle .h5 'files' hosted on AWS
            behind HSDS
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        group : str
            Group within .h5 resource file to open
        """
        self._heights = None
        super().__init__(h5_file, unscale=unscale, hsds=hsds,
                         str_decode=str_decode, group=group)

    @staticmethod
    def _parse_hub_height(name):
        """
        Extract hub height from given string

        Parameters
        ----------
        name : str
            String to parse hub height from

        Returns
        -------
        h : int | float
            Hub Height as a numeric value
        """
        h = name.strip('m')
        try:
            h = int(h)
        except ValueError:
            h = float(h)

        return h

    @staticmethod
    def _parse_name(ds_name):
        """
        Extract dataset name and height from dataset name

        Parameters
        ----------
        ds_name : str
            Dataset name

        Returns
        -------
        name : str
            Variable name
        h : int | float
            Height of variable
        """
        try:
            if ds_name.endswith('m'):
                name, h = ds_name.split('_')
                h = WindResource._parse_hub_height(h)
            else:
                raise ValueError('{} does not end with "_hm"'
                                 .format(ds_name))
        except Exception as ex:
            name = ds_name
            h = None
            msg = ('Could not extract hub-height from {}:\n{}'
                   .format(ds_name, ex))
            warnings.warn(msg)

        return name, h

    @property
    def heights(self):
        """
        Extract available heights for pressure, temperature, windspeed, precip,
        and winddirection variables. Used for interpolation/extrapolation.

        Returns
        -------
        self._heights : list
            List of available heights for:
            windspeed, winddirection, temperature, and pressure
        """
        if self._heights is None:
            heights = {'pressure': [],
                       'temperature': [],
                       'windspeed': [],
                       'winddirection': [],
                       'precipitationrate': [],
                       'relativehumidity': []}

            ignore = ['meta', 'time_index', 'coordinates']
            for ds in self.datasets:
                if ds not in ignore:
                    ds_name, h = self._parse_name(ds)
                    if ds_name in heights.keys():
                        heights[ds_name].append(h)

            self._heights = heights

        return self._heights

    @staticmethod
    def get_nearest_h(h, heights):
        """
        Get two nearest h values in heights.
        Determine if h is inside or outside the range of heights
        (requiring extrapolation instead of interpolation)

        Parameters
        ----------
        h : int | float
            Height value of interest
        heights : list
            List of available heights

        Returns
        -------
        nearest_h : list
            list of 1st and 2nd nearest height in heights
        extrapolate : bool
            Flag as to whether h is inside or outside heights range
        """

        heights_arr = np.array(heights, dtype='float32')
        dist = np.abs(heights_arr - h)
        pos = dist.argsort()[:2]
        nearest_h = sorted([heights[p] for p in pos])
        extrapolate = np.all(h < heights_arr) or np.all(h > heights_arr)

        if extrapolate:
            h_min, h_max = np.sort(heights)[[0, -1]]
            msg = ('{} is outside the height range'.format(h),
                   '({}, {}).'.format(h_min, h_max),
                   'Extrapolation to be used.')
            warnings.warn(' '.join(msg), ExtrapolationWarning)

        return nearest_h, extrapolate

    @staticmethod
    def monin_obukhov_extrapolation(ts_1, h_1, z0, L, h):
        """
        Monin-Obukhov extrapolation

        Parameters
        ----------
         ts_1 : ndarray
            Time-series array at height h_1
        h_1 : int | float
            Height corresponding to time-seris ts_1
        z0: int | float | ndarray
            Roughness length
        L : ndarray
            time-series of Obukhov length (m; measure of stability)
        h : int | float
            Desired height

        Returns
        -------
        ndarray
            new wind speed from MO extrapolation.
        """
        # Non dimensional stability parameter at h
        zeta = WindResource.stability_function(h / L)
        # Non dimensional stability parameter at z0
        zeta_0 = WindResource.stability_function(z0 / L)
        # Non dimensional stability parameter at h_1
        zeta_1 = WindResource.stability_function(h_1 / L)

        # Logarithmic extrapolation equation
        out = (ts_1 * (np.log(h / z0) - zeta + zeta_0)
               / (np.log(h_1 / z0) - zeta_1 + zeta_0))

        return out

    @staticmethod
    def stability_function(zeta):
        """
        Calculate stability function depending on sign of L
        (negative is unstable, positive is stable)

        Parameters
        ----------
        zeta : ndarray
            Normalized length

        Returns
        -------
        numpy.ndarray
            stability measurements.
        """
        stab_fun = np.zeros(len(zeta))
        zeta = zeta.astype(float)

        # Unstable conditions
        x = (np.power(1 - 16 * zeta[zeta < 0], 0.25))
        paulson_func = (np.pi / 2 - 2 * np.arctan(x)
                        + np.log(np.power(1 + x, 2)
                        * (1 + np.power(x, 2)) / 8))

        y = np.power(1 - 10 * zeta[zeta < 0], 1. / 3)
        conv_func = (3 / 2 * np.log(np.power(y, 2) + y + 1. / 3) - np.sqrt(3)
                     * np.arctan(2 * y + 1 / np.sqrt(3)) + np.pi / np.sqrt(3))

        o = ((paulson_func + np.power(zeta[zeta < 0], 2) * conv_func)
             / (1 + np.power(zeta[zeta < 0], 2)))

        stab_fun[np.where(zeta < 0)] = o

        # Stable conditions
        a = 6.1
        b = 2.5

        o = np.log(zeta[zeta >= 0]
                   + (1 + np.power(zeta[zeta >= 0], b))**(1 / b))
        o *= -a
        stab_fun[np.where(zeta >= 0)] = o

        return stab_fun

    @staticmethod
    def power_law_interp(ts_1, h_1, ts_2, h_2, h, mean=True):
        """
        Power-law interpolate/extrapolate time-series data to height h

        Parameters
        ----------
        ts_1 : ndarray
            Time-series array at height h_1
        h_1 : int | float
            Height corresponding to time-seris ts_1
        ts_2 : ndarray
            Time-series array at height h_2
        h_2 : int | float
            Height corresponding to time-seris ts_2
        h : int | float
            Height of desired time-series
        mean : bool
            Calculate average alpha versus point by point alpha

        Returns
        -------
        out : ndarray
            Time-series array at height h
        """
        if h_1 > h_2:
            h_1, h_2 = h_2, h_1
            ts_1, ts_2 = ts_2, ts_1

        if mean:
            alpha = (np.log(ts_2.mean() / ts_1.mean())
                     / np.log(h_2 / h_1))

            if alpha < 0.06:
                warnings.warn('Alpha is < 0.06', RuntimeWarning)
            elif alpha > 0.6:
                warnings.warn('Alpha is > 0.6', RuntimeWarning)
        else:
            # Replace zero values for alpha calculation
            ts_1[ts_1 == 0] = 0.001
            ts_2[ts_2 == 0] = 0.001

            alpha = np.log(ts_2 / ts_1) / np.log(h_2 / h_1)
            # The Hellmann exponent varies from 0.06 to 0.6
            alpha[alpha < 0.06] = 0.06
            alpha[alpha > 0.6] = 0.6

        out = ts_1 * (h / h_1)**alpha

        return out

    @staticmethod
    def linear_interp(ts_1, h_1, ts_2, h_2, h):
        """
        Linear interpolate/extrapolate time-series data to height h

        Parameters
        ----------
        ts_1 : ndarray
            Time-series array at height h_1
        h_1 : int | float
            Height corresponding to time-seris ts_1
        ts_2 : ndarray
            Time-series array at height h_2
        h_2 : int | float
            Height corresponding to time-seris ts_2
        h : int | float
            Height of desired time-series

        Returns
        -------
        out : ndarray
            Time-series array at height h
        """
        if h_1 > h_2:
            h_1, h_2 = h_2, h_1
            ts_1, ts_2 = ts_2, ts_1

        # Calculate slope for every posiiton in variable arrays
        m = (ts_2 - ts_1) / (h_2 - h_1)
        # Calculate intercept for every position in variable arrays
        b = ts_2 - m * h_2

        out = m * h + b

        return out

    @staticmethod
    def shortest_angle(a0, a1):
        """
        Calculate the shortest angle distance between a0 and a1

        Parameters
        ----------
        a0 : int | float
            angle 0 in degrees
        a1 : int | float
            angle 1 in degrees

        Returns
        -------
        da : int | float
            shortest angle distance between a0 and a1
        """
        da = (a1 - a0) % 360
        return 2 * da % 360 - da

    @staticmethod
    def circular_interp(ts_1, h_1, ts_2, h_2, h):
        """
        Circular interpolate/extrapolate time-series data to height h

        Parameters
        ----------
        ts_1 : ndarray
            Time-series array at height h_1
        h_1 : int | float
            Height corresponding to time-seris ts_1
        ts_2 : ndarray
            Time-series array at height h_2
        h_2 : int | float
            Height corresponding to time-seris ts_2
        h : int | float
            Height of desired time-series

        Returns
        -------
        out : ndarray
            Time-series array at height h
        """
        h_f = (h - h_1) / (h_2 - h_1)

        da = WindResource.shortest_angle(ts_1, ts_2) * h_f
        da = np.sign(da) * (np.abs(da) % 360)

        out = (ts_2 + da) % 360

        return out

    def _check_hub_height(self, h):
        """
        Check requested hub-height against available windspeed hub-heights
        If only one hub-height is available change request to match available
        hub-height

        Parameters
        ----------
        h : int | float
            Requested hub-height

        Returns
        -------
        h : int | float
            Hub-height to extract
        """
        heights = self.heights['windspeed']
        if len(heights) == 1:
            h = heights[0]
            warnings.warn('Wind speed is only available at {h}m, '
                          'all variables will be extracted at {h}m'
                          .format(h=h), ResourceWarning)

        return h

    def _try_monin_obukhov_extrapolation(self, ts_1, ds_slice, h_1, h):
        rmol = 'inversemoninobukhovlength_2m'
        if rmol not in self:
            msg = ("{} is needed to run monin obukhov extrapolation"
                   .format(rmol))
            warnings.warn(msg)
            raise MoninObukhovExtrapolationError(msg)

        if 'roughness_length' in self:
            z0 = self._get_ds('roughness_length', ds_slice)
        elif 'z0' in self.meta:
            z0 = self.meta['z0']
        else:
            msg = ("roughness length ('z0') is needed to run monin obukhov"
                   "extrapolation")
            warnings.warn(msg, ExtrapolationWarning)
            raise MoninObukhovExtrapolationError(msg)

        L = 1 / self._get_ds(rmol, ds_slice)

        out = self.monin_obukhov_extrapolation(ts_1, h_1, z0, L, h)

        return out

    def _get_ds(self, ds_name, ds_slice):
        """
        Extract data from given dataset

        Parameters
        ----------
        ds_name : str
            Variable dataset to be extracted
        ds_slice : tuple of int | list | slice
            tuple describing list ds_slice to extract

        Returns
        -------
        out : ndarray
            ndarray of variable timeseries data
            If unscale, returned in native units else in scaled units
        """
        var_name, h = self._parse_name(ds_name)
        heights = self.heights[var_name]
        if len(heights) == 1:
            h = heights[0]
            ds_name = '{}_{}m'.format(var_name, h)
            warnings.warn('Only one hub-height available, returning {}'
                          .format(ds_name), ResourceWarning)

        if h in heights:
            ds_name = '{}_{}m'.format(var_name, int(h))
            out = super()._get_ds(ds_name, ds_slice)
        else:
            (h1, h2), extrapolate = self.get_nearest_h(h, heights)
            if extrapolate:
                warnings.warn('Extrapolating {}'.format(ds_name),
                              ExtrapolationWarning)

            ts1 = super()._get_ds('{}_{}m'.format(var_name, h1), ds_slice)
            ts2 = super()._get_ds('{}_{}m'.format(var_name, h2), ds_slice)

            if (var_name == 'windspeed') and extrapolate:
                if h < h1:
                    try:
                        self._try_monin_obukhov_extrapolation(ts1, ds_slice,
                                                              h1, h)
                        warnings.warn('\t- Using Monin Obukhov Extrapolation',
                                      ExtrapolationWarning)
                    except MoninObukhovExtrapolationError:
                        out = self.power_law_interp(ts1, h1, ts2, h2, h)
                        warnings.warn('\t- Using Power Law Extrapolation',
                                      ExtrapolationWarning)
                else:
                    out = self.power_law_interp(ts1, h1, ts2, h2, h)
                    warnings.warn('\t- Using Power Law Extrapolation',
                                  ExtrapolationWarning)
            elif var_name == 'winddirection':
                out = self.circular_interp(ts1, h1, ts2, h2, h)
            else:
                out = self.linear_interp(ts1, h1, ts2, h2, h)

        return out

    def _get_SAM_df(self, ds_name, site, require_wind_dir=False,
                    icing=False):
        """
        Get SAM wind resource DataFrame for given site

        Parameters
        ----------
        ds_name : str
            'Dataset' name == SAM
        site : int
            Site to extract SAM DataFrame for
        require_wind_dir : bool
            Boolean flag as to whether wind direction will be loaded.
        icing : bool
            Boolean flag to include relativehumitidy for icing calculation

        Returns
        -------
        res_df : pandas.DataFrame
            time-series DataFrame of resource variables needed to run SAM
        """
        if not self._unscale:
            raise ResourceValueError("SAM requires unscaled values")

        _, h = self._parse_name(ds_name)
        h = self._check_hub_height(h)
        res_df = pd.DataFrame(index=self.time_index)
        res_df.index.name = 'time_index'
        res_df.name = "{}-{}".format(ds_name, site)
        variables = ['pressure', 'temperature', 'winddirection', 'windspeed']
        if not require_wind_dir:
            variables.remove('winddirection')

        if icing:
            variables.append('relativehumidity')
        for var in variables:
            var_name = "{}_{}m".format(var, h)
            ds_slice = (slice(None), site)
            var_array = self._get_ds(var_name, ds_slice)
            res_df[var_name] = SAMResource.check_units(var_name, var_array,
                                                       tech='windpower')
            res_df[var_name] = SAMResource.enforce_arr_range(
                var, res_df[var_name],
                SAMResource.WIND_DATA_RANGES[var], [site])

        return res_df

    def _preload_SAM(self, sites, hub_heights, require_wind_dir=False,
                     precip_rate=False, icing=False, means=False):
        """
        Pre-load project_points for SAM

        Parameters
        ----------
        sites : list
            List of sites to be provided to SAM
        hub_heights : int | float | list
            Hub heights to extract for SAM
        require_wind_dir : bool
            Boolean flag as to whether wind direction will be loaded.
        precip_rate : bool
            Boolean flag as to whether precipitationrate_0m will be preloaded
        icing : bool
            Boolean flag as to whether icing is analyzed.
            This will preload relative humidity.
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        SAM_res = SAMResource(sites, 'windpower', self.time_index,
                              hub_heights=hub_heights,
                              require_wind_dir=require_wind_dir,
                              means=means)
        sites = SAM_res.sites_slice
        SAM_res['meta'] = self['meta', sites]
        var_list = SAM_res.var_list
        if not require_wind_dir:
            var_list.remove('winddirection')

        h = self._check_hub_height(SAM_res.h)
        if isinstance(h, (int, float)):
            for var in var_list:
                ds_name = "{}_{}m".format(var, h)
                SAM_res[var] = self[ds_name, :, sites]
        else:
            _, unq_idx = np.unique(h, return_inverse=True)
            unq_h = sorted(list(set(h)))

            site_list = np.array(SAM_res.sites)
            height_slices = {}
            for i, h_i in enumerate(unq_h):
                pos = np.where(unq_idx == i)[0]
                height_slices[h_i] = (site_list[pos], pos)

            for var in var_list:
                for h_i, (h_pos, sam_pos) in height_slices.items():
                    ds_name = '{}_{}m'.format(var, h_i)
                    SAM_res[var, :, sam_pos] = self[ds_name, :, h_pos]

        if precip_rate:
            var = 'precipitationrate'
            ds_name = '{}_0m'.format(var)
            SAM_res.append_var_list(var)
            SAM_res[var] = self[ds_name, :, sites]

        if icing:
            var = 'rh'
            ds_name = 'relativehumidity_2m'
            SAM_res.append_var_list(var)
            SAM_res[var] = self[ds_name, :, sites]

        return SAM_res

    @classmethod
    def preload_SAM(cls, h5_file, sites, hub_heights, unscale=True,
                    hsds=False, str_decode=True, group=None,
                    require_wind_dir=False, precip_rate=False, icing=False,
                    means=False):
        """
        Placeholder for classmethod that will pre-load project_points for SAM

        Parameters
        ----------
        h5_file : str
            h5_file to extract resource from
        sites : list
            List of sites to be provided to SAM
        hub_heights : int | float | list
            Hub heights to extract for SAM
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        hsds : bool
            Boolean flag to use h5pyd to handle .h5 'files' hosted on AWS
            behind HSDS
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        group : str
            Group within .h5 resource file to open
        require_wind_dir : bool
            Boolean flag as to whether wind direction will be loaded.
        precip_rate : bool
            Boolean flag as to whether precipitationrate_0m will be preloaded
        icing : bool
            Boolean flag as to whether icing is analyzed.
            This will preload relative humidity.
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        kwargs = {"unscale": unscale, "hsds": hsds,
                  "str_decode": str_decode, "group": group}
        with cls(h5_file, **kwargs) as res:
            SAM_res = res._preload_SAM(sites, hub_heights,
                                       require_wind_dir=require_wind_dir,
                                       precip_rate=precip_rate, icing=icing,
                                       means=means)

        return SAM_res


class MultiFileNSRDB(MultiFileResource, NSRDB):
    """
    Class to handle 2018 and beyond NSRDB data that is at 2km and
    sub 30 min resolution

    See Also
    --------
    resource.MultiFileResource : Parent class
    resource.NSRDB : Parent class
    """
    @classmethod
    def preload_SAM(cls, h5_path, sites, unscale=True, str_decode=True,
                    tech='pv', clearsky=False, downscale=None, means=False):
        """
        Pre-load project_points for SAM

        Parameters
        ----------
        h5_path : str
            Path to directory containing multi-file resource file sets.
            Available formats:
                /h5_dir/
                /h5_dir/prefix*suffix
        sites : list
            List of sites to be provided to SAM
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        tech : str, optional
            Technology to be run by SAM, by default 'pv'
        clearsky : bool
            Boolean flag to pull clearsky instead of real irradiance
        downscale : NoneType | str
            Option for NSRDB resource downscaling to higher temporal
            resolution. Expects a string in the Pandas frequency format,
            e.g. '5min'.
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        with cls(h5_path, unscale=unscale, str_decode=str_decode) as res:
            SAM_res = res._preload_SAM(sites, tech=tech, clearsky=clearsky,
                                       downscale=downscale, means=means)

        return SAM_res


class MultiFileWTK(MultiFileResource, WindResource):
    """
    Class to handle 5min WIND Toolkit data

    See Also
    --------
    resource.MultiFileResource : Parent class
    resource.WindResource : Parent class

    Examples
    --------
    MultiFileWTK automatically searches for files of the form *m.h5

    >>> file = '$TESTDATADIR/wtk'
    >>> with MultiFileWTK(file) as res:
    >>>     print(list(res._h5_files)
    >>>     print(res.datasets)
    ['$TESTDATADIR/wtk_2010_200m.h5',
     '$TESTDATADIR/wtk_2010_100m.h5']
    ['coordinates', 'meta', 'pressure_100m', 'pressure_200m',
     'temperature_100m', 'temperature_200m', 'time_index',
     'winddirection_100m', 'winddirection_200m', 'windspeed_100m',
     'windspeed_200m']

    MultiFileWTK, like WindResource can interpolate / extrapolate hub-heights

    >>> with MultiFileWTK(file) as res:
    >>>     wspd = res['windspeed_150m']
    >>>
    >>> wspd
    [[16.19     16.25     16.305    ... 16.375    16.39     16.39    ]
     [16.15     16.205    16.255001 ... 16.35     16.365    16.39    ]
     [16.154999 16.195    16.23     ... 16.335    16.32     16.34    ]
     ...
     [10.965    11.675    12.08     ... 15.18     14.805    14.42    ]
     [11.66     11.91     12.535    ... 13.31     12.23     12.335   ]
     [12.785    13.295    14.014999 ... 12.205    11.360001 11.64    ]]
    """
    SUFFIX = 'm.h5'

    def __init__(self, h5_path, unscale=True, str_decode=True):
        """
        Parameters
        ----------
        h5_path : str
            Path to directory containing multi-file resource file sets.
            Available formats:
                /h5_dir/
                /h5_dir/prefix*suffix
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        """
        super().__init__(h5_path, unscale=unscale, str_decode=str_decode)
        self._heights = None

    @classmethod
    def preload_SAM(cls, h5_path, sites, hub_heights, unscale=True,
                    str_decode=True, require_wind_dir=False,
                    precip_rate=False, icing=False, means=False):
        """
        Placeholder for classmethod that will pre-load project_points for SAM

        Parameters
        ----------
        h5_path : str
            Path to directory containing multi-file resource file sets.
            Available formats:
                /h5_dir/
                /h5_dir/prefix*suffix
        sites : list
            List of sites to be provided to SAM
        hub_heights : int | float | list
            Hub heights to extract for SAM
        unscale : bool
            Boolean flag to automatically unscale variables on extraction
        str_decode : bool
            Boolean flag to decode the bytestring meta data into normal
            strings. Setting this to False will speed up the meta data read.
        require_wind_dir : bool
            Boolean flag as to whether wind direction will be loaded.
        precip_rate : bool
            Boolean flag as to whether precipitationrate_0m will be preloaded
        icing : bool
            Boolean flag as to whether icing is analyzed.
            This will preload relative humidity.
        means : bool
            Boolean flag to compute mean resource when res_array is set

        Returns
        -------
        SAM_res : SAMResource
            Instance of SAMResource pre-loaded with Solar resource for sites
            in project_points
        """
        with cls(h5_path, unscale=unscale, str_decode=str_decode) as res:
            SAM_res = res._preload_SAM(sites, hub_heights,
                                       require_wind_dir=require_wind_dir,
                                       precip_rate=precip_rate, icing=icing,
                                       means=means)

        return SAM_res
