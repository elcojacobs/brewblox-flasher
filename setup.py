from setuptools import find_packages, setup

setup(
    name='brewblox-flasher',
    use_scm_version={'local_scheme': lambda v: ''},
    description='Flashing new firmware to BrewPi Spark controllers',
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/brewblox-flasher',
    author='BrewPi',
    author_email='Development@brewpi.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.7',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    license='GPLv3',
    keywords='brewing brewpi brewblox embedded controller spark service',
    packages=find_packages(exclude=['test']),
    install_requires=[
        'pyserial-asyncio==0.4',
        'aiofiles~=0.4',
    ],
    python_requires='>=3.7',
    setup_requires=['setuptools_scm'],
)
