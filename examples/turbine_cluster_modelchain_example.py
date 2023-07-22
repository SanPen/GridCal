"""
The ``turbine_cluster_modelchain_example`` module shows how to calculate the
power output of wind farms and wind turbine clusters with the windpowerlib.
A cluster can be useful if you want to calculate the feed-in of a region for
which you want to use one single weather data point.

Functions that are used in the ``modelchain_example``, like the initialization
of wind turbines, are imported and used without further explanations.

SPDX-FileCopyrightText: 2019 oemof developer group <contact@oemof.org>
SPDX-License-Identifier: MIT
"""
import pandas as pd

try:
    from matplotlib import pyplot as plt
except ImportError:
    plt = None

from example import modelchain_example as mc_e
from windpowerlib import WindFarm
from windpowerlib import WindTurbineCluster
from windpowerlib import TurbineClusterModelChain

# You can use the logging package to get logging messages from the windpowerlib
# Change the logging level if you want more or less messages
import logging

logging.getLogger().setLevel(logging.DEBUG)


def initialize_wind_farms(my_turbine, e126):
    r"""
    Initializes two :class:`~.wind_farm.WindFarm` objects.

    This function shows how to initialize a WindFarm object. A WindFarm needs
    a wind turbine fleet specifying the wind turbines and their number or
    total installed capacity (in Watt) in the farm. Optionally, you can provide
    a wind farm efficiency (which can be constant or dependent on the wind
    speed) and a name as an identifier. See :class:`~.wind_farm.WindFarm` for
    more information.

    Parameters
    ----------
    my_turbine : :class:`~.wind_turbine.WindTurbine`
        WindTurbine object with self provided power curve.
    e126 : :class:`~.wind_turbine.WindTurbine`
        WindTurbine object with power curve from the OpenEnergy Database
        turbine library.

    Returns
    -------
    tuple(:class:`~.wind_farm.WindFarm`, :class:`~.wind_farm.WindFarm`)

    """

    # specification of wind farm data where turbine fleet is provided in a
    # pandas.DataFrame
    # for each turbine type you can either specify the number of turbines of
    # that type in the wind farm (float values are possible as well) or the
    # total installed capacity of that turbine type in W
    wind_turbine_fleet = pd.DataFrame(
        {
            "wind_turbine": [my_turbine, e126],  # as windpowerlib.WindTurbine
            "number_of_turbines": [6, None],
            "total_capacity": [None, 12.6e6],
        }
    )
    # initialize WindFarm object
    example_farm = WindFarm(
        name="example_farm", wind_turbine_fleet=wind_turbine_fleet
    )

    # specification of wind farm data (2) containing a wind farm efficiency
    # wind turbine fleet is provided using the to_group function
    example_farm_2_data = {
        "name": "example_farm_2",
        "wind_turbine_fleet": [
            my_turbine.to_group(6),
            e126.to_group(total_capacity=12.6e6),
        ],
        "efficiency": 0.9,
    }
    # initialize WindFarm object
    example_farm_2 = WindFarm(**example_farm_2_data)

    return example_farm, example_farm_2


def initialize_wind_turbine_cluster(example_farm, example_farm_2):
    r"""
    Initializes a :class:`~.wind_turbine_cluster.WindTurbineCluster` object.

    Function shows how to initialize a WindTurbineCluster object. A
    WindTurbineCluster consists of wind farms that are specified through the
    `wind_farms` parameter. Optionally, you can provide a name as an
    identifier.

    Parameters
    ----------
    example_farm : :class:`~.wind_farm.WindFarm`
        WindFarm object without provided efficiency.
    example_farm_2 : :class:`~.wind_farm.WindFarm`
        WindFarm object with constant wind farm efficiency.

    Returns
    -------
    :class:`~.wind_turbine_cluster.WindTurbineCluster`

    """

    # specification of cluster data
    example_cluster_data = {
        "name": "example_cluster",
        "wind_farms": [example_farm, example_farm_2],
    }
    # initialize WindTurbineCluster object
    example_cluster = WindTurbineCluster(**example_cluster_data)

    return example_cluster


