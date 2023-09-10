from setuptools import setup, find_packages


pkgs_to_exclude = ['tests', 'Tutorials', 'GridCal']

# find_packages will do a terrible job and it will find everything regardless of what you tell it to exclude
packages = find_packages(where='.', exclude=pkgs_to_exclude)

# ... so we have to do the filtering ourselves
packages2 = list()
for package in packages:
    elms = package.split('.')
    excluded = False
    for exclude in pkgs_to_exclude:
        if exclude in elms:
            excluded = True

    if not excluded:
        packages2.append(package)

setup(
    name='GridCalEngine',
    version='1.0.0',  # Update with your version number
    description='Your backend description',
    author='Your Name',
    author_email='your.email@example.com',
    packages=packages2,  # Automatically discover packages in the GridCalEngine directory
    install_requires=[
        # List any dependencies required for the backend package here
    ],
)