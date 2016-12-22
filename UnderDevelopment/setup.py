from distutils.core import setup

setup(
    # Application name:
    name="GridCal",

    # Version number (initial):
    version="1.011",

    # Application author details:
    author="Santiago Peñate Vera",
    author_email="santiago.penate.vera@gmail.com",

    # Packages
    packages=["GridCal"],

    # Include additional files into the package
    include_package_data=True,

    # Details
    url="http://pypi.python.org/pypi/GridCal/",

    #
    # license="LICENSE.txt",
    description="Research Oriented electrical simulation software.",

    # long_description=open("README.txt").read(),

    # Dependent packages (distributions)
    install_requires=["numpy",
                      "scipy",
                      "networkx",
                      "pandas",
                      "PyQt5",
                      "matplotlib",
                      "qtconsole"
                      ],
)