def calculate_power_output(weather, example_farm, example_cluster):
    r"""
    Calculates power output of wind farms and clusters using the
    :class:`~.turbine_cluster_modelchain.TurbineClusterModelChain`.

    The :class:`~.turbine_cluster_modelchain.TurbineClusterModelChain` is a
    class that provides all necessary steps to calculate the power output of a
    wind farm or cluster. You can either use the default methods for the
    calculation steps, as done for 'example_farm', or choose different methods,
    as done for 'example_cluster'.

    Parameters
    ----------
    weather : :pandas:`pandas.DataFrame<frame>`
        Contains weather data time series.
    example_farm : :class:`~.wind_farm.WindFarm`
        WindFarm object without provided efficiency.
    example_cluster : :class:`~.wind_turbine_cluster.WindTurbineCluster`
        WindTurbineCluster object.

    """
    example_farm.efficiency = 0.9
    # power output calculation for example_farm
    # initialize TurbineClusterModelChain with default parameters and use
    # run_model method to calculate power output
    mc_example_farm = TurbineClusterModelChain(example_farm).run_model(weather)
    # write power output time series to WindFarm object
    example_farm.power_output = mc_example_farm.power_output

    # power output calculation for turbine_cluster
    # own specifications for TurbineClusterModelChain setup
    modelchain_data = {
        "wake_losses_model": "wind_farm_efficiency",  # 'dena_mean' (default), None,
        # 'wind_farm_efficiency' or name
        #  of another wind efficiency curve
        #  see :py:func:`~.wake_losses.get_wind_efficiency_curve`
        "smoothing": True,  # False (default) or True
        "block_width": 0.5,  # default: 0.5
        "standard_deviation_method": "Staffell_Pfenninger",  #
        # 'turbulence_intensity' (default)
        # or 'Staffell_Pfenninger'
        "smoothing_order": "wind_farm_power_curves",  #
        # 'wind_farm_power_curves' (default) or
        # 'turbine_power_curves'
        "wind_speed_model": "logarithmic",  # 'logarithmic' (default),
        # 'hellman' or
        # 'interpolation_extrapolation'
        "density_model": "ideal_gas",  # 'barometric' (default), 'ideal_gas' or
        # 'interpolation_extrapolation'
        "temperature_model": "linear_gradient",  # 'linear_gradient' (def.) or
        # 'interpolation_extrapolation'
        "power_output_model": "power_curve",  # 'power_curve' (default) or
        # 'power_coefficient_curve'
        "density_correction": True,  # False (default) or True
        "obstacle_height": 0,  # default: 0
        "hellman_exp": None,
    }  # None (default) or None
    # initialize TurbineClusterModelChain with own specifications and use
    # run_model method to calculate power output
    mc_example_cluster = TurbineClusterModelChain(
        example_cluster, **modelchain_data
    ).run_model(weather)
    # write power output time series to WindTurbineCluster object
    example_cluster.power_output = mc_example_cluster.power_output

    return


def plot_or_print(example_farm, example_cluster):
    r"""
    Plots or prints power output and power (coefficient) curves.

    Parameters
    ----------
    example_farm : :class:`~.wind_farm.WindFarm`
        WindFarm object without provided efficiency.
    example_cluster : :class:`~.wind_turbine_cluster.WindTurbineCluster`
        WindTurbineCluster object.

    """

    # plot or print power output
    if plt:
        example_cluster.power_output.plot(legend=True, label="example cluster")
        example_farm.power_output.plot(legend=True, label="example farm")
        plt.xlabel("Wind speed in m/s")
        plt.ylabel("Power in W")
        plt.show()
    else:
        print(example_cluster.power_output)
        print(example_farm.power_output)


def run_example():
    r"""
    Runs the example.

    """
    weather = mc_e.get_weather_data("weather.csv")
    my_turbine, e126, my_turbine2 = mc_e.initialize_wind_turbines()
    example_farm, example_farm_2 = initialize_wind_farms(my_turbine, e126)
    example_cluster = initialize_wind_turbine_cluster(
        example_farm, example_farm_2
    )
    calculate_power_output(weather, example_farm, example_cluster)
    plot_or_print(example_farm, example_cluster)


if __name__ == "__main__":
    run_example()
